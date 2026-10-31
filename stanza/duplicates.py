"""Catálogo de importações repetidas e documentos com conteúdo semelhante.

O SQLite da v0.3 deduplicava por SHA-256; a v0.4 mantém a chave e registra
cada nova importação em tabela aditiva. Não apaga conteúdo automaticamente.
"""
from __future__ import annotations

import json
import re
import unicodedata
from itertools import combinations
from . import advanced
from .core import ParsedDocument


def _ensure_tables(db):
    db.execute('''CREATE TABLE IF NOT EXISTS document_imports (
        import_id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_imports_document_id ON document_imports(document_id)')


def record_import(document: ParsedDocument) -> dict:
    """Indexa pelo fluxo existente e registra a ocorrência, mesmo para SHA igual."""
    was_indexed = advanced.get_document(document.sha256) is not None
    saved = advanced.save_document(document)
    with advanced._lock, advanced.connection() as db:
        _ensure_tables(db)
        previous = db.execute('SELECT COUNT(*) FROM document_imports WHERE document_id=?',
                              (document.sha256,)).fetchone()[0]
        # A v0.3 não tinha tabela de histórico de envios: o registro original
        # pode existir, mas não é possível reconstruir quantos uploads ocorreram.
        db.execute('INSERT INTO document_imports(document_id,filename) VALUES (?, ?)',
                   (document.sha256, document.filename))
        count = previous + 1
    return {**saved, 'duplicado': was_indexed or previous > 0,
            'ocorrencias_registradas_v04': count}


def _normalize(text: str) -> str:
    text = unicodedata.normalize('NFKD', text.casefold())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return ' '.join(re.findall(r'\w+', text))[:20_000]


def _shingles(text: str, n: int = 3) -> set[str]:
    words = _normalize(text).split()
    return {' '.join(words[i:i+n]) for i in range(len(words) - n + 1)}


def _similarity(left: str, right: str) -> float:
    a, b = _shingles(left), _shingles(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def duplicate_report(*, threshold: float = 0.78, limit: int = 50) -> dict:
    if not .5 <= threshold <= 1 or not 1 <= limit <= 200:
        raise ValueError('threshold deve estar entre 0.5 e 1; limit entre 1 e 200.')
    with advanced.connection() as db:
        _ensure_tables(db)
        imports = db.execute('''SELECT document_id, COUNT(*), COUNT(DISTINCT filename)
                                FROM document_imports GROUP BY document_id
                                HAVING COUNT(*) > 1 ORDER BY COUNT(*) DESC LIMIT ?''', (limit,)).fetchall()
        exact = []
        for doc_id, count, _ in imports:
            names = db.execute('SELECT DISTINCT filename FROM document_imports WHERE document_id=? ORDER BY filename',
                               (doc_id,)).fetchall()
            exact.append({'documento_id': doc_id, 'sha256': doc_id,
                          'ocorrencias_registradas_v04': count,
                          'nomes': [item[0] for item in names]})
        rows = db.execute('SELECT id, filename, pages_json FROM documents ORDER BY created_at DESC LIMIT 100').fetchall()
    similar = []
    for (a_id, a_name, a_pages), (b_id, b_name, b_pages) in combinations(rows, 2):
        a_text = ' '.join(json.loads(a_pages))[:20_000]
        b_text = ' '.join(json.loads(b_pages))[:20_000]
        # Textos mínimos geram falsos positivos com frequência.
        if min(len(a_text.strip()), len(b_text.strip())) < 80:
            continue
        score = _similarity(a_text, b_text)
        if score >= threshold:
            similar.append({'documento_a': a_id, 'arquivo_a': a_name,
                            'documento_b': b_id, 'arquivo_b': b_name,
                            'similaridade_textual': round(score, 4), 'tipo': 'possivel_duplicata'})
    similar.sort(key=lambda item: item['similaridade_textual'], reverse=True)
    return {'duplicatas_exatas': exact, 'possiveis_semelhantes': similar[:limit],
            'limite_documentos_comparados': 100,
            'observacao': 'Similaridade é uma heurística; não significa equivalência jurídica. '
                          'Registros de importação anteriores à v0.4 não podem ser recuperados.'}


def check_document(document: ParsedDocument) -> dict:
    with advanced.connection() as db:
        existing = db.execute('SELECT id, filename FROM documents WHERE id=?', (document.sha256,)).fetchone()
        rows = db.execute('SELECT id, filename, pages_json FROM documents ORDER BY created_at DESC LIMIT 100').fetchall()
    similar = []
    for doc_id, filename, pages in rows:
        if doc_id == document.sha256:
            continue
        text = ' '.join(json.loads(pages))[:20_000]
        if min(len(text.strip()), len(document.text.strip())) < 80:
            continue
        score = _similarity(document.text[:20_000], text)
        if score >= .78:
            similar.append({'documento_id': doc_id, 'arquivo': filename,
                            'similaridade_textual': round(score, 4)})
    similar.sort(key=lambda x:x['similaridade_textual'], reverse=True)
    return {'sha256': document.sha256, 'duplicata_exata': bool(existing),
            'documento_existente': {'id': existing[0], 'arquivo': existing[1]} if existing else None,
            'possiveis_semelhantes': similar[:10]}
