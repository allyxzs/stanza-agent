# STANZA v0.5 — Agente de Inteligência Documental do ARA OS 12

**Stanza** é um agente Python para leitura, classificação, pesquisa e automação supervisionada de tarefas documentais. A v0.5 preserva as funcionalidades da v0.4 e acrescenta um motor local de fluxos com histórico persistente e um gateway autenticado para solicitações de outros agentes do ARA OS 12.

## Novidades da v0.5

1. **Motor de fluxos documentais:** quatro fluxos prontos — resumo e extração, revisão documental de contrato, pesquisa fundamentada e comparação de versões.
2. **Histórico persistente:** cada execução recebe um identificador, status, parâmetros, resultado, mensagem de erro resumida e horários. O histórico fica no SQLite existente, em uma tabela nova `workflow_tasks`.
3. **Relatório exportável:** cada tarefa pode ser exportada em Markdown.
4. **Gateway ARA OS 12:** outros agentes podem solicitar um fluxo e consultar seu resultado usando o cabeçalho `X-Stanza-Token`. O token é configurado pelo administrador e nunca é retornado pela API.
5. **Eventos de integração:** solicitações, conclusões e falhas são registradas no histórico local.
6. **Painel web:** permite executar os fluxos e consultar as tarefas recentes.

**Importante:** a execução dos fluxos nesta versão é síncrona e local; ainda não existe fila distribuída, execução em segundo plano, webhook ou comunicação automática de saída com outros agentes. O agente cliente inicia a solicitação HTTP. Os endpoints locais antigos continuam disponíveis.

## Fluxos disponíveis

| ID | Entrada | Resultado |
|---|---|---|
| `resumo_documento` | `documento_id` | Classificação, dados extraídos e resumo extrativo |
| `revisao_contrato` | `documento_id` | Cláusulas, temas e sinais para revisão humana com evidências |
| `pesquisa_documental` | `pergunta`, `documento_id` opcional, `modo_busca` | Trechos relevantes com arquivo, página e pontuação |
| `comparacao_documental` | `documento_id`, `documento_id_b` | Diferenças textuais entre dois documentos indexados |

Os documentos devem ser indexados antes da execução. O identificador é o SHA-256 retornado por `POST /documentos`.

## Instalação no Kali Linux

Dependências de sistema (OCR opcional, mas recomendado se trabalhar com PDFs digitalizados):

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip unzip tesseract-ocr tesseract-ocr-por tesseract-ocr-eng
```

Extraia o ZIP e entre na pasta do projeto:

```bash
cd ~/Downloads
unzip stanza_agent_v0.5.zip -d stanza_v05
cd stanza_v05
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
uvicorn stanza.main:app --host 127.0.0.1 --port 8000
```

Painel: **http://127.0.0.1:8000/**  
Documentação da API: **http://127.0.0.1:8000/docs**  
Saúde: **http://127.0.0.1:8000/health**

## Atualizar uma instalação existente da v0.4

Faça backup do projeto e do banco antes de atualizar. O servidor deve estar parado durante o backup/cópia do banco SQLite.

```bash
cd ~/Downloads
unzip stanza_agent_v0.5.zip -d stanza_v05
```

Copie somente código, testes e arquivos de projeto para a pasta já clonada do GitHub. Exemplo, se ela estiver em `~/Downloads/stanza_agent`:

```bash
cp -r ~/Downloads/stanza_v05/stanza ~/Downloads/stanza_v05/tests ~/Downloads/stanza_agent/
cp ~/Downloads/stanza_v05/README.md ~/Downloads/stanza_v05/CHANGELOG.md \
   ~/Downloads/stanza_v05/requirements.txt ~/Downloads/stanza_v05/requirements-semantic.txt \
   ~/Downloads/stanza_v05/.gitignore ~/Downloads/stanza_v05/.env.example \
   ~/Downloads/stanza_agent/
cd ~/Downloads/stanza_agent
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
```

**Não copie** `.git/`, `.venv/`, o banco SQLite, `.env` nem documentos particulares. A atualização cria a tabela `workflow_tasks` automaticamente e não apaga tabelas ou documentos antigos.

## Testar os fluxos pela API

Primeiro, indexe um arquivo:

```bash
curl -F 'arquivo=@contrato.pdf' http://127.0.0.1:8000/documentos
```

Copie o campo `id` (SHA-256) da resposta. Consulte os fluxos:

```bash
curl http://127.0.0.1:8000/fluxos
```

Executar resumo:

```bash
curl -X POST http://127.0.0.1:8000/tarefas \
  -H 'Content-Type: application/json' \
  -d '{"fluxo":"resumo_documento","parametros":{"documento_id":"COLE_O_SHA256_AQUI"}}'
```

Executar revisão de contrato:

```bash
curl -X POST http://127.0.0.1:8000/tarefas \
  -H 'Content-Type: application/json' \
  -d '{"fluxo":"revisao_contrato","parametros":{"documento_id":"COLE_O_SHA256_AQUI"}}'
```

Pesquisar nos documentos indexados:

```bash
curl -X POST http://127.0.0.1:8000/tarefas \
  -H 'Content-Type: application/json' \
  -d '{"fluxo":"pesquisa_documental","parametros":{"pergunta":"Qual é o prazo de vigência?","modo_busca":"lexical"}}'
```

Comparar duas versões:

```bash
curl -X POST http://127.0.0.1:8000/tarefas \
  -H 'Content-Type: application/json' \
  -d '{"fluxo":"comparacao_documental","parametros":{"documento_id":"SHA256_A","documento_id_b":"SHA256_B"}}'
```

Consultar tarefas e relatório:

```bash
curl 'http://127.0.0.1:8000/tarefas?limite=30'
curl http://127.0.0.1:8000/tarefas/ID_DA_TAREFA
curl -OJ http://127.0.0.1:8000/tarefas/ID_DA_TAREFA/relatorio
```

## Integração autenticada com outros agentes ARA OS 12

A integração entre agentes fica desativada até o administrador definir um segredo compartilhado com pelo menos 24 caracteres. Gere um segredo aleatório no Kali:

```bash
openssl rand -hex 32
```

Configure-o no mesmo terminal em que iniciará o servidor (use o mesmo valor no agente cliente):

```bash
export STANZA_INTEGRATION_TOKEN='COLE_AQUI_O_SEGREDO_GERADO'
uvicorn stanza.main:app --host 127.0.0.1 --port 8000
```

Não publique esse segredo no GitHub, README, prints ou mensagens. Para uso persistente, utilize um gerenciador de segredos ou um arquivo de ambiente fora do repositório, com permissões restritas.

Solicitar fluxo a partir de outro agente:

```bash
curl -X POST http://127.0.0.1:8000/integracao/tarefas \
  -H 'Content-Type: application/json' \
  -H "X-Stanza-Token: $STANZA_INTEGRATION_TOKEN" \
  -d '{"fluxo":"resumo_documento","parametros":{"documento_id":"COLE_O_SHA256_AQUI"}}'
```

Consultar a tarefa com o mesmo cabeçalho:

```bash
curl http://127.0.0.1:8000/integracao/tarefas/ID_DA_TAREFA \
  -H "X-Stanza-Token: $STANZA_INTEGRATION_TOKEN"
```

Rotas de integração:

- `GET /integracao/manifesto` — capacidades, rotas e indicação se o token está configurado (nunca revela o segredo).
- `GET /integracao/eventos` — histórico local de eventos.
- `POST /integracao/tarefas` — solicitação autenticada de fluxo.
- `GET /integracao/tarefas/{task_id}` — consulta autenticada de execução.

A autenticação é um token compartilhado simples para ambiente local/confiável. Não exponha o servidor à internet. Para uma instalação multiusuário ou em rede, adicione TLS, gestão individual de identidades, autorização por agente, rotação de segredo, rate limiting e auditoria centralizada.

## Endpoints principais

| Método | Rota | Função |
|---|---|---|
| GET | `/` | Painel web |
| GET | `/health` | Estado e recursos configurados |
| GET | `/fluxos` | Catálogo de fluxos |
| POST | `/tarefas` | Executa fluxo local e registra histórico |
| GET | `/tarefas` | Lista tarefas recentes |
| GET | `/tarefas/{task_id}` | Detalha uma tarefa |
| GET | `/tarefas/{task_id}/relatorio` | Exporta relatório Markdown |
| POST | `/integracao/tarefas` | Cria tarefa por agente autenticado |
| GET | `/integracao/tarefas/{task_id}` | Consulta autenticada da tarefa |
| POST | `/documentos` | Indexa documento |
| GET | `/documentos` | Lista documentos |
| POST | `/busca-avancada` | Pesquisa lexical ou semântica |
| POST | `/responder-ia` | Resposta com IA externa opcional |
| POST | `/contratos/analisar` | Análise heurística de contrato |
| GET | `/duplicatas` | Relatório de duplicatas |
| POST | `/organizacao/prever` | Prévia de organização |
| POST | `/organizacao/aplicar` | Cópia após confirmação explícita |

Os endpoints anteriores da v0.4 permanecem disponíveis; consulte `/docs` para a lista completa.

## Recursos herdados e opcionais

- **OCR local:** Tesseract (`tesseract-ocr`, `tesseract-ocr-por`, `tesseract-ocr-eng`).
- **IA externa opcional:** configure `STANZA_LLM_API_KEY`, `STANZA_LLM_MODEL` e, se necessário, `STANZA_LLM_BASE_URL`. Os trechos recuperados serão enviados ao provedor configurado somente ao chamar `/responder-ia`.
- **Busca semântica opcional:** `pip install -r requirements-semantic.txt` e `STANZA_EMBED_MODEL`. O modelo pode ser baixado na primeira utilização.
- **Organização por cópia:** configure `STANZA_ORGANIZE_ROOT`; veja a documentação da v0.4 ou `/docs`. Os arquivos originais não são apagados.

## Limitações e segurança

- Os fluxos são síncronos e executados no processo da API. Não há worker, fila distribuída, agendamento ou retry automático.
- O histórico de tarefas pode conter trechos recuperados ou resultados derivados dos documentos. Restrinja o acesso ao SQLite (`~/.stanza/documents.sqlite3` por padrão).
- A API local não possui login de usuário. Use apenas `127.0.0.1`; não use `--host 0.0.0.0` nem exponha a porta publicamente.
- O gateway de agentes exige token, mas token compartilhado não substitui identidade individual, TLS e autorização granular.
- Documentos são dados não confiáveis; nunca execute instruções encontradas neles. Respostas de IA e análises heurísticas exigem revisão humana.
- A análise contratual não é parecer jurídico e pode deixar de detectar cláusulas ou sinalizar falsos positivos.
- Formatos aceitos: PDF, DOCX e TXT; upload máximo de 15 MB, até 120 páginas de PDF e 25 páginas de OCR.

## Testes

```bash
python -m pytest -q
```

A suíte v0.5 cobre regressão das versões anteriores, persistência de tarefas, quatro fluxos, exportação Markdown e autenticação do gateway.

**Versão:** 0.5.0 · **Agente:** Stanza · **Sistema:** ARA OS 12
