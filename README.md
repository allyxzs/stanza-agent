# Stanza v0.1 — ARA OS 12

Protótipo funcional de inteligência documental **local**, sem necessidade de chave de API.

## Iniciar

Requer Python 3.10+ (recomendado 3.12).

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn stanza.main:app --reload
```

Acesse http://127.0.0.1:8000/docs para testar upload e comparação.

## Testar

```bash
pytest -q
```

## Exemplos

```bash
curl -F 'arquivo=@contrato.pdf' 'http://127.0.0.1:8000/analisar?frases=5'
curl -F 'original=@antigo.docx' -F 'atualizado=@novo.docx' http://127.0.0.1:8000/comparar
```

## Limites e segurança

- PDF, DOCX e TXT até 15 MB. Não há OCR para PDFs escaneados.
- Classificação por palavras-chave e resumo **extrativo**: não é um LLM e não garante interpretação jurídica ou precisão semântica.
- Não salva nem altera arquivos enviados; uploads são processados em memória.
- Não possui autenticação, rate limiting ou armazenamento persistente. **Não exponha na internet sem adicionar essas proteções.**
- CNPJ é reconhecido pelo formato, não validado pelo dígito verificador.
- Diferenças são textuais, não estruturais ou visuais.
