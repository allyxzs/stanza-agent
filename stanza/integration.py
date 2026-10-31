"""Contrato mínimo de integração do Stanza com outros agentes ARA OS 12.

Eventos ficam APENAS no SQLite local; não são publicados na rede.
"""
from __future__ import annotations

import json
from . import advanced

VERSION = '0.4.0'
EVENTS = ('document.indexed', 'document.organized', 'contract.reviewed')


def manifest() -> dict:
    return {
        'agente': 'Stanza', 'sistema': 'ARA OS 12', 'versao': VERSION,
        'transporte': 'consulta_local_api', 'autenticacao': 'nenhuma (apenas localhost)',
        'eventos': list(EVENTS),
        'rotas': ['/integracao/manifesto', '/integracao/eventos'],
        'observacao': 'Ainda não envia eventos automaticamente a outros agentes; '
                      'fornece histórico local para integração futura.'
    }


def _ensure_table(db):
    db.execute('''CREATE TABLE IF NOT EXISTS agent_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_name TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )''')


def record(event_name: str, payload: dict) -> None:
    if event_name not in EVENTS:
        raise ValueError('Evento não suportado.')
    # Não aceita payloads enormes nem texto integral dos documentos.
    serialized = json.dumps(payload, ensure_ascii=False)
    if len(serialized) > 6000:
        raise ValueError('Evento muito grande.')
    with advanced._lock, advanced.connection() as db:
        _ensure_table(db)
        db.execute('INSERT INTO agent_events(event_name,payload_json) VALUES (?,?)',
                   (event_name, serialized))


def events(limit: int = 30) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ValueError('limit deve estar entre 1 e 100.')
    with advanced.connection() as db:
        _ensure_table(db)
        rows = db.execute('SELECT event_id,event_name,payload_json,created_at FROM agent_events ORDER BY event_id DESC LIMIT ?',
                          (limit,)).fetchall()
    return [{'id': event_id, 'evento': event_name, 'dados': json.loads(data), 'data': created}
            for event_id, event_name, data, created in rows]
