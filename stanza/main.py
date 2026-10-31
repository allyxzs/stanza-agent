"""API do Stanza 0.4. Mantém os endpoints anteriores sem excluir dados."""
from __future__ import annotations

import difflib
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .advanced import answer, get_document, list_documents, search
from .core import MAX_BYTES, analyze, ocr_available, parse_document
from .intelligence import advanced_search, llm_answer, llm_enabled, semantic_enabled
from .contracts import analyze_contract
from .duplicates import record_import, duplicate_report, check_document
from .integration import manifest, events, record
from .organizer import preview_plan, apply_plan
import os

app = FastAPI(title='Stanza | ARA OS 12', version='0.4.0',
              description='Inteligência documental: organização segura, duplicatas, cláusulas, OCR e IA opcional')


async def read_upload(file: UploadFile, ocr: str = 'auto'):
    try:
        content = await file.read(MAX_BYTES + 1)
        return parse_document(file.filename or 'arquivo', content, ocr=ocr)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()


class Question(BaseModel):
    pergunta: str = Field(min_length=3, max_length=1000)
    documento_id: str | None = Field(default=None, max_length=64)


@app.get('/')
def pagina_inicial():
    return FileResponse(Path(__file__).parent / 'web' / 'index.html')


@app.get('/health')
def health():
    return {'status': 'ok', 'agente': 'Stanza', 'versao': '0.4.0',
            'ocr_disponivel': ocr_available(), 'ia_configurada': llm_enabled(),
            'busca_semantica_configurada': semantic_enabled(),
            'organizacao_configurada': bool(os.getenv('STANZA_ORGANIZE_ROOT', '').strip())}


@app.post('/analisar')
async def analisar(arquivo: UploadFile = File(...), frases: int = Query(5, ge=1, le=20),
                  ocr: str = Query('auto', pattern='^(auto|sim|nao)$')):
    return analyze(await read_upload(arquivo, ocr), frases)


@app.post('/comparar')
async def comparar(original: UploadFile = File(...), atualizado: UploadFile = File(...),
                   ocr: str = Query('auto', pattern='^(auto|sim|nao)$')):
    old = await read_upload(original, ocr)
    new = await read_upload(atualizado, ocr)
    diff = list(difflib.unified_diff(old.text.splitlines(), new.text.splitlines(),
                                     fromfile=old.filename, tofile=new.filename, lineterm=''))
    return {'original': old.filename, 'atualizado': new.filename,
            'iguais': old.sha256 == new.sha256, 'diferencas': diff[:500],
            'truncado': len(diff) > 500}


@app.post('/documentos')
async def documentos_adicionar(arquivo: UploadFile = File(...),
                               ocr: str = Query('auto', pattern='^(auto|sim|nao)$')):
    doc = await read_upload(arquivo, ocr)
    result = record_import(doc)
    record('document.indexed', {'documento_id': doc.sha256, 'arquivo': doc.filename,
                                'duplicado': result['duplicado']})
    return result


@app.get('/documentos')
def documentos_listar():
    return list_documents()


@app.get('/documentos/{documento_id}')
def documentos_detalhe(documento_id: str):
    doc = get_document(documento_id)
    if not doc:
        raise HTTPException(status_code=404, detail='Documento não encontrado.')
    return {k: v for k, v in doc.items() if k != 'paginas'}


@app.post('/pesquisar')
def pesquisar(query: Question, limite: int = Query(5, ge=1, le=20)):
    try:
        return {'resultados': search(query.pergunta, query.documento_id, limite)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/perguntar')
def perguntar(query: Question):
    try:
        return answer(query.pergunta, query.documento_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/busca-avancada')
def busca_avancada(query: Question, limite: int = Query(5, ge=1, le=20),
                   modo: str = Query('auto', pattern='^(auto|lexical|semantica)$')):
    try:
        return advanced_search(query.pergunta, query.documento_id, limite, modo)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post('/responder-ia')
def responder_ia(query: Question, modo: str = Query('auto', pattern='^(auto|lexical|semantica)$')):
    try:
        return llm_answer(query.pergunta, query.documento_id, modo)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# Novidades v0.4 -------------------------------------------------------------

class OrganizationApproval(BaseModel):
    plano_id: str = Field(min_length=10, max_length=120)
    confirmar: bool = False


@app.get('/duplicatas')
def duplicatas_listar(limite: int = Query(50, ge=1, le=200),
                      limiar: float = Query(0.78, ge=0.5, le=1)):
    return duplicate_report(threshold=limiar, limit=limite)


@app.post('/duplicatas/verificar')
async def duplicatas_verificar(arquivo: UploadFile = File(...),
                              ocr: str = Query('auto', pattern='^(auto|sim|nao)$')):
    doc = await read_upload(arquivo, ocr)
    return check_document(doc)


@app.post('/contratos/analisar')
async def contratos_analisar(arquivo: UploadFile = File(...),
                            ocr: str = Query('auto', pattern='^(auto|sim|nao)$')):
    doc = await read_upload(arquivo, ocr)
    result = analyze_contract(doc)
    record('contract.reviewed', {'documento_id': doc.sha256,
                                 'arquivo': doc.filename,
                                 'clausulas': len(result['clausulas']),
                                 'sinais_para_revisao': len(result['sinais_para_revisao'])})
    return result


@app.get('/documentos/{documento_id}/clausulas')
def contratos_documento(documento_id: str):
    doc = get_document(documento_id)
    if not doc:
        raise HTTPException(status_code=404, detail='Documento não encontrado.')
    from .core import ParsedDocument
    parsed = ParsedDocument(filename=doc['arquivo'], pages=doc['paginas'], sha256=doc['id'])
    return analyze_contract(parsed)


@app.post('/organizacao/prever')
def organizacao_prever():
    try:
        return preview_plan()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/organizacao/aplicar')
def organizacao_aplicar(payload: OrganizationApproval):
    try:
        result = apply_plan(payload.plano_id, payload.confirmar)
        record('document.organized', {'plano_id': payload.plano_id,
                                      'quantidade_copiada': result['quantidade_copiada']})
        return result
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail='Falha de disco ao copiar arquivos; confira a pasta de saída.') from exc


@app.get('/integracao/manifesto')
def integracao_manifesto():
    return manifest()


@app.get('/integracao/eventos')
def integracao_eventos(limite: int = Query(30, ge=1, le=100)):
    return events(limite)
