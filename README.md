# Stanza v0.2 — ARA OS 12

Agente Python para análise documental com API FastAPI. Suporta PDF com texto selecionável, DOCX e TXT. Processa documentos localmente e permite indexar, pesquisar e localizar evidências por página.

## Instalação no Kali Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
uvicorn stanza.main:app --host 127.0.0.1 --port 8000
```

Abra http://127.0.0.1:8000/docs.

## Endpoints

- `GET /health`: estado do serviço.
- `POST /analisar`: upload de PDF, DOCX ou TXT; classificação, extração e resumo extrativo.
- `POST /comparar`: comparação textual entre arquivos.
- `POST /documentos`: upload e indexação em SQLite.
- `GET /documentos`: lista de documentos indexados.
- `GET /documentos/{id}`: metadados e análise.
- `POST /pesquisar`: pesquisa lexical nos documentos indexados.
- `POST /perguntar`: resposta conservadora baseada em trechos encontrados.

Para `/pesquisar` e `/perguntar`, envie JSON como `{"pergunta":"Qual é o valor do contrato?"}`. Pode incluir `documento_id` retornado em `/documentos`.

## Limitações e segurança

- Esta versão **não** integra um LLM e **não** executa OCR; PDFs escaneados sem camada de texto não são suportados.
- A pesquisa é lexical, não semântica; as respostas retornam evidências, não interpretações geradas por IA.
- Arquivos são limitados a 15 MB; não há autenticação na API. Mantenha o servidor em `127.0.0.1`, nunca exponha diretamente à internet.
- Conteúdo indexado é armazenado em SQLite local, em `~/.stanza/documents.sqlite3` (configurável por `STANZA_DB_PATH`). Proteja o banco caso os documentos sejam confidenciais.
- Não envie documentos pessoais sem verificar permissões e requisitos de privacidade.

## Atualização do GitHub

Copie o conteúdo desta versão sobre a pasta do repositório, preservando `.git/` e `.venv/`, depois execute `git add . && git commit -m "Stanza v0.2" && git push origin main`.
