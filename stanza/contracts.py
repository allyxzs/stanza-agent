"""Identificação heurística e rastreável de trechos de contratos.

Não é parecer jurídico, nem valida autenticidade de assinatura ou legalidade.
"""
from __future__ import annotations

import re
from .core import ParsedDocument, extract, classify

CLAUSE_HEADING = re.compile(
    r'^\s*(?:CL[ÁA]USULA\s+(?:\d{1,3}|PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA|QUINTA|SEXTA|S[ÉE]TIMA|OITAVA|NONA|D[ÉE]CIMA)\b[^\n]*'
    r'|\d{1,2}(?:\.\d{1,2})?\s*[-.)–]\s*[A-Za-zÁÀÂÃÉÊÍÓÔÕÚÇ][^\n]{3,100})',
    flags=re.IGNORECASE,
)
TOPICS = {
    'objeto': r'\b(?:objeto|prest[aã]ção de servi[çc]os|finalidade)\b',
    'pagamento': r'\b(?:pagamento|remunera[çc][aã]o|valor total|honor[aá]rios|pre[çc]o)\b',
    'prazo_vigencia': r'\b(?:vig[êe]ncia|prazo|dura[çc][aã]o|vencimento)\b',
    'rescisao': r'\b(?:rescis[aã]o|resolu[çc][aã]o|encerramento|distrato)\b',
    'multa_penalidade': r'\b(?:multa|penalidade|juros morat[oó]rios)\b',
    'renovacao': r'\b(?:renova[çc][aã]o|prorroga[çc][aã]o)\b',
    'confidencialidade': r'\b(?:confidencialidade|sigilo|informa[çc][õo]es confidenciais)\b',
    'dados_pessoais': r'\b(?:lgpd|dados pessoais|prote[çc][aã]o de dados)\b',
    'foro': r'\b(?:foro|jurisdi[çc][aã]o|comarca)\b',
}
WARNINGS = {
    'renovacao_automatica': (r'\brenova[çc][aã]o autom[aá]tica\b|\bautomaticamente renovad[oa]\b',
                              'Menção a renovação automática; confira as condições e prazos.'),
    'multa': (r'\bmulta\b|\bpenalidade\b',
              'Menção a multa ou penalidade; confira hipóteses e valores.'),
    'rescisao': (r'\brescis[aã]o\b',
                 'Menção a rescisão; confira aviso prévio e consequências.'),
    'dados_pessoais': (r'\blgpd\b|\bdados pessoais\b',
                       'Menção a dados pessoais; confira obrigações previstas.'),
}


def _topic(text: str) -> str:
    for label, expression in TOPICS.items():
        if re.search(expression, text, flags=re.IGNORECASE):
            return label
    return 'outros'


def _blocks(page: str) -> list[tuple[str, str]]:
    """Separa trechos por títulos explícitos; não inventa cláusulas."""
    blocks = []
    title, body = None, []
    for line in page.splitlines():
        line = line.strip()
        if not line:
            continue
        if CLAUSE_HEADING.match(line):
            if title is not None:
                blocks.append((title, ' '.join(body).strip()))
            title, body = line[:180], []
        elif title is not None:
            body.append(line)
    if title is not None:
        blocks.append((title, ' '.join(body).strip()))
    return blocks


def analyze_contract(doc: ParsedDocument) -> dict:
    clauses = []
    alerts = []
    for page_num, page in enumerate(doc.pages, 1):
        for heading, body in _blocks(page):
            if len(clauses) >= 80:
                break
            source = (heading + '\n' + body).strip()
            clauses.append({'pagina': page_num, 'titulo': heading,
                            'tipo': _topic(source[:1500]), 'evidencia': source[:1200],
                            'confianca': 'media', 'extraida_por': 'regras_locais'})
        for code, (expression, description) in WARNINGS.items():
            for match in list(re.finditer(expression, page, flags=re.IGNORECASE))[:3]:
                if len(alerts) >= 30:
                    break
                start, end = max(0, match.start() - 70), min(len(page), match.end() + 110)
                alerts.append({'codigo': code, 'pagina': page_num,
                               'evidencia': re.sub(r'\s+', ' ', page[start:end]).strip(),
                               'orientacao': description})
    return {'arquivo': doc.filename, 'sha256': doc.sha256,
            'categoria_provavel': classify(doc.text)['categoria'],
            'clausulas': clauses, 'sinais_para_revisao': alerts,
            'campos_extraidos': extract(doc.text),
            'observacao': ('Detecção heurística de títulos e termos. Uma cláusula pode atravessar '
                           'páginas e trechos podem estar incompletos. '
                           'A ausência de alerta não comprova ausência de risco. Não é parecer jurídico.')}
