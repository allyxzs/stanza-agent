"""API HTTP do Stanza 0.3. Mantém os endpoints e schemas principais da v0.2."""
from __future__ import annotations

import difflib
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .advanced import answer, get_document, list_documents, save_document, search
from .core import MAX_BYTES, analyze, ocr_available, parse_document
from .intelligence import advanced_search, llm_answer, llm_enabled, semantic_enabled

app = FastAPI(title='Stanza | ARA OS 12', version='0.3.0',
              description='Inteligência documental: OCR, busca, IA opcional e rastreabilidade')


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
    return {'status': 'ok', 'agente': 'Stanza', 'versao': '0.3.0',
            'ocr_disponivel': ocr_available(), 'ia_configurada': llm_enabled(),
            'busca_semantica_configurada': semantic_enabled()}


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
    return save_document(await read_upload(arquivo, ocr))


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
