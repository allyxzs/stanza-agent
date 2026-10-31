# Histórico do Stanza

## 0.4.0
- Planejamento e aplicação de organização por cópia, com autorização explícita, SHA-256, não sobrescrita, proteção de symlinks e restrição por diretório configurado.
- Registro aditivo de ocorrências de upload e relatório de duplicatas exatas (SHA-256) e possíveis semelhantes (trigramas de palavras).
- Extração heurística de cláusulas de contratos e alertas com trechos/páginas citadas.
- Manifesto de integração ARA OS 12 e log local de eventos, sem comunicação com agentes externos.
- Painel web com ferramentas de duplicatas, cláusulas, organização e eventos.
- Preservação do banco v0.3 e dos endpoints legados; novos testes de segurança e regressão.

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
