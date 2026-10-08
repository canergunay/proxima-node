"""ADM-local lossless history capture and read-only, sanitized retrieval.

Uses the source-backed Proxima migration's design, with independent identity,
strict attribution and no dependency on its archive or mutable configuration.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
def norm(v):
    return str(v).replace('\\', '/').removeprefix('//?/').rstrip('/').lower()
IDENTITY = norm(ROOT)
ARCHIVE = Path(os.environ['LOCALAPPDATA']) / 'OpenCode/continuity' / ('proxima-node-' + hashlib.sha256(IDENTITY.encode()).hexdigest()[:12])
def digest(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
def write(p, v):
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding='utf-8')
def emit(v):
    print(json.dumps(v, ensure_ascii=False, indent=2))
def exact(v):
    return norm(v) == IDENTITY or norm(v).startswith(IDENTITY + '/')
def records(p):
    with p.open(encoding='utf-8-sig') as f:
        for line, raw in enumerate(f, 1):
            try:
                o = json.loads(raw)
                yield line, o if isinstance(o, dict) else {'_parse_error': True}
            except ValueError:
                yield line, {'_parse_error': True}
SENSITIVE = r'(?i)password|passwd|private.?key|preshared|authorization|cookie|token|secret|api.?key|credential'
def redact(s):
    s = re.sub(r'-----BEGIN[^\n]*PRIVATE KEY-----.*?-----END[^\n]*PRIVATE KEY-----', lambda m: '\n'.join('[REDACTED PRIVATE KEY]' for _ in m[0].split('\n')), s, flags=re.S)
    s = re.sub(r'(?i)\b(?:ss|ssconf|vless|vmess|trojan|hysteria2)://[^\s"<>]+', '[REDACTED URI]', s)
    s = re.sub(r'https?://[^\s"<>]+', lambda m: re.sub(r'[?#].*', '?[REDACTED]', re.sub(r'//[^/@\s]+:[^/@\s]+@', '//[REDACTED]@', m[0])), s)
    s = '\n'.join('[REDACTED sensitive line]' if re.search(SENSITIVE + r'|bearer\s|пароль|şifre|parola', x) else x for x in s.splitlines())
    s = re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]+|eyJ[A-Za-z0-9_.-]+)\b', '[REDACTED]', s)
    return re.sub(r'(?<![\w])[A-Za-z0-9+/=_-]{40,}(?![\w])', '[REDACTED opaque]', s)
def flatten(v):
    if isinstance(v, str):
        # Embedded structured JSON must be redacted before losing its keys.
        try:
            parsed = json.loads(v)
            if isinstance(parsed, (list, dict)):
                return flatten(parsed)
        except ValueError:
            pass
        return redact(v)
    if isinstance(v, list):
        return '\n'.join(flatten(x) for x in v)
    if isinstance(v, dict):
        if v.get('type') in ('image', 'document'):
            return '[BINARY: original source record retained]'
        return '\n'.join('[REDACTED field]' if re.search(SENSITIVE, k) else flatten(x) for k, x in v.items() if k not in ('data', 'signature') and isinstance(x, (str, dict, list)))
    return ''
def acl(path=ARCHIVE, protected=True):
    ps = "$a=Get-Acl -LiteralPath '" + str(path).replace("'", "''") + "'; $u=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value; @{user=$u; protected=$a.AreAccessRulesProtected; rules=@($a.Access | ForEach-Object { @{sid=$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value; type=$_.AccessControlType.ToString(); rights=$_.FileSystemRights.ToString()} })} | ConvertTo-Json -Depth 5 -Compress"
    a = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', ps], text=True))
    assert (not protected or a['protected']) and {r['sid'] for r in a['rules']} == {a['user'], 'S-1-5-18'}
    assert all(r['type'] == 'Allow' and r['rights'] == 'FullControl' for r in a['rules'])
    return a
def secure():
    if ARCHIVE.exists():
        assert json.loads((ARCHIVE / 'owner.json').read_text())['workspace'] == IDENTITY
    else:
        ARCHIVE.mkdir(parents=True)
        sid = re.search(r'S-1-5-[0-9-]+', subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True))[0]
        subprocess.run(['icacls', str(ARCHIVE), '/inheritance:r', '/grant:r', f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'], check=True, stdout=subprocess.DEVNULL)
        acl()
        write(ARCHIVE / 'owner.json', {'workspace': IDENTITY, 'project': 'proxima-node (ADM)'})
    acl()
def path_evidence(o, cwd=''):
    """Only structured path fields, not textual project-name resemblance."""
    found = []
    if isinstance(o, dict):
        cwd = o.get('cwd') or cwd
        for k, v in o.items():
            if k in ('cwd', 'file_path', 'filePath', 'path', 'workdir', 'trackingPath') and isinstance(v, str):
                resolved = os.path.abspath(os.path.join(cwd, v)) if cwd and not os.path.isabs(v) else v
                if exact(resolved):
                    found.append((k, resolved))
            if isinstance(v, (dict, list)):
                found.extend(path_evidence(v, cwd))
    elif isinstance(o, list):
        for v in o:
            found.extend(path_evidence(v, cwd))
    return found
def discover():
    secure()
    found, errors, probes = {}, [], []
    sessions, stores = set(), set()
    def add(p, category, evidence, session=None):
        if p.is_file():
            found.setdefault(norm(p), {'path': str(p), 'category': category, 'evidence': evidence, 'session': session, 'bytes': p.stat().st_size})
    bases = [(HOME / '.claude/projects', 'transcript'), (HOME / '.codex/sessions', 'codex-transcript'), (HOME / '.codex/archived_sessions', 'codex-transcript')]
    for base, cat in bases:
        scanned = 0
        for p in base.rglob('*.jsonl'):
            scanned += 1
            evidence, cwds = [], set()
            try:
                inherited = ''
                for line, o in records(p):
                    if o.get('cwd'):
                        cwds.add(norm(o['cwd']))
                        inherited = o['cwd']
                    for key, value in path_evidence(o, inherited):
                        if len(evidence) < 12:
                            evidence.append({'line': line, 'field': key, 'path': value})
                if evidence:
                    meta = next(records(p), (0, {}))[1].get('payload', {})
                    sid = meta.get('id', p.stem) if cat == 'codex-transcript' else p.stem
                    add(p, cat, evidence, sid)
                    found[norm(p)]['mixed_container'] = any(not exact(c) for c in cwds)
                    sessions.add(sid)
                    if cat == 'transcript':
                        stores.add(p.parent if p.parent.parent.name == 'projects' else next((a for a in p.parents if a.parent.name == 'projects'), p.parent))
            except (OSError, UnicodeError) as e:
                errors.append({'path': str(p), 'error': type(e).__name__})
        probes.append({'root': str(base), 'exists': base.exists(), 'jsonl_scanned': scanned})
    # Imported Codex sessions retain the original mixed cwd. Resolve their
    # provenance through the local import ledger's exact original source path.
    ledger = HOME / '.codex/external_agent_session_imports.json'
    import_links = []
    if ledger.exists():
        def walk_import(v):
            if isinstance(v, dict):
                source = v.get('source_path')
                if isinstance(source, str) and norm(source) in found:
                    uuids = set()
                    def ids(x):
                        if isinstance(x, str):
                            uuids.update(re.findall(r'(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', x))
                        elif isinstance(x, dict):
                            for y in x.values():
                                ids(y)
                        elif isinstance(x, list):
                            for y in x:
                                ids(y)
                    ids(v)
                    import_links.append({'source_path': source, 'uuid_candidates': sorted(uuids)})
                for x in v.values():
                    walk_import(x)
            elif isinstance(v, list):
                for x in v:
                    walk_import(x)
        walk_import(json.loads(ledger.read_text(encoding='utf-8')))
        for p in (HOME / '.codex/sessions').rglob('*.jsonl'):
            meta = next(records(p), (0, {}))[1].get('payload', {})
            for link in import_links:
                if meta.get('id') in link['uuid_candidates']:
                    add(p, 'codex-transcript', {'import_ledger': str(ledger), 'source_path': link['source_path'], 'relation': 'ledger UUID matches session_meta.id; mixed import'}, meta['id'])
    write(ARCHIVE / 'import-provenance.json', import_links)
    for base in stores:
        # Shared memory is preserved as a historical container, never active rules.
        for p in (base / 'memory').rglob('*'):
            add(p, 'shared-memory', 'memory in store containing path-attributed ADM sessions; mixed scope')
        for sid in list(sessions):
            for p in (base / sid).rglob('*'):
                add(p, 'session-sidecar', 'verified parent session directory', sid)
    for bucket in ('file-history', 'todos', 'session-env', 'sessions', 'debug'):
        for p in (HOME / '.claude' / bucket).glob('*'):
            sid = next((s for s in sessions if p.name == s or p.name.startswith(s + '.')), None)
            if sid:
                for q in ([p] if p.is_file() else p.rglob('*')):
                    add(q, bucket, 'attributed parent session identifier', sid)
    temp = Path(os.environ['LOCALAPPDATA']) / 'Temp/claude'
    for base in temp.glob('*'):
        for sid in sessions:
            for p in (base / sid).rglob('*'):
                add(p, 'session-artifact', 'attributed parent session identifier', sid)
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    for name in filter(None, tracked):
        add(ROOT / name, 'workspace-checkpoint', 'tracked current ADM file, not historical revision')
    for name in ('GOC.md', 'CLAUDE.md', 'AGENTS.md', 'CONTINUITY.md', '.claude', '.codex', '.agents', 'TEMP'):
        p = ROOT / name
        for q in ([p] if p.is_file() else p.rglob('*')):
            add(q, 'workspace-artifact', 'exact workspace')
    for base in [Path(os.environ['APPDATA']) / 'Claude' / n for n in ('claude-code-sessions', 'local-agent-mode-sessions', 'claude-code', 'space-memory-copy', 'git-shadow')] + [Path(os.environ['LOCALAPPDATA']) / 'Claude-Data', HOME / '.local/share/opencode']:
        count = size = 0
        candidates = []
        for p in base.rglob('*'):
            if p.is_file():
                count += 1
                size += p.stat().st_size
                if p.suffix in ('.json', '.jsonl') and p.stat().st_size < 15000000:
                    try:
                        objs = records(p) if p.suffix == '.jsonl' else [(1, json.loads(p.read_text(encoding='utf-8')))]
                        if any(path_evidence(o) for _, o in objs):
                            candidates.append(str(p))
                            add(p, 'alternative-store', 'structured exact ADM path; container may be mixed')
                    except (OSError, ValueError, UnicodeError):
                        pass
        probes.append({'root': str(base), 'exists': base.exists(), 'files': count, 'bytes': size, 'candidates': candidates})
    if (ARCHIVE / 'current.json').exists():
        _, prior = current()
        for e in prior['files']:
            if norm(e['path']) not in found and not Path(e['path']).exists():
                found[norm(e['path'])] = e
    write(ARCHIVE / 'discovery.json', {'workspace': IDENTITY, 'sources': list(found.values()), 'errors': errors, 'probes': probes})
    emit({'archive': str(ARCHIVE), 'files': len(found), 'bytes': sum(x['bytes'] for x in found.values()), 'categories': dict(Counter(x['category'] for x in found.values())), 'errors': errors, 'probes': probes})
def capture():
    secure()
    prior_snapshot, prior_files = None, {}
    if (ARCHIVE / 'current.json').exists():
        prior_snapshot, prior = current()
        prior_files = {norm(e['path']): e for e in prior['files']}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    snap = ARCHIVE / 'snapshots' / stamp
    snap.mkdir(parents=True)
    objects = ARCHIVE / 'objects'
    objects.mkdir(exist_ok=True)
    entries = json.loads((ARCHIVE / 'discovery.json').read_text(encoding='utf-8'))['sources']
    for e in entries:
        p = Path(e['path'])
        try:
            before = p.stat()
            data = p.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            dest = objects / sha
            if not dest.exists():
                with dest.open('xb') as f:
                    f.write(data)
            after = p.stat()
            stable = before.st_size == after.st_size == len(data) and before.st_mtime_ns == after.st_mtime_ns and digest(p) == sha
            assert digest(dest) == sha
            e.update(sha256=sha, archive_path=str(dest), bytes=len(data), error=None if stable else 'unstable source')
        except (OSError, AssertionError) as ex:
            old = prior_files.get(norm(p))
            if isinstance(ex, FileNotFoundError) and old and not old.get('error') and digest(old['archive_path']) == old['sha256']:
                e.update(sha256=old['sha256'], archive_path=old['archive_path'], bytes=old['bytes'], error=None, source_error='source disappeared after prior verified capture', preserved_from_snapshot=prior_snapshot.name)
            else:
                e['error'] = type(ex).__name__
    write(snap / 'manifest.json', {'workspace': IDENTITY, 'snapshot': stamp, 'files': entries})
    errors = sum(bool(e.get('error')) for e in entries)
    if not errors:
        write(ARCHIVE / 'current.json', {'snapshot': stamp})
    emit({'snapshot': stamp, 'files': len(entries), 'bytes': sum(e['bytes'] for e in entries), 'errors': errors})
    return int(bool(errors))
def current():
    assert json.loads((ARCHIVE / 'owner.json').read_text())['workspace'] == IDENTITY
    snap = ARCHIVE / 'snapshots' / json.loads((ARCHIVE / 'current.json').read_text())['snapshot']
    return snap, json.loads((snap / 'manifest.json').read_text(encoding='utf-8'))
def index():
    snap, m = current()
    assert not (snap / 'index.sqlite').exists(), 'Immutable index exists; capture a new snapshot'
    db = sqlite3.connect(snap / 'index.sqlite')
    db.execute('CREATE TABLE records(source, session, line INTEGER, uuid, parent, timestamp, kind, human INTEGER, scope, text)')
    db.execute('CREATE VIRTUAL TABLE search USING fts5(text, content=records, content_rowid=rowid)')
    stats, links, refs, sessions, locations = Counter(), [], [], {}, []
    for e in m['files']:
        p = Path(e['archive_path'])
        original = Path(e['path'])
        if original.suffix == '.jsonl':
            inherited = ''
            for line, o in records(p):
                if o.get('_parse_error'):
                    stats['parse_errors'] += 1
                    continue
                payload = o.get('payload', {})
                inherited = o.get('cwd') or (payload.get('cwd') if isinstance(payload, dict) else None) or inherited
                msg = o.get('message', {})
                kind = o.get('type', 'unknown')
                sid = o.get('sessionId') or e.get('session') or original.stem
                content = msg.get('content', '') if isinstance(msg, dict) else msg
                human = kind == 'user' and (isinstance(content, str) or any(isinstance(b, dict) and b.get('type') == 'text' for b in content if isinstance(content, list)))
                if e['category'] == 'codex-transcript':
                    content = payload.get('content', payload.get('message', payload))
                    human = (kind == 'response_item' and payload.get('role') == 'user') or (kind == 'event_msg' and payload.get('type') == 'user_message')
                    kind = 'codex-' + kind + '-' + str(payload.get('type', payload.get('role', '')))
                if o.get('type') == 'queue-operation':
                    content = o.get('content', o.get('data', o.get('text', '')))
                    human = o.get('operation') == 'enqueue' and bool(content)
                    stats['queue_records'] += 1
                attachment = o.get('attachment', {})
                if isinstance(attachment, dict) and attachment.get('type') == 'queued_command':
                    content = attachment.get('prompt', '')
                    human = attachment.get('humanTurn') is True
                    stats['queued_command_records'] += 1
                if o.get('type') == 'last-prompt':
                    content = o.get('lastPrompt', '')
                    human = False
                    stats['resume_records'] += 1
                text = flatten(content or o)
                if o.get('humanTurn') is False or o.get('isMeta') or o.get('isCompactSummary') or re.fullmatch(r'(?:(?:input_)?text\n)?\s*<task-notification>.*</task-notification>\s*', text, re.S) or 'This session is being continued from a previous conversation' in text[:100] or re.fullmatch(r'(?:text\n)?\[Request interrupted by user(?: for tool use)?\]', text.strip()):
                    human = False
                scope = 'ADM-path-evidence' if path_evidence(o, inherited) else 'mixed-container-context-not-active-memory'
                db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?)', (e['path'], sid, line, o.get('uuid', ''), o.get('parentUuid', ''), o.get('timestamp', ''), kind, int(human), scope, text))
                stats['records'] += 1
                stats['human_occurrences'] += int(human)
                stats['adm_path_records'] += scope == 'ADM-path-evidence'
                session = sessions.setdefault(sid, {'sources': set(), 'first': '', 'last': '', 'records': 0, 'humans': 0})
                session['sources'].add(e['path'])
                stamp = o.get('timestamp') or ''
                session['first'] = min(filter(None, [session['first'], stamp]), default='')
                session['last'] = max(session['last'], stamp)
                session['records'] += 1
                session['humans'] += int(human)
                def blocks(v):
                    if isinstance(v, dict):
                        if v.get('type') in ('image', 'document', 'tool_result'):
                            stats[v['type'] + '_blocks'] += 1
                            locations.append({'source': e['path'], 'session': sid, 'line': line, 'kind': v['type'], 'archive_path': e['archive_path'], 'container_sha256': e['sha256']})
                        for x in v.values():
                            blocks(x)
                    elif isinstance(v, list):
                        for x in v:
                            blocks(x)
                blocks(o)
                backups = o.get('snapshot', {}).get('trackedFileBackups', {})
                if o.get('type') == 'file-history-delta':
                    backups = {o.get('trackingPath', ''): o.get('backup', {})}
                for old, backup in backups.items():
                    if isinstance(backup, dict):
                        name = backup.get('backupFileName')
                        matches = [x['archive_path'] for x in m['files'] if name and Path(x['path']).name == name and sid in Path(x['path']).parts and x['category'] == 'file-history']
                        resolved_old = os.path.abspath(os.path.join(inherited, old)) if inherited and not os.path.isabs(old) else old
                        links.append({'original_path': old, 'resolved_original_path': resolved_old, 'cwd_evidence': inherited, 'backup_name': name, 'source': e['path'], 'line': line, 'session': sid, 'archive_paths': matches, 'scope': 'ADM' if exact(resolved_old) else 'mixed'})
                for url in re.findall(r'https?://[^\s<>"\)]+', text):
                    refs.append({'source': e['path'], 'line': line, 'url': redact(url), 'status': 'reference only; content not fetched'})
        elif original.suffix in ('.md', '.txt'):
            try:
                text = redact(p.read_text(encoding='utf-8-sig'))
            except UnicodeError:
                continue
            for line, text in enumerate(text.splitlines(), 1):
                db.execute('INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?)', (e['path'], '', line, '', '', '', e['category'], 0, 'historical-document', text))
                stats['document_lines'] += 1
    db.execute("INSERT INTO search(search) VALUES ('rebuild')")
    db.commit()
    db.close()
    write(snap / 'sessions.json', [{'session': s, **v, 'sources': sorted(v['sources'])} for s, v in sessions.items()])
    write(snap / 'file-links.json', links)
    write(snap / 'external-references.json', refs)
    write(snap / 'raw-locations.json', locations)
    write(snap / 'memory-catalog.json', [e for e in m['files'] if e['category'] == 'shared-memory'])
    write(snap / 'index-stats.json', dict(stats))
    write(snap / 'derived-manifest.json', [{'path': str(p), 'sha256': digest(p), 'bytes': p.stat().st_size} for p in snap.iterdir() if p.name != 'manifest.json'])
    emit(dict(stats))
def verify():
    snap, m = current()
    failures, source_failures = [], []
    for e in m['files']:
        for k in ('path', 'archive_path'):
            p = Path(e[k])
            if not p.exists() or p.stat().st_size != e['bytes'] or digest(p) != e['sha256']:
                (source_failures if k == 'path' else failures).append({'path': str(p), 'error': 'missing' if not p.exists() else 'size/hash changed'})
    for e in json.loads((snap / 'derived-manifest.json').read_text()):
        if digest(e['path']) != e['sha256']:
            failures.append({'path': e['path'], 'error': 'derivative hash'})
    a = acl()
    # Descendants inherit only these two SIDs; inspect the actual object ACL too.
    acl(Path(m['files'][0]['archive_path']), False)
    emit({'files': len(m['files']), 'bytes': sum(e['bytes'] for e in m['files']), 'failures': failures, 'source_failures': source_failures, 'acl': a, 'archive_ok': not failures, 'ok': not failures and not source_failures})
    return int(bool(failures or source_failures))
def query(a):
    snap, m = current()
    if a.command == 'resolve':
        hits = [e for e in m['files'] if norm(a.value) in norm(e['path'])]
        links = [e for e in json.loads((snap / 'file-links.json').read_text(encoding='utf-8')) if norm(a.value) in norm(e['original_path']) or norm(a.value) in norm(e.get('resolved_original_path', ''))]
        emit({'files': hits, 'revisions': links[:a.limit], 'revision_count': len(links)})
        return 0 if hits or links else 1
    if a.command == 'sessions':
        emit(json.loads((snap / 'sessions.json').read_text()))
        return 0
    if a.command == 'locations':
        rows = [r for r in json.loads((snap / 'raw-locations.json').read_text(encoding='utf-8')) if a.value in r['kind'] and a.session in r['session']]
        emit({'matches': len(rows), 'locations': rows[:a.limit]})
        return 0 if rows else 1
    db = sqlite3.connect((snap / 'index.sqlite').as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    if a.command == 'search':
        rows = db.execute('SELECT r.* FROM records r JOIN search s ON r.rowid=s.rowid WHERE search MATCH ? AND session LIKE ? ORDER BY timestamp, source, line LIMIT ?', (a.value, '%' + a.session + '%', a.limit)).fetchall()
    elif a.command == 'humans':
        order = 'DESC' if a.latest else 'ASC'
        rows = db.execute(f'SELECT * FROM records WHERE human=1 AND session LIKE ? ORDER BY timestamp {order}, source, line {order} LIMIT ?', ('%' + a.value + '%', a.limit)).fetchall()
    else:
        rows = db.execute('SELECT * FROM records WHERE source=? AND line BETWEEN ? AND ? ORDER BY line', (a.source or a.value, a.line - a.context, a.line + a.context)).fetchall()
    out = [dict(r) for r in rows]
    for r in out:
        if a.command == 'open':
            e = next(e for e in m['files'] if e['path'] == r['source'])
            assert digest(e['archive_path']) == e['sha256']
            with Path(e['archive_path']).open('rb') as f:
                raw = next(v for n, v in enumerate(f, 1) if n == r['line'])
            r.update(archive_path=e['archive_path'], raw_line_sha256=hashlib.sha256(raw).hexdigest(), raw_record_opened=True)
        elif len(r['text']) > 1800:
            r['text'] = r['text'][:1800] + '[preview; open exact source for full sanitized text]'
    emit(out)
    return 0 if out else 1
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['discover', 'capture', 'index', 'verify', 'search', 'humans', 'open', 'resolve', 'sessions', 'locations'])
    p.add_argument('value', nargs='?', default='')
    p.add_argument('--line', type=int, default=1)
    p.add_argument('--context', type=int, default=0)
    p.add_argument('--limit', type=int, default=10)
    p.add_argument('--source', default='')
    p.add_argument('--session', default='')
    p.add_argument('--latest', action='store_true')
    a = p.parse_args()
    try:
        if a.command in ('discover', 'capture', 'index', 'verify'):
            return globals()[a.command]() or 0
        return query(a)
    except (OSError, ValueError, AssertionError, sqlite3.Error, subprocess.CalledProcessError, StopIteration) as e:
        emit({'error': type(e).__name__, 'detail': redact(str(e))})
        return 2
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
