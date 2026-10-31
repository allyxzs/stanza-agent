# Histórico do Stanza

## 0.3.0
- OCR local em PDFs escaneados, via Tesseract (opt-in/automático e com limites de processamento).
- Novo painel web em `GET /` para indexar e pesquisar documentos.
- Busca avançada com ranking lexical e embeddings semânticos locais opcionais.
- Respostas com IA via API compatível com `chat/completions` quando configurada.
- Resultados de busca com referência ao arquivo e à página.
- Compatibilidade com API e banco SQLite da v0.2, sem migração destrutiva.
- Testes automatizados de OCR, busca, IA simulada, API e retrocompatibilidade.

## 0.2.0
- Armazenamento SQLite, indexação e pesquisa lexical.
- Perguntas baseadas em evidências sem IA generativa.

## 0.1.0
- Leitura de PDF com texto, DOCX e TXT.
- Classificação, extração, resumo e comparação determinísticos.
