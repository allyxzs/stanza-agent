"""Organização com prévia e confirmação, sempre por CÓPIA.

Diretório raiz explicitamente autorizado por STANZA_ORGANIZE_ROOT:
  entrada/      arquivos de origem (recursivo, excluindo symlinks)
  organizados/  arquivos copiados para categoria/ano/nome
A API nunca aceita caminhos de origem/destino arbitrários.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import tempfile
import threading
import time
import unicodedata
from pathlib import Path
from .core import MAX_BYTES, SUPPORTED, classify, parse_document

MAX_FILES = 100
PLAN_TTL_SECONDS = 900
_plans: dict[str, tuple[float, dict]] = {}
_lock = threading.RLock()


def _base() -> Path:
    configured = os.getenv('STANZA_ORGANIZE_ROOT', '').strip()
    if not configured:
        raise RuntimeError('Configure STANZA_ORGANIZE_ROOT para habilitar a organização.')
    try:
        root = Path(configured).expanduser().resolve(strict=True)
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise ValueError('STANZA_ORGANIZE_ROOT não existe ou não é uma pasta válida.') from exc
    if not root.is_dir():
        raise ValueError('STANZA_ORGANIZE_ROOT deve ser uma pasta existente.')
    return root


def _safe_file(root: Path, path: Path) -> bool:
    """Não segue symlinks, nem em qualquer componente dentro da raiz."""
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    current = root
    for segment in relative.parts:
        current = current / segment
        if current.is_symlink():
            return False
    return path.is_file()


def _slug(value: str, max_len: int = 90) -> str:
    value = unicodedata.normalize('NFKD', value)
    value = ''.join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r'[^A-Za-z0-9._-]+', '_', value).strip('._-')
    return value[:max_len] or 'arquivo'


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _folder_for(filename: str, content: bytes, year: int) -> str:
    try:
        doc = parse_document(filename, content, ocr='nao')
        category = classify(doc.text)['categoria']
    except ValueError:
        category = 'nao_classificados'
    return f'{_slug(category, 40)}/{year}'


def _output_path(root: Path, relative: str) -> Path:
    out = root / 'organizados'
    target = out.joinpath(*Path(relative).parts)
    if target == out or not target.is_relative_to(out):
        raise ValueError('Destino inválido.')
    current = root
    for item in target.relative_to(root).parts:
        current = current / item
        if current.is_symlink():
            raise ValueError('Destino com link simbólico não permitido.')
    return target


def preview_plan() -> dict:
    root = _base()
    incoming = root / 'entrada'
    if incoming.is_symlink() or not incoming.is_dir():
        raise ValueError('Crie uma pasta real chamada entrada dentro de STANZA_ORGANIZE_ROOT.')
    files = sorted((p for p in incoming.rglob('*') if p.suffix.lower() in SUPPORTED and _safe_file(root, p)),
                   key=lambda p: str(p))
    if len(files) > MAX_FILES:
        raise ValueError(f'Limite de {MAX_FILES} arquivos por prévia.')
    operations = []
    used_paths: dict[str, str] = {}
    for path in files:
        size = path.stat().st_size
        if size < 1 or size > MAX_BYTES:
            operations.append({'origem': path.relative_to(root).as_posix(), 'acao': 'ignorar',
                               'motivo': 'Arquivo vazio ou maior que 15 MB.'})
            continue
        content = path.read_bytes()
        sha = hashlib.sha256(content).hexdigest()
        year = time.gmtime(path.stat().st_mtime).tm_year
        folder = _folder_for(path.name, content, year)
        suffix = path.suffix.lower()
        stem = _slug(path.stem, 85)
        original_target = f'{folder}/{stem}{suffix}'
        target = original_target
        resolved = _output_path(root, target)
        if target in used_paths and used_paths[target] != sha:
            target = f'{folder}/{stem}_{sha[:10]}{suffix}'
            resolved = _output_path(root, target)
        if resolved.exists():
            if not _safe_file(root, resolved):
                raise ValueError('Destino existente não é um arquivo regular.')
            if _digest_file(resolved) == sha:
                action = 'ja_organizado'
            else:
                target = f'{folder}/{stem}_{sha[:10]}{suffix}'
                resolved = _output_path(root, target)
                if resolved.exists():
                    if not _safe_file(root, resolved):
                        raise ValueError('Destino com colisão não segura.')
                    if _digest_file(resolved) != sha:
                        raise ValueError('Colisão de nomes: mova manualmente o arquivo de destino e tente de novo.')
                    action = 'ja_organizado'
                else:
                    action = 'copiar'
        else:
            action = 'ja_organizado' if used_paths.get(target) == sha else 'copiar'
        used_paths[target] = sha
        operations.append({'origem': path.relative_to(root).as_posix(), 'destino': target,
                           'sha256': sha, 'tamanho_bytes': size,
                           'categoria': folder.split('/')[0], 'acao': action})
    plan_id = secrets.token_urlsafe(24)
    data = {'plano_id': plan_id, 'raiz': str(root), 'acoes': operations,
            'arquivos': len(operations), 'copias_propostas': sum(x['acao']=='copiar' for x in operations),
            'expira_em_segundos': PLAN_TTL_SECONDS,
            'aviso': 'A aplicação copia arquivos e mantém os originais. Não há sobrescrita nem exclusão.'}
    with _lock:
        now = time.monotonic()
        for key, (created, _) in list(_plans.items()):
            if now - created >= PLAN_TTL_SECONDS:
                del _plans[key]
        _plans[plan_id] = (now, data)
    return data


def _copy_no_overwrite(source: Path, destination: Path, sha: str) -> None:
    """Copia para arquivo temporário e publica com hardlink exclusivo (sem overwrite)."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.parent.is_symlink() or destination.is_symlink():
        raise ValueError('Destino com link simbólico não permitido.')
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.stanza-', dir=destination.parent, delete=False) as tmp:
            temp_name = tmp.name
            with source.open('rb') as src:
                for chunk in iter(lambda: src.read(1024 * 1024), b''):
                    tmp.write(chunk)
            tmp.flush()
            os.fsync(tmp.fileno())
        if _digest_file(Path(temp_name)) != sha:
            raise ValueError('Cópia inválida: SHA-256 não confere.')
        # Hardlink falha se destino já existe; diferente de replace/rename.
        os.link(temp_name, destination, follow_symlinks=False)
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)


def apply_plan(plan_id: str, confirm: bool) -> dict:
    if not confirm:
        raise ValueError('Envie confirmar=true para aplicar a prévia.')
    with _lock:
        pending = _plans.get(plan_id)
        if not pending or time.monotonic() - pending[0] >= PLAN_TTL_SECONDS:
            raise LookupError('Plano inexistente ou expirado; gere uma nova prévia.')
        plan = pending[1]
        root = _base()
        if str(root) != plan['raiz']:
            raise ValueError('A pasta autorizada mudou; gere uma nova prévia.')
        # Todos os pré-requisitos são validados antes de copiar o primeiro arquivo.
        for op in plan['acoes']:
            if op['acao'] == 'ignorar':
                continue
            source = root / op['origem']
            if not _safe_file(root, source) or _digest_file(source) != op['sha256']:
                raise ValueError('Um arquivo de origem foi alterado; gere uma nova prévia.')
            target = _output_path(root, op['destino'])
            if op['acao'] == 'copiar' and target.exists():
                raise ValueError('Um destino mudou; gere uma nova prévia.')
            if op['acao'] == 'ja_organizado' and (not _safe_file(root, target) or _digest_file(target) != op['sha256']):
                raise ValueError('Um destino existente mudou; gere uma nova prévia.')
        completed = []
        try:
            for op in plan['acoes']:
                if op['acao'] != 'copiar':
                    continue
                source = root / op['origem']
                target = _output_path(root, op['destino'])
                # Segue estritamente sem substituir arquivos existentes.
                _copy_no_overwrite(source, target, op['sha256'])
                completed.append(op['destino'])
        finally:
            del _plans[plan_id]  # Evita repetição, mesmo em caso de falha parcial.
        return {'plano_id': plan_id, 'copiados': completed, 'quantidade_copiada': len(completed),
                'originais_preservados': True,
                'aviso': 'Arquivos copiados; confira a pasta organizados. A prévia é de uso único.'}
