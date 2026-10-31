"""Stanza HTTP API."""
from __future__ import annotations

import difflib
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from .core import MAX_BYTES, analyze, parse_document

app = FastAPI(title="Stanza | ARA OS 12", version="0.1.0", description="Análise local de PDF, DOCX e TXT")


async def read_upload(file: UploadFile):
    try:
        content = await file.read(MAX_BYTES + 1)
        return parse_document(file.filename or "arquivo", content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        await file.close()


@app.get("/health")
def health():
    return {"status": "ok", "agente": "Stanza", "versao": "0.1.0"}


@app.post("/analisar")
async def analisar(arquivo: UploadFile = File(...), frases: int = Query(5, ge=1, le=20)):
    doc = await read_upload(arquivo)
    return analyze(doc, frases)


@app.post("/comparar")
async def comparar(original: UploadFile = File(...), atualizado: UploadFile = File(...)):
    old = await read_upload(original)
    new = await read_upload(atualizado)
    diff = list(difflib.unified_diff(old.text.splitlines(), new.text.splitlines(), fromfile=old.filename, tofile=new.filename, lineterm=""))
    return {"original": old.filename, "atualizado": new.filename, "iguais": old.sha256 == new.sha256, "diferencas": diff[:500], "truncado": len(diff) > 500}
