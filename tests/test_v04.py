"""Regressão v0.4 — usa SQLite isolado e não envia dados para a rede."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from stanza import advanced
from stanza.core import parse_document
from stanza.main import app

client = TestClient(app)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(advanced, 'DB_PATH', tmp_path / 'db.sqlite3')
    monkeypatch.delenv('STANZA_ORGANIZE_ROOT', raising=False)
    return tmp_path


def test_health_and_legacy(isolated):
    assert client.get('/health').json()['versao'] == '0.5.0'
    r = client.post('/analisar', files={'arquivo': ('a.txt', b'Contrato. Contratante e contratada. Valor R$ 500,00.')})
    assert r.status_code == 200
    assert r.json()['classificacao']['categoria'] == 'contrato'
    assert client.post('/organizacao/prever').status_code == 503


def test_exact_duplicate_uploads_and_events(isolated):
    content = 'Contrato de prestação de serviços. Cláusula 1 - Objeto\nO prazo é de 30 dias.'.encode()
    first = client.post('/documentos', files={'arquivo': ('contrato.txt', content)})
    assert first.status_code == 200
    assert first.json()['duplicado'] is False
    second = client.post('/documentos', files={'arquivo': ('contrato_2.txt', content)})
    assert second.status_code == 200
    assert second.json()['duplicado'] is True
    assert first.json()['id'] == second.json()['id']
    report = client.get('/duplicatas').json()
    assert len(report['duplicatas_exatas']) == 1
    assert set(report['duplicatas_exatas'][0]['nomes']) == {'contrato.txt', 'contrato_2.txt'}
    assert len(client.get('/documentos').json()) == 1
    events = client.get('/integracao/eventos').json()
    assert len(events) == 2 and events[0]['evento'] == 'document.indexed'
    assert client.get('/integracao/manifesto').json()['agente'] == 'Stanza'


def test_preexisting_v03_document_recognized(isolated):
    doc = parse_document('original.txt', b'Contrato com objeto e pagamento por transferencia.')
    advanced.save_document(doc)  # simulando ingestão antiga
    new = client.post('/documentos', files={'arquivo': ('copiado.txt', b'Contrato com objeto e pagamento por transferencia.')})
    assert new.status_code == 200
    assert new.json()['duplicado'] is True
    # Antigos eventos não aparecem artificialmente na contagem.
    assert new.json()['ocorrencias_registradas_v04'] == 1


def test_precheck_duplicates_without_indexing(isolated):
    content = b'Acordo importante entre empresas de consultoria.\nO objeto principal envolve levantamento de dados financeiros e analise de contratos.'
    client.post('/documentos', files={'arquivo':('A.txt',content)})
    response = client.post('/duplicatas/verificar', files={'arquivo':('B.txt',content)})
    assert response.status_code == 200 and response.json()['duplicata_exata']
    assert len(client.get('/documentos').json()) == 1


def test_similar_documents(isolated):
    base = ('Este contrato possui um conjunto de palavras relevantes para comparacao de duplicatas. '
            'A analise vai comparar contratos e organizar de forma automatica sem substituir arquivos. '
            'Valores da operacao e prazo de vigencia previstos na proposta. ')
    for name, text in [('a.txt',base + 'Final original.'), ('b.txt',base + 'Final revisado.')]:
        response = client.post('/documentos', files={'arquivo':(name,text.encode())})
        assert response.status_code == 200
    report = client.get('/duplicatas?limiar=0.65').json()
    assert len(report['possiveis_semelhantes']) == 1
    assert report['possiveis_semelhantes'][0]['similaridade_textual'] >= 0.65
    assert client.get('/duplicatas?limiar=0.1').status_code == 422


def test_contract_clauses_and_alerts(isolated):
    raw = '''CONTRATO DE PRESTAÇÃO DE SERVIÇOS
CLÁUSULA PRIMEIRA - OBJETO
A contratada fará análise de documentos.
CLÁUSULA SEGUNDA - PAGAMENTO
O preço é R$ 2.000,00 até 20/11/2026.
CLÁUSULA TERCEIRA - RENOVAÇÃO
Haverá renovação automática salvo aviso prévio.
CLÁUSULA QUARTA - RESCISÃO
A multa por rescisão será de R$ 200,00.
'''.encode()
    result = client.post('/contratos/analisar', files={'arquivo':('contrato.txt',raw)})
    assert result.status_code == 200, result.text
    data = result.json()
    assert len(data['clausulas']) == 4
    assert {'objeto', 'pagamento', 'renovacao', 'rescisao'} <= {x['tipo'] for x in data['clausulas']}
    assert {'renovacao_automatica','multa'} <= {x['codigo'] for x in data['sinais_para_revisao']}
    assert data['clausulas'][1]['pagina'] == 1
    assert 'R$ 2.000' in data['campos_extraidos']['valores'][0]
    doc_id = client.post('/documentos', files={'arquivo':('contrato.txt',raw)}).json()['id']
    assert len(client.get(f'/documentos/{doc_id}/clausulas').json()['clausulas']) == 4
    assert client.get('/documentos/invalid/clausulas').status_code == 404


def test_organize_requires_permission_and_copy_only(isolated, monkeypatch):
    root = isolated / 'stanza-organizacao'
    incoming = root / 'entrada'
    incoming.mkdir(parents=True)
    (incoming / 'contrato.txt').write_text('Contrato entre contratante e contratada. Vigência até 31/12/2026.', encoding='utf-8')
    monkeypatch.setenv('STANZA_ORGANIZE_ROOT', str(root))
    preview = client.post('/organizacao/prever')
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data['copias_propostas'] == 1
    target = root / 'organizados' / data['acoes'][0]['destino']
    assert not target.exists()
    assert client.post('/organizacao/aplicar', json={'plano_id':data['plano_id'], 'confirmar':False}).status_code == 409
    result = client.post('/organizacao/aplicar', json={'plano_id':data['plano_id'], 'confirmar':True})
    assert result.status_code == 200, result.text
    assert target.read_text(encoding='utf-8') == (incoming / 'contrato.txt').read_text(encoding='utf-8')
    assert (incoming / 'contrato.txt').exists()
    assert client.post('/organizacao/aplicar', json={'plano_id':data['plano_id'], 'confirmar':True}).status_code == 404
    again = client.post('/organizacao/prever').json()
    assert again['copias_propostas'] == 0
    assert again['acoes'][0]['acao'] == 'ja_organizado'
    assert any(x['evento'] == 'document.organized' for x in client.get('/integracao/eventos').json())


def test_organizer_rejects_changes_after_preview(isolated, monkeypatch):
    root = isolated / 'root'
    root.joinpath('entrada').mkdir(parents=True)
    origin = root/'entrada'/'contrato.txt'
    origin.write_text('Contrato inicial com cláusula sobre valores')
    monkeypatch.setenv('STANZA_ORGANIZE_ROOT', str(root))
    preview = client.post('/organizacao/prever').json()
    origin.write_text('CONTRATO MODIFICADO')
    assert client.post('/organizacao/aplicar', json={'plano_id':preview['plano_id'],'confirmar':True}).status_code == 409
    assert not root.joinpath('organizados').exists()


def test_organizer_avoids_symlink_files(isolated, monkeypatch):
    root = isolated / 'safe'
    root.joinpath('entrada').mkdir(parents=True)
    outside = isolated / 'outside.txt'
    outside.write_text('Conteúdo de fora')
    (root/'entrada'/'link.txt').symlink_to(outside)
    monkeypatch.setenv('STANZA_ORGANIZE_ROOT', str(root))
    data = client.post('/organizacao/prever').json()
    assert data['acoes'] == []


def test_organizer_rejects_external_symlink_destination(isolated, monkeypatch):
    root = isolated / 'safe'
    root.joinpath('entrada').mkdir(parents=True)
    (root/'entrada'/'contrato.txt').write_text('Contrato entre partes')
    outside = isolated / 'outside'
    outside.mkdir()
    (root/'organizados').symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv('STANZA_ORGANIZE_ROOT', str(root))
    r = client.post('/organizacao/prever')
    assert r.status_code == 422
    assert list(outside.iterdir()) == []


def test_organizer_requires_existing_root(isolated, monkeypatch):
    monkeypatch.setenv('STANZA_ORGANIZE_ROOT', str(isolated/'not-created'))
    assert client.post('/organizacao/prever').status_code == 422


def test_organizer_multiple_same_names_different_content(isolated, monkeypatch):
    root = isolated/'root'
    for folder, content in [('a','Contrato entre contratante e contratada, parcela A.'),
                            ('b','Contrato entre contratante e contratada, parcela B.')]:
        directory = root/'entrada'/folder
        directory.mkdir(parents=True)
        (directory/'contrato.txt').write_text(content)
    monkeypatch.setenv('STANZA_ORGANIZE_ROOT', str(root))
    preview = client.post('/organizacao/prever').json()
    assert preview['copias_propostas'] == 2
    targets = [entry['destino'] for entry in preview['acoes']]
    assert len(set(targets)) == 2
    result = client.post('/organizacao/aplicar', json={'plano_id':preview['plano_id'], 'confirmar':True})
    assert result.status_code == 200, result.text
    assert result.json()['quantidade_copiada'] == 2
    assert len(list((root/'organizados'/'contrato').rglob('*.txt'))) == 2


def test_web_panel_v04(isolated):
    response = client.get('/')
    assert response.status_code == 200
    for name in ['STANZA', 'v0.5', 'Duplicatas', 'Revisão contratual', 'Organizar arquivos', 'Fluxos e tarefas']:
        assert name in response.text
