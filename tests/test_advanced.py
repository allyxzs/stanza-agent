from stanza import advanced
from stanza.core import parse_document

def test_document_store_and_grounded_question(tmp_path, monkeypatch):
    monkeypatch.setattr(advanced, 'DB_PATH', tmp_path / 'test.sqlite3')
    doc = parse_document('contrato.txt', 'Contrato de prestação de serviços. Valor total R$ 1.200,00. Vigência até 20/12/2026.'.encode())
    saved = advanced.save_document(doc)
    assert saved['id'] == doc.sha256
    assert len(advanced.list_documents()) == 1
    assert advanced.get_document(doc.sha256)['arquivo'] == 'contrato.txt'
    result = advanced.answer('Qual o valor total do contrato?', doc.sha256)
    assert result['fontes'] and '1.200' in result['fontes'][0]['trecho']
    assert advanced.answer('astronautas na lua', doc.sha256)['fontes'] == []
