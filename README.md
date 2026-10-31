# STANZA v0.3 — Agente documental do ARA OS 12

Projeto Python **executável**, baseado na v0.2, que inclui OCR para PDFs escaneados, busca avançada, integração opcional a modelos de IA compatíveis com `/chat/completions` e painel web local. O Stanza mantém os endpoints anteriores e reutiliza o banco SQLite da v0.2.

## Instalar no Kali Linux

```bash
sudo apt update
sudo apt install -y python3-venv tesseract-ocr tesseract-ocr-por tesseract-ocr-eng
cd ~/Downloads/stanza_agent
source .venv/bin/activate              # se já tem a v0.2 instalada
python -m pip install -r requirements.txt
python -m pytest -q
uvicorn stanza.main:app --host 127.0.0.1 --port 8000
```

- **Painel web:** http://127.0.0.1:8000/
- **Documentação da API:** http://127.0.0.1:8000/docs
- **Status:** http://127.0.0.1:8000/health

Se não tiver `.venv`, crie com `python3 -m venv .venv` e ative com `source .venv/bin/activate`.

## O que mudou

- **OCR integrado (opcional):** ao ler um PDF com página sem texto, chama o binário local `tesseract`, sem enviar dados à internet. Precisa dos pacotes `tesseract-ocr` e idioma(s) instalados. Query param `ocr=auto|sim|nao`. Máximo de 25 páginas OCR por arquivo, 120 páginas totais e 15 MB de upload.
- **`POST /busca-avancada`:** ranking lexical melhorado por trechos, com indicação de arquivo e página. Pode usar embeddings locais de `sentence-transformers` quando configurados.
- **`POST /responder-ia`:** consulta opcional a uma API externa de modelo de linguagem, com até cinco fontes de evidências e instruções para não inventar fatos. Precisa configurar chave e modelo. **Trechos de documentos serão enviados ao provedor externo** quando este recurso for usado.
- **`GET /`:** interface web local para indexar documentos, fazer perguntas e visualizar fontes.
- **Compatibilidade:** mantém `/health`, `/analisar`, `/comparar`, `/documentos`, `/pesquisar` e `/perguntar` com suas funções anteriores.

## Uso da IA (opcional)

Nenhuma chave é necessária para OCR, análise, indexação, busca lexical ou interface. Para habilitar `/responder-ia` configure no terminal antes de iniciar o servidor:

```bash
export STANZA_LLM_API_KEY='SUA_CHAVE_AQUI'
export STANZA_LLM_MODEL='NOME_DO_MODELO_DISPONIVEL_NA_SUA_CONTA'
# opcional: endereço de uma API compatível com /chat/completions
export STANZA_LLM_BASE_URL='https://api.openai.com/v1'
```

Esses são exemplos de parâmetros; escolha um modelo realmente disponível em seu provedor. Não inclua chaves no Git. Caso a API não esteja configurada, `/responder-ia` devolve HTTP 503, sem prejudicar a busca local.

## Busca semântica local (opcional)

Por padrão, a busca avançada é **lexical**. Para ativar a busca semântica **de verdade**, instale a dependência extra e selecione um modelo de embeddings multilingual:

```bash
python -m pip install -r requirements-semantic.txt
export STANZA_EMBED_MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
```

Na primeira execução, o modelo pode baixar arquivos da internet; depois será carregado do cache local. Instalar `sentence-transformers` é opcional e consome mais espaço/RAM. Quando habilitado, o modo `auto` usa embeddings; `modo=lexical` força a busca lexical. Se solicitar `modo=semantica` sem configurar modelo, receberá HTTP 503.

## Exemplos de API

Indexar um arquivo:

```bash
curl -F 'arquivo=@contrato.pdf' 'http://127.0.0.1:8000/documentos'
```

Buscar evidências:

```bash
curl -H 'Content-Type: application/json' -d '{"pergunta":"Qual o valor do contrato?"}' \
  'http://127.0.0.1:8000/busca-avancada?modo=lexical'
```

Perguntar ao modelo de IA, caso esteja habilitado:

```bash
curl -H 'Content-Type: application/json' -d '{"pergunta":"Qual o valor do contrato?"}' \
  'http://127.0.0.1:8000/responder-ia'
```

Os resultados da IA podem errar; verifique as evidências fornecidas. Não use as respostas como parecer jurídico.

## Banco de dados e privacidade

O banco padrão é `~/.stanza/documents.sqlite3`, configurável por `STANZA_DB_PATH`. O banco da v0.2 é reaproveitado. Os **textos completos dos documentos** ficam no SQLite local; faça backup antes de atualizar e controle permissões de leitura. A API não possui login ou controle de usuários: **mantenha o bind em `127.0.0.1`**. Não abra a porta 8000 em interfaces públicas. Não compartilhe banco de dados, tokens e documentos confidenciais no repositório.

Arquivos PDF escaneados exigem OCR instalado; PDFs muito extensos podem ser rejeitados por limite de processamento. Classificação e extração ainda usam heurísticas, não interpretação jurídica especializada. A busca semântica pode trazer aproximações incorretas, e o modelo de IA externo não garante ausência de alucinações.

## Atualizar a v0.2 no repositório existente

1. **Faça backup** da pasta do projeto e do banco `~/.stanza/documents.sqlite3`.
2. Extraia o ZIP da v0.3 em uma pasta temporária e copie `stanza/`, `tests/`, `README.md`, `.gitignore`, `requirements.txt`, `requirements-semantic.txt` e `.env.example` sobre a pasta do projeto; **não copie nem substitua `.git/`, `.venv/` nem o banco SQLite**.
3. Instale requisitos e rode os testes antes de publicar.
4. Se já houver arquivos `__pycache__`/`*.pyc` versionados acidentalmente na v0.2, remova-os apenas do índice:

```bash
git ls-files -z | grep -zE '(^|/)__pycache__/|\.pyc$' | xargs -0 -r git rm --cached --
git add .
git status
git commit -m 'Stanza v0.3 - OCR, busca avançada e IA opcional'
git pull --rebase origin main
git push origin main
```

Se o `git pull --rebase` produzir conflitos, resolva-os antes de executar o `git push`; **não use `--force`**.

## Endpoints

| Método | Endpoint | Função |
| --- | --- | --- |
| GET | `/` | Painel web local |
| GET | `/health` | Estado das funções OCR, IA e embeddings |
| POST | `/analisar` | Extrai e analisa PDF/DOCX/TXT com OCR opcional |
| POST | `/comparar` | Diferenças textuais entre dois documentos |
| POST | `/documentos` | Indexa e persiste no SQLite |
| GET | `/documentos` | Lista arquivos indexados |
| GET | `/documentos/{id}` | Consulta metadados sem devolver o texto completo |
| POST | `/pesquisar` | Busca lexical da v0.2 (compatibilidade) |
| POST | `/perguntar` | Evidências conservadoras da v0.2 (compatibilidade) |
| POST | `/busca-avancada` | Busca lexical ou semântica com fontes |
| POST | `/responder-ia` | Resposta gerada com fontes, exige API configurada |

## Testes

```bash
python -m pytest -q
```

**Versão:** 0.3.0 · **Projeto:** ARA OS 12 · **Agente:** Stanza
