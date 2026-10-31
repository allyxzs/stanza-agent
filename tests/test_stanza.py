from fastapi.testclient import TestClient
from stanza.main import app
from stanza.core import parse_document, analyze

client = TestClient(app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_analysis():
    data = b"Contrato entre contratante e contratada.\nValor R$ 1.500,00 em 12/10/2026.\nA clausula trata da vigencia contratual."
    response = client.post("/analisar", files={"arquivo": ("contrato.txt", data, "text/plain")})
    assert response.status_code == 200
    payload = response.json()
    assert payload["classificacao"]["categoria"] == "contrato"
    assert "12/10/2026" in payload["dados"]["datas"]


def test_bad_extension():
    response = client.post("/analisar", files={"arquivo": ("a.exe", b"abc")})
    assert response.status_code == 422


def test_compare():
    response = client.post("/comparar", files={"original": ("a.txt", b"Primeira versao"), "atualizado": ("b.txt", b"Segunda versao")})
    assert response.status_code == 200
    assert response.json()["iguais"] is False
