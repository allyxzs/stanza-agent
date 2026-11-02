"""Orquestração local e persistente de fluxos documentais do Stanza v0.5.

Os fluxos são executados de forma síncrona, sem fila externa. O histórico guarda
metadados, parâmetros e resultados resumidos; não duplica o conteúdo integral dos
arquivos já armazenados no catálogo.
"""
from __future__ import annotations

import difflib
import json
import re
import secrets
from typing import Any

from . import advanced
from .contracts import analyze_contract
from .core import ParsedDocument, analyze
from .intelligence import advanced_search

WORKFLOWS: dict[str, dict[str, Any]] = {
    "resumo_documento": {
        "nome": "Resumo e extração",
        "descricao": "Gera resumo extrativo, classificação e campos identificados de um documento indexado.",
        "campos": ["documento_id"],
    },
    "revisao_contrato": {
        "nome": "Revisão documental de contrato",
        "descricao": "Identifica títulos de cláusulas, temas e sinais para revisão humana, com evidências.",
        "campos": ["documento_id"],
    },
    "pesquisa_documental": {
        "nome": "Pesquisa fundamentada",
        "descricao": "Busca trechos relevantes nos documentos indexados; não inventa respostas.",
        "campos": ["pergunta", "documento_id (opcional)", "modo_busca"],
    },
    "comparacao_documental": {
        "nome": "Comparação de versões",
        "descricao": "Compara dois documentos indexados e lista diferenças textuais com limite de saída.",
        "campos": ["documento_id", "documento_id_b"],
    },
}

ID_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")
MAX_REPORT_CHARS = 180_000


def ensure_table(db) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS workflow_tasks (
            task_id TEXT PRIMARY KEY,
            workflow TEXT NOT NULL,
            status TEXT NOT NULL,
            request_json TEXT NOT NULL,
            result_json TEXT,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT
        )"""
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_workflow_tasks_created ON workflow_tasks(created_at)")


def workflow_catalog() -> dict:
    return {
        "agente": "Stanza",
        "versao": "0.5.0",
        "execucao": "sincrona_local",
        "fluxos": [
            {"id": key, **value}
            for key, value in WORKFLOWS.items()
        ],
        "observacao": "Os fluxos usam documentos previamente indexados. Resultados automatizados devem ser revisados por uma pessoa.",
    }


def _document(document_id: str | None) -> dict:
    if not document_id or not ID_PATTERN.fullmatch(document_id):
        raise ValueError("Informe um documento_id SHA-256 válido.")
    doc = advanced.get_document(document_id)
    if not doc:
        raise LookupError("Documento não encontrado. Indexe o arquivo antes de executar o fluxo.")
    return doc


def validate_request(workflow: str, payload: dict) -> dict:
    if workflow not in WORKFLOWS:
        raise ValueError("Fluxo não suportado. Consulte GET /fluxos.")
    if not isinstance(payload, dict):
        raise ValueError("O corpo da solicitação deve ser um objeto JSON.")
    clean: dict[str, Any] = {}
    if workflow in {"resumo_documento", "revisao_contrato"}:
        doc_id = payload.get("documento_id")
        _document(doc_id)
        clean["documento_id"] = doc_id
    elif workflow == "pesquisa_documental":
        question = payload.get("pergunta")
        if not isinstance(question, str) or not 3 <= len(question.strip()) <= 1000:
            raise ValueError("A pergunta deve conter entre 3 e 1000 caracteres.")
        doc_id = payload.get("documento_id")
        if doc_id is not None:
            _document(doc_id)
        mode = payload.get("modo_busca", "lexical")
        if mode not in {"lexical", "semantica", "auto"}:
            raise ValueError("modo_busca deve ser lexical, semantica ou auto.")
        clean.update(pergunta=question.strip(), documento_id=doc_id, modo_busca=mode)
    elif workflow == "comparacao_documental":
        first = payload.get("documento_id")
        second = payload.get("documento_id_b")
        _document(first)
        _document(second)
        if first == second:
            raise ValueError("Selecione dois documentos diferentes para comparar.")
        clean.update(documento_id=first, documento_id_b=second)
    return clean


def _parsed(doc: dict) -> ParsedDocument:
    return ParsedDocument(filename=doc["arquivo"], pages=doc["paginas"], sha256=doc["id"])


def _execute(workflow: str, payload: dict) -> dict:
    if workflow == "resumo_documento":
        doc = _document(payload["documento_id"])
        result = analyze(_parsed(doc))
        return {
            "documento_id": doc["id"],
            "arquivo": doc["arquivo"],
            "classificacao": result["classificacao"],
            "dados_extraidos": result["dados"],
            "resumo_extrativo": result["resumo_extrativo"],
            "paginas": result["paginas"],
            "observacao": "Resumo extrativo local; não é interpretação jurídica nem validação dos dados.",
        }
    if workflow == "revisao_contrato":
        doc = _document(payload["documento_id"])
        result = analyze_contract(_parsed(doc))
        return {"documento_id": doc["id"], **result}
    if workflow == "pesquisa_documental":
        result = advanced_search(
            payload["pergunta"], payload.get("documento_id"), limite=8,
            modo=payload.get("modo_busca", "lexical"),
        )
        return {
            "pergunta": payload["pergunta"],
            "documento_id": payload.get("documento_id"),
            "metodo": result["metodo"],
            "resultados": result["resultados"],
            "observacao": "São evidências localizadas, não uma conclusão gerada por IA.",
        }
    if workflow == "comparacao_documental":
        old = _document(payload["documento_id"])
        new = _document(payload["documento_id_b"])
        old_text = "\n\n".join(old["paginas"])
        new_text = "\n\n".join(new["paginas"])
        diff = list(difflib.unified_diff(
            old_text.splitlines(), new_text.splitlines(),
            fromfile=old["arquivo"], tofile=new["arquivo"], lineterm="",
        ))
        clipped = [line[:600] for line in diff[:200]]
        return {
            "documento_a": {"id": old["id"], "arquivo": old["arquivo"]},
            "documento_b": {"id": new["id"], "arquivo": new["arquivo"]},
            "iguais": old["id"] == new["id"],
            "diferencas": clipped,
            "truncado": len(diff) > 300 or any(len(line) > 1200 for line in diff[:300]),
            "observacao": "Comparação textual; diferenças de formatação e contexto jurídico exigem revisão humana.",
        }
    raise ValueError("Fluxo não suportado.")


def _save_task(task_id: str, workflow: str, status: str, request: dict,
               result: dict | None = None, error: str | None = None,
               finished: bool = False) -> None:
    serialized_result = json.dumps(result, ensure_ascii=False) if result is not None else None
    if serialized_result and len(serialized_result) > MAX_REPORT_CHARS:
        raise ValueError("Resultado excedeu o limite de armazenamento da tarefa.")
    with advanced._lock, advanced.connection() as db:
        ensure_table(db)
        db.execute(
            """INSERT INTO workflow_tasks(task_id,workflow,status,request_json,result_json,error,finished_at)
               VALUES(?,?,?,?,?,?,CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END)""",
            (task_id, workflow, status, json.dumps(request, ensure_ascii=False),
             serialized_result, error, int(finished)),
        )


def _finish_task(task_id: str, status: str, result: dict | None = None,
                 error: str | None = None) -> None:
    serialized_result = json.dumps(result, ensure_ascii=False) if result is not None else None
    if serialized_result and len(serialized_result) > MAX_REPORT_CHARS:
        status, serialized_result, error = "falhou", None, "Resultado excedeu o limite de armazenamento da tarefa."
    with advanced._lock, advanced.connection() as db:
        ensure_table(db)
        db.execute(
            "UPDATE workflow_tasks SET status=?, result_json=?, error=?, finished_at=CURRENT_TIMESTAMP WHERE task_id=?",
            (status, serialized_result, error, task_id),
        )


def get_task(task_id: str) -> dict | None:
    with advanced.connection() as db:
        ensure_table(db)
        row = db.execute(
            "SELECT task_id,workflow,status,request_json,result_json,error,created_at,finished_at FROM workflow_tasks WHERE task_id=?",
            (task_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "task_id": row[0], "fluxo": row[1], "status": row[2],
        "solicitacao": json.loads(row[3]),
        "resultado": json.loads(row[4]) if row[4] else None,
        "erro": row[5], "criada_em": row[6], "finalizada_em": row[7],
    }


def list_tasks(limit: int = 30) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ValueError("limit deve estar entre 1 e 100.")
    with advanced.connection() as db:
        ensure_table(db)
        rows = db.execute(
            "SELECT task_id,workflow,status,error,created_at,finished_at FROM workflow_tasks ORDER BY rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {"task_id": r[0], "fluxo": r[1], "status": r[2], "erro": r[3],
         "criada_em": r[4], "finalizada_em": r[5]}
        for r in rows
    ]


def run_workflow(workflow: str, payload: dict) -> dict:
    clean = validate_request(workflow, payload)
    task_id = secrets.token_hex(16)
    _save_task(task_id, workflow, "executando", clean)
    try:
        result = _execute(workflow, clean)
        _finish_task(task_id, "concluida", result=result)
    except Exception as exc:
        # A API guarda uma mensagem curta, sem traceback, tokens ou conteúdo integral.
        safe_error = str(exc)[:500] or "Falha desconhecida ao executar o fluxo."
        _finish_task(task_id, "falhou", error=safe_error)
    task = get_task(task_id)
    if task is None:  # Defensive; should not happen after successful insert.
        raise RuntimeError("Não foi possível recuperar o registro da tarefa.")
    return task


def task_report(task: dict) -> str:
    result = task.get("resultado") or {}
    lines = [
        "# Relatório de execução do Stanza",
        "",
        f"- **Tarefa:** `{task['task_id']}`",
        f"- **Fluxo:** {task['fluxo']}",
        f"- **Status:** {task['status']}",
        f"- **Criada em:** {task['criada_em']}",
        f"- **Finalizada em:** {task['finalizada_em'] or 'não finalizada'}",
        "",
    ]
    if task.get("erro"):
        lines.extend(["## Erro", "", task["erro"], ""])
    if result:
        lines.extend(["## Resultado", "", "```json", json.dumps(result, ensure_ascii=False, indent=2), "```", ""])
    lines.extend(["---", "Relatório gerado localmente pelo Stanza. Revise as evidências antes de tomar decisões."])
    return "\n".join(lines)
