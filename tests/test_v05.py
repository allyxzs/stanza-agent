"""Testes dos fluxos persistentes e integração autenticada da v0.5."""
import pytest
from fastapi.testclient import TestClient

from stanza import advanced
from stanza.main import app

client = TestClient(app)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(advanced, 'DB_PATH', tmp_path / 'stanza-v05.sqlite3')
    monkeypatch.delenv('STANZA_INTEGRATION_TOKEN', raising=False)
    monkeypatch.delenv('STANZA_EMBED_MODEL', raising=False)
    return tmp_path


def index_doc(name: str, text: str) -> str:
    response = client.post('/documentos', files={'arquivo': (name, text.encode('utf-8'))})
    assert response.status_code == 200, response.text
    return response.json()['id']


def test_v05_catalog_and_health(isolated):
    health = client.get('/health').json()
    assert health['versao'] == '0.5.0'
    catalog = client.get('/fluxos')
    assert catalog.status_code == 200
    assert catalog.json()['versao'] == '0.5.0'
    assert {x['id'] for x in catalog.json()['fluxos']} == {
        'resumo_documento', 'revisao_contrato', 'pesquisa_documental', 'comparacao_documental'
    }


def test_summary_workflow_persists_task_and_report(isolated):
    doc_id = index_doc('relatorio.txt', 'Relatório financeiro. Receita total R$ 12.500,00. O prazo termina em 30/11/2026.')
    response = client.post('/tarefas', json={
        'fluxo': 'resumo_documento', 'parametros': {'documento_id': doc_id}
    })
    assert response.status_code == 200, response.text
    task = response.json()
    assert task['status'] == 'concluida'
    assert task['resultado']['arquivo'] == 'relatorio.txt'
    assert 'R$ 12.500,00' in task['resultado']['dados_extraidos']['valores']
    assert client.get('/tarefas/' + task['task_id']).json()['task_id'] == task['task_id']
    assert client.get('/tarefas?limite=10').json()[0]['task_id'] == task['task_id']
    report = client.get('/tarefas/' + task['task_id'] + '/relatorio')
    assert report.status_code == 200
    assert '# Relatório de execução do Stanza' in report.text
    assert 'relatorio.txt' in report.text
    assert client.get('/tarefas/inexistente').status_code == 404


def test_contract_review_workflow(isolated):
    doc_id = index_doc('contrato.txt', '''CONTRATO DE SERVIÇOS
CLÁUSULA PRIMEIRA - OBJETO
A contratada prestará serviços de análise documental.
CLÁUSULA SEGUNDA - PAGAMENTO
O pagamento será de R$ 900,00 por mês.
CLÁUSULA TERCEIRA - RESCISÃO
A rescisão poderá ocorrer mediante aviso prévio.''')
    response = client.post('/tarefas', json={
        'fluxo': 'revisao_contrato', 'parametros': {'documento_id': doc_id}
    })
    assert response.status_code == 200
    task = response.json()
    assert task['status'] == 'concluida'
    assert len(task['resultado']['clausulas']) >= 3
    assert task['resultado']['arquivo'] == 'contrato.txt'


def test_search_workflow(isolated):
    doc_id = index_doc('financeiro.txt', 'O faturamento mensal da empresa foi de R$ 4.500,00 no mês analisado.')
    response = client.post('/tarefas', json={
        'fluxo': 'pesquisa_documental',
        'parametros': {'pergunta': 'faturamento mensal', 'documento_id': doc_id, 'modo_busca': 'lexical'},
    })
    assert response.status_code == 200
    task = response.json()
    assert task['status'] == 'concluida'
    assert task['resultado']['metodo'] == 'lexical'
    assert task['resultado']['resultados'][0]['documento_id'] == doc_id


def test_compare_workflow(isolated):
    first = index_doc('versao-a.txt', 'Contrato. Prazo de 12 meses. Pagamento de R$ 500,00.')
    second = index_doc('versao-b.txt', 'Contrato. Prazo de 24 meses. Pagamento de R$ 500,00.')
    response = client.post('/tarefas', json={
        'fluxo': 'comparacao_documental',
        'parametros': {'documento_id': first, 'documento_id_b': second},
    })
    assert response.status_code == 200
    task = response.json()
    assert task['status'] == 'concluida'
    assert task['resultado']['iguais'] is False
    assert any('12 meses' in line for line in task['resultado']['diferencas'])
    assert any('24 meses' in line for line in task['resultado']['diferencas'])


def test_workflow_validation(isolated):
    assert client.post('/tarefas', json={'fluxo': 'inexistente', 'parametros': {}}).status_code == 422
    assert client.post('/tarefas', json={'fluxo': 'resumo_documento', 'parametros': {}}).status_code == 422
    assert client.post('/tarefas', json={
        'fluxo': 'resumo_documento', 'parametros': {'documento_id': 'f' * 64}
    }).status_code == 404
    assert client.post('/tarefas', json={
        'fluxo': 'comparacao_documental', 'parametros': {'documento_id': 'a' * 64, 'documento_id_b': 'a' * 64}
    }).status_code == 404


def test_agent_gateway_requires_token_and_accepts_valid_token(isolated, monkeypatch):
    doc_id = index_doc('gateway.txt', 'Relatório de operação. Total de solicitações: 42.')
    body = {'fluxo': 'resumo_documento', 'parametros': {'documento_id': doc_id}}
    assert client.post('/integracao/tarefas', json=body).status_code == 503
    monkeypatch.setenv('STANZA_INTEGRATION_TOKEN', 'x' * 32)
    assert client.post('/integracao/tarefas', json=body, headers={'X-Stanza-Token': 'wrong'}).status_code == 403
    response = client.post('/integracao/tarefas', json=body, headers={'X-Stanza-Token': 'x' * 32})
    assert response.status_code == 200, response.text
    task = response.json()
    assert task['status'] == 'concluida'
    detail = client.get('/integracao/tarefas/' + task['task_id'], headers={'X-Stanza-Token': 'x' * 32})
    assert detail.status_code == 200
    assert detail.json()['task_id'] == task['task_id']
    assert client.get('/integracao/tarefas/' + task['task_id']).status_code == 401
    events = client.get('/integracao/eventos').json()
    names = [event['evento'] for event in events]
    assert 'agent.workflow.requested' in names
    assert 'workflow.completed' in names


def test_manifest_does_not_expose_integration_secret(isolated, monkeypatch):
    monkeypatch.setenv('STANZA_INTEGRATION_TOKEN', 'private-token-value-' * 2)
    manifest = client.get('/integracao/manifesto').json()
    assert manifest['token_configurado'] is True
    assert 'private-token-value' not in str(manifest)
    assert '/integracao/tarefas' in manifest['rotas']


def test_failed_workflow_is_persisted(isolated, monkeypatch):
    doc_id = index_doc('semantico.txt', 'Documento sobre gestão de arquivos e contratos.')
    monkeypatch.delenv('STANZA_EMBED_MODEL', raising=False)
    response = client.post('/tarefas', json={
        'fluxo': 'pesquisa_documental',
        'parametros': {'pergunta': 'gestão documental', 'documento_id': doc_id, 'modo_busca': 'semantica'},
    })
    assert response.status_code == 200
    task = response.json()
    assert task['status'] == 'falhou'
    assert 'STANZA_EMBED_MODEL' in task['erro']
    assert client.get('/tarefas/' + task['task_id']).json()['status'] == 'falhou'
