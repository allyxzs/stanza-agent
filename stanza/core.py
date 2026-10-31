"""Leitura, extração e análise determinística do Stanza. Nunca envia arquivos à nuvem."""
from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import fitz
from docx import Document

SUPPORTED = {'.pdf', '.docx', '.txt'}
MAX_BYTES = 15 * 1024 * 1024
MAX_PAGES = 120
MAX_OCR_PAGES = 25
STOPWORDS = set('a o as os de da do das dos em no na nos nas um uma uns umas e ou que com por para ao aos à às se é foi ser como mais menos muito sobre este esta esse essa seu sua seus suas the and of to in for on is are be by from'.split())


@dataclass
class ParsedDocument:
    filename: str
    pages: list[str]
    sha256: str
    ocr_pages: list[int] = field(default_factory=list)

    @property
    def text(self) -> str:
        return '\n\n'.join(self.pages)


def ocr_available() -> bool:
    return shutil.which('tesseract') is not None


def ocr_page(page: fitz.Page) -> str:
    if not ocr_available():
        raise ValueError('OCR indisponível. Instale: sudo apt install tesseract-ocr tesseract-ocr-por')
    # Prevent huge images and unbounded OCR calls on large or malicious PDF pages.
    rect = page.rect
    scale = min(1.6, (9_000_000 / max(rect.width * rect.height, 1)) ** 0.5)
    if scale <= 0:
        raise ValueError('Página PDF inválida para OCR.')
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY, alpha=False)
    image = pix.tobytes('png')
    langs = os.getenv('STANZA_OCR_LANG', 'por+eng')
    if not re.fullmatch(r'[A-Za-z0-9_+]+', langs):
        raise ValueError('STANZA_OCR_LANG inválido.')
    try:
        proc = subprocess.run(
            ['tesseract', 'stdin', 'stdout', '-l', langs],
            input=image, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=30, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError('OCR excedeu o tempo limite por página.') from exc
    if proc.returncode:
        raise ValueError('Falha no OCR. Confira os idiomas instalados (tesseract --list-langs).')
    return proc.stdout.decode('utf-8', errors='replace')


def parse_document(filename: str, content: bytes, *, ocr: str = 'auto') -> ParsedDocument:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED:
        raise ValueError('Formato não suportado. Use PDF, DOCX ou TXT.')
    if not content:
        raise ValueError('Arquivo vazio.')
    if len(content) > MAX_BYTES:
        raise ValueError('Arquivo maior que o limite de 15 MB.')
    if ocr not in {'auto', 'sim', 'nao'}:
        raise ValueError('ocr deve ser auto, sim ou nao.')
    ocr_pages = []
    try:
        if extension == '.pdf':
            with fitz.open(stream=content, filetype='pdf') as pdf:
                if pdf.needs_pass:
                    raise ValueError('PDF protegido por senha não é suportado.')
                if len(pdf) > MAX_PAGES:
                    raise ValueError(f'PDF excede o limite de {MAX_PAGES} páginas.')
                pages = []
                for index, page in enumerate(pdf, start=1):
                    value = page.get_text(sort=True)
                    use_ocr = ocr == 'sim' or (ocr == 'auto' and len(value.strip()) < 30)
                    if use_ocr:
                        if len(ocr_pages) >= MAX_OCR_PAGES:
                            raise ValueError(f'Limite de {MAX_OCR_PAGES} páginas processadas por OCR.')
                        recognized = ocr_page(page)
                        if recognized.strip():
                            value = recognized
                        ocr_pages.append(index)
                    pages.append(value)
        elif extension == '.docx':
            doc = Document(io.BytesIO(content))
            lines = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    lines.append(' | '.join(cell.text for cell in row.cells))
            pages = ['\n'.join(lines)]
        else:
            try:
                pages = [content.decode('utf-8-sig')]
            except UnicodeDecodeError:
                pages = [content.decode('cp1252')]
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError('Arquivo inválido ou corrompido.') from exc
    if not any(p.strip() for p in pages):
        raise ValueError('Nenhum texto extraível no documento.')
    return ParsedDocument(filename=Path(filename).name, pages=pages,
                          sha256=hashlib.sha256(content).hexdigest(), ocr_pages=ocr_pages)


def classify(text: str) -> dict:
    rules = {
        'contrato': ['contratante', 'contratada', 'cláusula', 'vigência', 'rescisão', 'contrato'],
        'nota_fiscal': ['nota fiscal', 'danfe', 'chave de acesso', 'emitente', 'nfe'],
        'curriculo': ['currículo', 'curriculum', 'experiência profissional', 'formação acadêmica'],
        'relatorio': ['relatório', 'indicadores', 'resultados', 'análise', 'conclusão'],
        'comprovante': ['comprovante', 'autenticação bancária', 'transferência realizada', 'pagamento efetuado'],
    }
    lower = text.casefold()
    scores = {kind: sum(lower.count(word) for word in words) for kind, words in rules.items()}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return {'categoria': 'outros', 'confianca': 'baixa', 'evidencias': []}
    evidence = [word for word in rules[best] if word in lower]
    return {'categoria': best, 'confianca': 'media' if len(evidence) >= 2 else 'baixa', 'evidencias': evidence}


def extract(text: str) -> dict:
    dates = re.findall(r'\b(?:0?[1-9]|[12]\d|3[01])/(?:0?[1-9]|1[0-2])/(?:19|20)\d{2}\b', text)
    money = re.findall(r'R\$\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})?|R\$\s*\d+(?:,\d{2})?', text)
    cnpjs = re.findall(r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b', text)
    emails = re.findall(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b', text)
    return {'datas': list(dict.fromkeys(dates)), 'valores': list(dict.fromkeys(money)), 'cnpjs_formato': list(dict.fromkeys(cnpjs)), 'emails': list(dict.fromkeys(emails))}


def summarize(pages: list[str], max_sentences: int = 5) -> list[dict]:
    if not 1 <= max_sentences <= 20:
        raise ValueError('max_sentences deve estar entre 1 e 20.')
    sentences = []
    for page_num, page in enumerate(pages, 1):
        for sentence in re.split(r'(?<=[.!?])\s+|\n+', page):
            sentence = sentence.strip()
            if len(sentence) >= 25:
                sentences.append((page_num, sentence))
    if not sentences:
        return [{'pagina': 1, 'texto': pages[0][:500]}]
    words = [w for _, s in sentences for w in re.findall(r'\b\w+\b', s.casefold()) if len(w) > 3 and w not in STOPWORDS]
    frequency = Counter(words)
    ranked = sorted(enumerate(sentences), key=lambda item: (-sum(frequency[w] for w in re.findall(r'\b\w+\b', item[1][1].casefold())) / max(len(item[1][1].split()), 1), item[0]))
    chosen = sorted(ranked[:max_sentences], key=lambda item: item[0])
    return [{'pagina': page, 'texto': sentence[:1200]} for _, (page, sentence) in chosen]


def analyze(doc: ParsedDocument, max_sentences: int = 5) -> dict:
    return {'arquivo': doc.filename, 'sha256': doc.sha256, 'paginas': len(doc.pages),
            'caracteres': len(doc.text), 'classificacao': classify(doc.text),
            'dados': extract(doc.text), 'resumo_extrativo': summarize(doc.pages, max_sentences),
            'ocr_paginas': doc.ocr_pages}
