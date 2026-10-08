"""Portable, folder-local conversation snapshots. No model or source-history API.

Native exports are sanitized by OpenCode. Listing/reading does not import or
execute any conversation. The same standalone file can live in each project.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / 'continuity' / 'sessions'


def norm(value):
    return str(value).replace('\\', '/').rstrip('/').casefold()


def executable():
    if os.name == 'nt':
        binary = Path(os.environ.get('APPDATA', '')) / 'npm/node_modules/opencode-ai/bin/opencode.exe'
        if binary.is_file():
            return str(binary)
    binary = shutil.which('opencode')
    if not binary:
        raise RuntimeError('OpenCode is not installed; read CONTINUITY.md and saved transcript.md files directly.')
    return binary


def cli(*args, cwd=None):
    result = subprocess.run([executable(), *args, '--pure'], cwd=cwd or ROOT,
                            capture_output=True, encoding='utf-8', timeout=120)
    if result.returncode:
        raise RuntimeError(f'OpenCode {args[0]} failed (exit {result.returncode}); no transcript or credential output emitted.')
    return result.stdout


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def local_sessions(workspace):
    output = cli('session', 'list', '--format', 'json', cwd=workspace)
    values = json.loads(output) if output.strip() else []
    if not isinstance(values, list):
        raise RuntimeError('Unsupported session-list shape')
    return [v for v in values if norm(v.get('directory', '')) == norm(workspace)]


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def catalog():
    path = STORE / 'catalog.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'version': 1, 'sessions': []}


def safe_title(text):
    # Titles are navigation metadata, never an excuse to print credentials.
    text = re.sub(r'(?i)(?:https?://|ss://|vless://)\S+|\b(?:eyJ|ghp_|sk-)[\w.-]+', '[redacted]', text)
    return re.sub(r'[\r\n\[\]`<>]', ' ', text)[:160]


def conversation_text(text):
    """Keep conversation text, with conservative secret guards; not lossless."""
    text = re.sub(r'-----BEGIN[^\n]*PRIVATE KEY-----.*?-----END[^\n]*PRIVATE KEY-----',
                  '[REDACTED PRIVATE KEY]', text, flags=re.S)
    text = re.sub(r'(?i)\b(?:ss|ssconf|vless|vmess|trojan|hysteria2)://\S+', '[REDACTED URI]', text)
    text = re.sub(r'https?://[^\s<>"`]+', lambda m: re.sub(r'[?#].*', '?[REDACTED]',
                  re.sub(r'//[^/@\s]+:[^/@\s]+@', '//[REDACTED]@', m[0])), text)
    text = '\n'.join('[REDACTED sensitive line]' if re.search(
        r'(?i)password|passwd|private.?key|preshared|authorization|bearer\s|cookie|jwt_secret|api.?key|access.?token|refresh.?token|client.?secret|пароль|şifre|parola|(?:token|secret)[\s"\x27]*[=:]', line)
        else line for line in text.splitlines())
    text = re.sub(r'\b(?:gh[pousr]_[\w]+|github_pat_[\w]+|sk-[\w-]+|eyJ[\w.-]+)\b', '[REDACTED]', text)
    text = re.sub(r'\b[A-Za-z][A-Za-z_-]{2,}[_-]\d{4,}\b', '[REDACTED ambiguous identifier]', text)
    return re.sub(r'(?<![\w])[A-Za-z0-9+/=_-]{40,}(?![\w])', '[REDACTED opaque value]', text)


def render_index(value):
    lines = [f'# {ROOT.name} — saved sessions', '', 'Read ../SESSIONS.md for restore instructions.', '',
             'Each entry is a separate snapshot, not the authoritative project backlog.', '']
    for entry in value['sessions']:
        lines += [f"## {entry['key']} — {entry['title']}", '',
                  f"- Captured UTC: {entry['captured_utc']}", f"- Scope: {entry['scope']}",
                  f"- Original session: `{entry['origin_id']}`", f"- Messages: {entry['messages']}",
                  f"- [Readable transcript]({entry['transcript']})", f"- [Native export]({entry['native']})", '']
    if not value['sessions']:
        lines += ['No session saved yet. The project can still resume from ../../CONTINUITY.md.', '']
    notes = sorted((STORE / 'notes').glob('*.md'))
    if notes:
        lines += ['## Agent-neutral continuation notes', '']
        lines += [f'- [{safe_title(p.stem)}]({p.relative_to(STORE).as_posix()})' for p in notes]
    (STORE / 'INDEX.md').write_text('\n'.join(lines), encoding='utf-8')


def save(args):
    source = Path(args.from_workspace).resolve() if args.from_workspace else ROOT
    if norm(source) != norm(ROOT) and not args.shared:
        raise RuntimeError('A different source workspace requires explicit --shared provenance.')
    sessions = local_sessions(source)
    if args.session:
        sessions = [s for s in sessions if s['id'] == args.session]
    sessions = sorted(sessions, key=lambda s: s.get('updated', 0), reverse=True)[:args.limit]
    if not sessions:
        raise RuntimeError('No matching native OpenCode session. Existing saved sessions and project context were not changed.')
    STORE.mkdir(parents=True, exist_ok=True)
    value = catalog()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    results = []
    for session in sessions:
        original_id = session['id']
        if not re.fullmatch(r'ses_[A-Za-z0-9]+', original_id):
            raise RuntimeError('Unsupported native session ID')
        # Native sanitize redacts ALL message bodies in this version. Keep its
        # safe metadata/tool/file skeleton, restoring only guarded visible text.
        data = json.loads(cli('export', original_id, '--sanitize', cwd=source))
        if not isinstance(data.get('info'), dict) or not isinstance(data.get('messages'), list):
            raise RuntimeError('Unsupported native export shape')
        raw = json.loads(cli('export', original_id, cwd=source))  # Memory only.
        visible = {p['id']: p['text'] for m in raw.get('messages', [])
                   if m.get('info', {}).get('role') in ('user', 'assistant')
                   for p in m.get('parts', []) if p.get('type') == 'text'
                   and isinstance(p.get('text'), str) and not p.get('synthetic')}
        for message in data['messages']:
            for part in message.get('parts', []):
                if part.get('type') == 'text' and part.get('id') in visible:
                    part['text'] = conversation_text(visible[part['id']])
        del raw, visible  # Unsanitized tool/file payloads are never written.
        key = original_id
        folder = STORE / 'snapshots' / key / stamp
        folder.mkdir(parents=True, exist_ok=False)
        native, transcript = folder / 'opencode.json', folder / 'transcript.md'
        write_json(native, data)
        title = safe_title(session.get('title', 'Untitled session'))
        scope = 'shared multi-root workspace conversation; use this folder\'s CONTINUITY for project state' if args.shared else 'this project workspace'
        lines = [f'# {title}', '', f'Original session: `{original_id}`', f'Scope: {scope}',
                 f'Captured: {stamp}. Sanitized snapshot; not live application state.', '',
                 'Tool records remain in the native JSON. This readable view contains user/assistant text.', '']
        for message in data['messages']:
            info = message.get('info', {})
            parts = message.get('parts', [])
            text = '\n\n'.join(p.get('text', '') for p in parts if p.get('type') == 'text' and not p.get('ignored'))
            if text:
                lines += [f"## {info.get('role', 'message')} — {info.get('id', '')}", '', text, '']
        transcript.write_text('\n'.join(lines), encoding='utf-8')
        entry = {'key': key, 'title': title, 'origin_id': original_id, 'source_workspace': str(source),
                 'project_key': value.get('project_key', ROOT.name), 'scope': scope, 'captured_utc': stamp,
                 'messages': len(data['messages']), 'native': native.relative_to(STORE).as_posix(),
                 'transcript': transcript.relative_to(STORE).as_posix(),
                 'sha256': {'native': checksum(native), 'transcript': checksum(transcript)},
                 'native_sanitized': True, 'visible_text_guarded': True, 'source_changed': False}
        write_json(folder / 'session.json', entry)
        value['project_key'] = entry['project_key']
        value['sessions'] = [e for e in value['sessions'] if e['key'] != key] + [entry]
        results.append({k: entry[k] for k in ('key', 'captured_utc', 'messages', 'scope')})
    write_json(STORE / 'catalog.json', value)
    render_index(value)
    emit({'project': ROOT.name, 'saved': results, 'catalog': str(STORE / 'INDEX.md')})


def verified_entry(key):
    entries = catalog()['sessions']
    if not key and len(entries) == 1:
        key = entries[0]['key']
    entry = next((e for e in entries if e['key'] == key), None)
    if not entry:
        raise RuntimeError('Choose an existing session key from continuity/sessions/INDEX.md.')
    for kind in ('native', 'transcript'):
        path = (STORE / entry[kind]).resolve()
        if STORE.resolve() not in path.parents or checksum(path) != entry['sha256'][kind]:
            raise RuntimeError('Saved snapshot path/hash verification failed')
    return entry


def project_id():
    result = subprocess.run(['git', 'rev-list', '--max-parents=0', 'HEAD'], cwd=ROOT,
                            capture_output=True, encoding='utf-8') if shutil.which('git') else None
    return sorted(result.stdout.split())[0] if result and result.returncode == 0 and result.stdout.strip() else 'global'


def prepare(key):
    entry = verified_entry(key)
    data = json.loads((STORE / entry['native']).read_text(encoding='utf-8'))
    # Fork identifiers deterministically per project: a shared workspace snapshot
    # can be restored in several folders without overwriting the original thread.
    ids = {data['info']['id']}
    for message in data['messages']:
        ids.add(message['info']['id'])
        ids.update(p['id'] for p in message.get('parts', []) if p.get('id'))
    mapping = {old: old.split('_', 1)[0] + '_' + hashlib.sha256(
               (entry['project_key'] + ':' + old).encode()).hexdigest()[:26] for old in ids}
    def remap(value):
        if isinstance(value, dict):
            return {k: remap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [remap(v) for v in value]
        return mapping.get(value, value) if isinstance(value, str) else value
    data = remap(data)
    info = data['info']
    info.update(directory=str(ROOT), projectID=project_id(), title=f"[{entry['project_key']}] {entry['title']}")
    for key in ('parentID', 'permission', 'share'):
        info.pop(key, None)
    for meta in [info] + [m['info'] for m in data['messages']]:
        if isinstance(meta.get('path'), dict):
            meta['path'] = {**meta['path'], 'cwd': str(ROOT), 'root': str(ROOT)}
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    for message in data['messages']:
        for part in message.get('parts', []):
            state = part.get('state', {})
            if part.get('type') == 'tool' and state.get('status') in ('pending', 'running'):
                part['state'] = {'status': 'error', 'input': state.get('input', {}),
                                 'error': 'Interrupted at portable snapshot; not automatically re-executed.',
                                 'time': {'start': state.get('time', {}).get('start', now), 'end': now}}
        if message['info'].get('role') == 'assistant' and not message['info'].get('time', {}).get('completed'):
            message['info'].setdefault('time', {})['completed'] = now
            message['info'].setdefault('finish', 'stop')
    destination = STORE / 'restore' / (entry['key'] + '.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_json(destination, data)
    return destination, info['id']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['list', 'live', 'save', 'verify', 'prepare', 'restore', 'index'])
    parser.add_argument('key', nargs='?', default='')
    parser.add_argument('--session', default='')
    parser.add_argument('--from-workspace', default='')
    parser.add_argument('--shared', action='store_true')
    parser.add_argument('--limit', type=int, default=3)
    args = parser.parse_args()
    try:
        if args.command == 'index':
            STORE.mkdir(parents=True, exist_ok=True)
            render_index(catalog())
            emit({'catalog': str(STORE / 'INDEX.md')})
        elif args.command == 'list':
            emit({'project': ROOT.name, 'sessions': [{k: e[k] for k in ('key', 'title', 'captured_utc', 'scope')} for e in catalog()['sessions']]})
        elif args.command == 'live':
            emit({'project': ROOT.name, 'sessions': [{k: s[k] for k in ('id', 'created', 'updated', 'directory')} for s in local_sessions(ROOT)]})
        elif args.command == 'save':
            if args.limit < 1:
                raise RuntimeError('--limit must be positive')
            save(args)
        elif args.command == 'verify':
            entries = catalog()['sessions']
            if not entries:
                raise RuntimeError('No saved sessions to verify; project startup documents remain available.')
            for entry in entries:
                verified_entry(entry['key'])
            emit({'project': ROOT.name, 'sessions': len(entries), 'ok': True})
        else:
            destination, session_id = prepare(args.key)
            already_present = False
            if args.command == 'restore':
                listed = cli('session', 'list', '--format', 'json')
                already_present = any(s['id'] == session_id for s in (json.loads(listed) if listed.strip() else []))
                if not already_present:
                    cli('import', str(destination))
            emit({'prepared': str(destination), 'imported': args.command == 'restore' and not already_present,
                  'already_present': already_present,
                  'session_id': session_id, 'resume': f'opencode . --session {session_id}',
                  'note': 'Open explicitly; no model run or historical tool execution was started.'})
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        emit({'error': type(exc).__name__, 'detail': str(exc) if isinstance(exc, RuntimeError) else 'Session operation failed; originals unchanged.'})
        return 2


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
