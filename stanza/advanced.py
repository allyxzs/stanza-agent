"""Stanza v0.2: searchable local document store and grounded Q&A."""
from __future__ import annotations
import json
import os
import re
import sqlite3
import threading
from pathlib import Path
from .core import ParsedDocument, analyze

DB_PATH = Path(os.getenv('STANZA_DB_PATH', str(Path.home() / '.stanza' / 'documents.sqlite3')))
_lock = threading.RLock()

def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, filename TEXT NOT NULL, pages_json TEXT NOT NULL, analysis_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
    return db

def save_document(doc: ParsedDocument) -> dict:
    data = analyze(doc)
    with _lock, connection() as db:
        db.execute('INSERT OR IGNORE INTO documents (id, filename, pages_json, analysis_json) VALUES (?, ?, ?, ?)', (doc.sha256, doc.filename, json.dumps(doc.pages, ensure_ascii=False), json.dumps(data, ensure_ascii=False)))
    return {'id': doc.sha256, 'analise': data}

def get_document(doc_id: str) -> dict | None:
    with connection() as db:
        row = db.execute('SELECT id, filename, pages_json, analysis_json, created_at FROM documents WHERE id=?', (doc_id,)).fetchone()
    if not row:
        return None
    return {'id': row[0], 'arquivo': row[1], 'paginas': json.loads(row[2]), 'analise': json.loads(row[3]), 'criado_em': row[4]}

def list_documents() -> list[dict]:
    with connection() as db:
        rows = db.execute('SELECT id, filename, created_at FROM documents ORDER BY created_at DESC LIMIT 200').fetchall()
    return [{'id': i, 'arquivo': name, 'criado_em': created} for i, name, created in rows]

def _terms(value: str) -> set[str]:
    return {x for x in re.findall(r'\w+', value.casefold()) if len(x) > 2}

def search(question: str, doc_id: str | None = None, limit: int = 5) -> list[dict]:
    if not question.strip():
        raise ValueError('Informe uma pergunta ou termo de busca.')
    terms = _terms(question)
    if not terms:
        raise ValueError('Busca sem termos significativos.')
    with connection() as db:
        if doc_id:
            rows = db.execute('SELECT id, filename, pages_json FROM documents WHERE id=?', (doc_id,)).fetchall()
        else:
            rows = db.execute('SELECT id, filename, pages_json FROM documents ORDER BY created_at DESC LIMIT 200').fetchall()
    hits = []
    for ident, filename, pages_json in rows:
        for page_number, page in enumerate(json.loads(pages_json), 1):
            chunks = [page[i:i+1400] for i in range(0, len(page), 1200)]
            for chunk in chunks:
                found = terms & _terms(chunk)
                if found:
                    hits.append({'documento_id': ident, 'arquivo': filename, 'pagina': page_number, 'trecho': chunk[:1000], 'pontuacao': len(found) / len(terms)})
    hits.sort(key=lambda x: x['pontuacao'], reverse=True)
    return hits[:limit]

def answer(question: str, doc_id: str | None = None) -> dict:
    hits = search(question, doc_id)
    return {'pergunta': question, 'resposta': ('Trechos encontrados nos documentos. Confira as evidências abaixo; o modo local não gera conclusões além do texto.' if hits else 'Não encontrei evidências suficientes nos documentos indexados.'), 'fontes': hits, 'modo': 'busca_local_fundamentada'}
