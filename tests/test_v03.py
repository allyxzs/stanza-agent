import io

import fitz
import httpx
import pytest
from fastapi.testclient import TestClient

from stanza import advanced, core, intelligence
from stanza.main import app

client = TestClient(app)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(advanced, 'DB_PATH', tmp_path / 'documents.sqlite3')
    return tmp_path


def test_ui_and_health(monkeypatch):
    monkeypatch.delenv('STANZA_LLM_API_KEY', raising=False)
    monkeypatch.delenv('STANZA_LLM_MODEL', raising=False)
    assert client.get('/').status_code == 200
    assert 'STANZA' in client.get('/').text
    health = client.get('/health').json()
    assert health['versao'] == '0.3.0'
    assert health['ia_configurada'] is False


def test_search_index_and_reference(db, monkeypatch):
    monkeypatch.delenv('STANZA_EMBED_MODEL', raising=False)
    saved = client.post('/documentos', files={
        'arquivo': ('relatorio.txt', 'Relatório financeiro de outubro. Receita total R$ 12.500,00.'.encode('utf-8'))
    })
    assert saved.status_code == 200
    ident = saved.json()['id']
    results = client.post('/busca-avancada?modo=lexical', json={
        'pergunta': 'Qual a receita total?', 'documento_id': ident
    })
    assert results.status_code == 200
    data = results.json()
    assert data['metodo'] == 'lexical'
    assert data['resultados'][0]['arquivo'] == 'relatorio.txt'
    assert data['resultados'][0]['pagina'] == 1
    assert '12.500' in data['resultados'][0]['trecho']
    assert client.post('/busca-avancada', json={'pergunta':'receita','documento_id':'missing'}).status_code == 404


def test_legacy_endpoints_still_work(db):
    x = client.post('/analisar', files={'arquivo':('contrato.txt', b'Contrato entre contratante e contratada. Valor R$ 123,00.')})
    assert x.status_code == 200
    assert x.json()['classificacao']['categoria'] == 'contrato'
    y = client.post('/comparar', files={
        'original':('a.txt',b'Old version'), 'atualizado':('b.txt',b'New version')
    })
    assert y.status_code == 200 and y.json()['iguais'] is False


def test_ai_unconfigured(db, monkeypatch):
    monkeypatch.delenv('STANZA_LLM_API_KEY', raising=False)
    monkeypatch.delenv('STANZA_LLM_MODEL', raising=False)
    r = client.post('/responder-ia', json={'pergunta':'Qual o valor?'})
    assert r.status_code == 503
    assert 'STANZA_LLM_API_KEY' in r.json()['detail']


def test_semantic_mode_unconfigured(db, monkeypatch):
    monkeypatch.delenv('STANZA_EMBED_MODEL', raising=False)
    doc = core.parse_document('exemplo.txt', b'Documento com detalhes financeiros importantes.')
    advanced.save_document(doc)
    r = client.post('/busca-avancada?modo=semantica', json={'pergunta':'financas'})
    assert r.status_code == 503


def test_semantic_scores_with_stub(db, monkeypatch):
    advanced.save_document(core.parse_document('contrato.txt', b'Valor de pagamento total de contrato.'))
    monkeypatch.setenv('STANZA_EMBED_MODEL', 'fake-model')
    monkeypatch.setattr(intelligence, '_semantic_scores', lambda question, chunks:[0.8] * len(chunks))
    result = intelligence.advanced_search('quantia do acordo', modo='semantica')
    assert result['metodo'] == 'semantica'
    assert result['resultados'][0]['pontuacao'] == 0.8


def test_ocr_pdf(monkeypatch):
    pdf = fitz.open()
    page = pdf.new_page()
    # An empty PDF triggers OCR; stub removes dependency on system language packs.
    content = pdf.tobytes()
    pdf.close()
    monkeypatch.setattr(core, 'ocr_page', lambda page:'Texto reconhecido pelo OCR.\nValor total R$ 30,00')
    doc = core.parse_document('scanned.pdf', content)
    assert doc.ocr_pages == [1]
    assert 'reconhecido' in doc.text
    assert core.analyze(doc)['ocr_paginas'] == [1]


def test_pdf_ocr_opt_out():
    pdf = fitz.open()
    pdf.new_page()
    raw = pdf.tobytes()
    pdf.close()
    with pytest.raises(ValueError, match='Nenhum texto'):
        core.parse_document('scanned.pdf', raw, ocr='nao')


def test_ai_answer_with_mock_transport(db, monkeypatch):
    advanced.save_document(core.parse_document('relatorio.txt', 'Relatorio. O valor total e R$ 1.200,00.'.encode()))
    monkeypatch.setenv('STANZA_LLM_API_KEY', 'dummy-test-token')
    monkeypatch.setenv('STANZA_LLM_MODEL', 'fake-test-model')
    monkeypatch.delenv('STANZA_EMBED_MODEL', raising=False)
    recorded = {}
    def handler(req):
        recorded['request'] = req
        return httpx.Response(200, json={'choices': [{'message':{'content':'O valor é R$ 1.200,00 [FONTE 1].'}}]})
    real_client = httpx.Client
    monkeypatch.setattr(intelligence.httpx, 'Client', lambda **kwargs:real_client(transport=httpx.MockTransport(handler), **kwargs))
    result = intelligence.llm_answer('valor total', modo='lexical')
    assert result['modo'] == 'ia_com_evidencias'
    assert '[FONTE 1]' in result['resposta']
    assert 'Bearer dummy-test-token' == recorded['request'].headers['authorization']
    assert 'R$ 1.200' in recorded['request'].content.decode()


def test_oversized_upload_and_bad_mode():
    r = client.post('/analisar', files={'arquivo':('a.txt', b'a' * (core.MAX_BYTES + 1))})
    assert r.status_code == 422
    assert client.post('/busca-avancada?modo=wrong', json={'pergunta':'valor'}).status_code == 422
