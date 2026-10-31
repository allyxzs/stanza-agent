# STANZA v0.4 — Agente de Inteligência Documental do ARA OS 12

**Projeto Python executável.** A v0.4 evolui diretamente da v0.3, mantém o painel e todos os endpoints anteriores e preserva o banco SQLite existente. Não requer chave de IA para classificação, OCR local, duplicatas, organização nem análise heurística de cláusulas.

> **Limites:** não é um serviço multiusuário nem um parecer jurídico. A API não tem autenticação: execute **somente em `127.0.0.1`**. Não publique a porta 8000 na internet. Dados de documentos ficam no SQLite local; IA externa, quando habilitada, envia trechos selecionados à API configurada.

## Novidades da v0.4

1. **Organização segura de arquivos** — uma prévia (sem alterações) com classificação por tipo e ano, seguida de confirmação explícita. Copia arquivos de `entrada/` para `organizados/categoria/ano/`; **nunca exclui, move, nem sobrescreve os originais**. Bloqueia symlinks e verifica SHA-256 antes de aplicar. Por segurança, a pasta autorizada deve ser configurada pelo administrador via variável de ambiente.
2. **Detecção de duplicatas** — identifica reenvios idênticos por SHA-256, registra eventos de novas importações na v0.4 e compara similaridade textual aproximada entre documentos distintos. Não exclui arquivos nem decide automaticamente que documentos semelhantes são equivalentes.
3. **Análise de cláusulas contratuais** — localiza títulos de cláusulas, identifica temas como pagamento, rescisão e confidencialidade e marca trechos que merecem revisão humana, sempre mostrando página e evidência. Regras heurísticas podem perder cláusulas ou produzir falsos positivos.
4. **Integração inicial com ARA OS 12** — manifesto de capacidades e log de eventos somente no SQLite local (`document.indexed`, `document.organized`, `contract.reviewed`). **Ainda não há comunicação automática com outros agentes**.
5. **Painel web atualizado** — interface para indexar, pesquisar, listar duplicatas, analisar cláusulas, pré-visualizar/copiar arquivos e consultar eventos locais.

Continuam disponíveis: leitura PDF/DOCX/TXT, OCR Tesseract (com limites), classificação e extração, resumos extrativos, comparação, busca lexical/semântica opcional e respostas com IA externa opcional.

## Instalação no Kali Linux

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip unzip tesseract-ocr tesseract-ocr-por tesseract-ocr-eng
cd ~/Downloads/stanza_agent
python3 -m venv .venv  # somente se ainda não existir
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
uvicorn stanza.main:app --host 127.0.0.1 --port 8000
```

Navegador: **http://127.0.0.1:8000/**. API interativa: **http://127.0.0.1:8000/docs**.

## Atualizar do Stanza v0.3 sem perder Git e banco

Antes de fazer alterações, confirme se não há rebase ativo (`git status`) e sincronize com o remoto quando seu diretório estiver limpo (`git pull --rebase origin main`). **Se houver conflitos, resolva-os antes de continuar**.

Faça backup do repositório e, se houver, do banco SQLite. No Linux, o banco padrão fica em `~/.stanza/documents.sqlite3`; com SQLite em WAL, pare o servidor antes de copiar o banco.

Baixe `stanza_agent_v0.4.zip` para `~/Downloads`. Em seguida:

```bash
cd ~/Downloads
unzip -o stanza_agent_v0.4.zip -d stanza_v04
# Copie SOMENTE o código e os arquivos de configuração/documentação.
cp -r stanza_v04/stanza stanza_v04/tests stanza_agent/
cp stanza_v04/README.md stanza_v04/CHANGELOG.md stanza_v04/requirements.txt \
   stanza_v04/requirements-semantic.txt stanza_v04/.gitignore stanza_v04/.env.example stanza_agent/
cd stanza_agent
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
```

**Não copie** `.git/`, `.venv/`, o SQLite ou arquivos pessoais entre os projetos.

Se seu Git antigo incluiu arquivos compilados `.pyc`, remova-os **apenas do índice** antes do commit:

```bash
git ls-files -z | grep -zE '(^|/)__pycache__/|\.pyc$' | xargs -0 -r git rm --cached --
git add .
git status
# Confira a lista: não publique .env, documentos privados nem seu banco de dados.
git commit -m "Stanza v0.4 - Organizacao, Duplicatas e Contratos"
git push origin main
```

Se o `push` indicar `fetch first`, execute `git pull --rebase origin main`, resolva qualquer conflito e tente de novo. **Não use `git push --force`.**

## Configurar a organização (recurso opcional)

O administrador escolhe uma pasta real de trabalho. Exemplo:

```bash
mkdir -p "$HOME/Documentos/Stanza/entrada"
export STANZA_ORGANIZE_ROOT="$HOME/Documentos/Stanza"
```

Coloque arquivos `.pdf`, `.docx` ou `.txt` dentro de `~/Documentos/Stanza/entrada/`. Reinicie o servidor **no mesmo terminal em que exportou a variável**:

```bash
uvicorn stanza.main:app --host 127.0.0.1 --port 8000
```

1. No painel, clique **Gerar prévia segura**, ou `POST /organizacao/prever`.
2. Confira a lista de arquivos e categorias. A prévia não copia ou altera nada.
3. Clique **Confirmar e copiar arquivos** (ou `POST /organizacao/aplicar` com `{"plano_id":"...","confirmar":true}`).
4. Os arquivos são copiados para `organizados/<categoria>/<ano>/<nome>`, usando o ano de modificação do arquivo, não a data contratual.

**Regras de proteção:** raiz fixa por variável de ambiente; planos temporários de uso único, validade de 15 minutos; sem links simbólicos; limite de 100 arquivos por prévia e 15 MB por arquivo; verificação SHA-256 dos originais; recusa sobrescrever destinos; arquivos originais mantidos. Reiniciar o servidor invalida prévias pendentes. Em falhas de disco durante um lote, algumas cópias podem estar concluídas: confira a pasta de saída e gere nova prévia.

**Observação:** na organização, a classificação de PDFs digitalizados sem camada textual não usa OCR (para evitar processamento massivo). O OCR permanece disponível ao indexar ou analisar documentos; arquivos sem texto extraível vão para `nao_classificados`.

## Detecção de duplicatas

```bash
# Indexar o mesmo conteúdo com dois nomes registra duas ocorrências na v0.4
curl -F 'arquivo=@contrato.pdf' 'http://127.0.0.1:8000/documentos'
curl 'http://127.0.0.1:8000/duplicatas'
# Consultar duplicatas antes de indexar um arquivo
curl -F 'arquivo=@contrato.pdf' 'http://127.0.0.1:8000/duplicatas/verificar'
```

- Duplicata exata: SHA-256 igual; conteúdo binário idêntico.
- Possível semelhante: sobreposição de trigramas de palavras normalizadas; compara até 100 documentos e usa limiar padrão 0,78. Semelhança não é identidade.
- O histórico de importações **começa na v0.4**. Documentos indexados antes dela são preservados, mas suas antigas ocorrências de reenvio não podem ser reconstruídas.

## Cláusulas contratuais

```bash
curl -F 'arquivo=@contrato.pdf' 'http://127.0.0.1:8000/contratos/analisar'
# Para documento já indexado:
curl 'http://127.0.0.1:8000/documentos/ID_SHA256/clausulas'
```

Cada cláusula detectada retorna título, assunto provável, trecho literal e número da página. Sinais de renovação automática, multa, rescisão e dados pessoais vêm com evidências. Uma cláusula atravessando páginas pode ficar incompleta. **Não substitui análise de advogado**.

## Integração ARA OS 12 (local, passiva)

```bash
curl http://127.0.0.1:8000/integracao/manifesto
curl http://127.0.0.1:8000/integracao/eventos
```

O manifesto especifica tipos de eventos; o log local guarda apenas metadados (hash, nome do arquivo, contagens). **Não existem webhooks, fila remota ou comunicação direta com outros agentes nesta versão**. A integração externa precisará de autenticação, autorização por agente e controle de acesso antes da exposição em rede.

## Recursos opcionais herdados da v0.3

**OCR:** `sudo apt install tesseract-ocr tesseract-ocr-por tesseract-ocr-eng`.

**Modelo de IA externo compatível com Chat Completions:**

```bash
export STANZA_LLM_API_KEY='sua-chave-privada'  # Nunca coloque no GitHub
export STANZA_LLM_MODEL='nome-do-modelo-da-sua-conta'
# Opcional: export STANZA_LLM_BASE_URL='https://api.openai.com/v1'
```

O modelo não é embutido no ZIP. Só faz chamadas externas quando `/responder-ia` é usado e a configuração existe. Trechos de documentos são enviados ao provedor selecionado.

**Embeddings locais opcionais:**

```bash
python -m pip install -r requirements-semantic.txt
export STANZA_EMBED_MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
```

Na primeira utilização, o modelo poderá ser baixado da internet. Sem ele, a pesquisa usa ranking lexical local.

## Endpoints

| Verbo | Rota | Função |
|---|---|---|
| GET | `/` | Painel local v0.4 |
| GET | `/health` | Saúde e capacidades |
| POST | `/analisar` | Análise determinística com OCR opcional |
| POST | `/comparar` | Comparação textual |
| POST | `/documentos` | Indexa e registra cada importação |
| GET | `/documentos` | Lista até 200 documentos |
| GET | `/documentos/{id}` | Metadados de um documento |
| POST | `/pesquisar` | Busca lexical legada |
| POST | `/perguntar` | Evidências legadas sem IA |
| POST | `/busca-avancada` | Busca lexical ou semântica opcional |
| POST | `/responder-ia` | Resposta via provedor de IA externo opcional |
| GET | `/duplicatas` | Relatório de exatas e possíveis semelhantes |
| POST | `/duplicatas/verificar` | Verifica arquivo sem indexá-lo |
| POST | `/contratos/analisar` | Identifica cláusulas e sinais em upload |
| GET | `/documentos/{id}/clausulas` | Identifica cláusulas de documento indexado |
| POST | `/organizacao/prever` | Prévia sem alterações |
| POST | `/organizacao/aplicar` | Copia apenas após confirmação do plano |
| GET | `/integracao/manifesto` | Contrato de integração local |
| GET | `/integracao/eventos` | Histórico dos eventos registrados |

## Armazenamento, privacidade e limites

- Banco padrão: `~/.stanza/documents.sqlite3`, alterável por `STANZA_DB_PATH`. Tabelas novas são criadas aditivamente no banco existente.
- O banco contém texto integral de documentos indexados e precisa de backup e controle de acesso de arquivos.
- Extensões: PDF, DOCX, TXT. Upload máximo 15 MB; até 120 páginas de PDF e 25 páginas de OCR por arquivo. Arquivos corrompidos ou sem texto reconhecível são rejeitados.
- O Stanza não executa instruções encontradas nos documentos. IA externa recebe instruções para tratar o texto como dados não confiáveis; ainda assim, resultados gerados por IA precisam de revisão.
- Esta versão não tem autenticação nem permissões por usuário; não execute com bind `0.0.0.0`, não exponha internet, e evite armazenar documentos de terceiros sem autorização.
- Testes: `python -m pytest -q`.

**Versão:** 0.4.0 · **Agente:** Stanza · **Sistema:** ARA OS 12
