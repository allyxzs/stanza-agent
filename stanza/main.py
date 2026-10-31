"""Stanza v0.2 HTTP API, backwards compatible with v0.1."""
from __future__ import annotations
import difflib
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from .core import MAX_BYTES, analyze, parse_document
from .advanced import answer, get_document, list_documents, save_document, search

app = FastAPI(title='Stanza | ARA OS 12', version='0.2.0', description='Inteligência documental local com pesquisa e evidências')

async def read_upload(file: UploadFile):
    try:
        content = await file.read(MAX_BYTES + 1)
        return parse_document(file.filename or 'arquivo', content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()

class Question(BaseModel):
    pergunta: str = Field(min_length=3, max_length=1000)
    documento_id: str | None = None

@app.get('/health')
def health():
    return {'status': 'ok', 'agente': 'Stanza', 'versao': '0.2.0'}

@app.post('/analisar')
async def analisar(arquivo: UploadFile = File(...), frases: int = Query(5, ge=1, le=20)):
    return analyze(await read_upload(arquivo), frases)

@app.post('/comparar')
async def comparar(original: UploadFile = File(...), atualizado: UploadFile = File(...)):
    old = await read_upload(original)
    new = await read_upload(atualizado)
    diff = list(difflib.unified_diff(old.text.splitlines(), new.text.splitlines(), fromfile=old.filename, tofile=new.filename, lineterm=''))
    return {'original': old.filename, 'atualizado': new.filename, 'iguais': old.sha256 == new.sha256, 'diferencas': diff[:500], 'truncado': len(diff) > 500}

@app.post('/documentos')
async def documentos_adicionar(arquivo: UploadFile = File(...)):
    return save_document(await read_upload(arquivo))

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
