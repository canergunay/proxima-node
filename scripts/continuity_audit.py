"""Safe metadata inventory; never prints arbitrary configuration keys or values."""
import json
from pathlib import Path
import re
import subprocess
import sys
import sqlite3
sys.dont_write_bytecode = True
from continuity import HOME, ROOT, ARCHIVE, norm, records, write, emit, current, redact

def main():
    if '--include-reference-gaps' in sys.argv:
        snap, _ = current()
        report = json.loads((snap / 'verification.json').read_text(encoding='utf-8'))
        discovery = json.loads((ARCHIVE / 'discovery.json').read_text(encoding='utf-8'))
        seen = {norm(e['path']) for e in discovery['sources']}
        added = []
        for r in report['unarchived_structured_local_references']:
            p = Path(r['path'])
            if r['exists'] and r['ADM'] and norm(p) not in seen:
                discovery['sources'].append({'path': str(p), 'category': 'referenced-workspace-artifact', 'session': None, 'bytes': p.stat().st_size, 'evidence': {'source': r['source'], 'line': r['line'], 'relation': 'structured file reference in exact ADM workspace'}})
                seen.add(norm(p))
                added.append(str(p))
        write(ARCHIVE / 'discovery.json', discovery)
        emit({'added_paths': added})
        return
    if '--gap-summary' in sys.argv:
        snap, _ = current()
        report = json.loads((snap / 'verification.json').read_text(encoding='utf-8'))
        emit({'existing_unarchived_ADM_paths': sorted({r['path'] for r in report['unarchived_structured_local_references'] if r['exists'] and r['ADM']})})
        return
    if '--resume' in sys.argv:
        snap, _ = current()
        db = sqlite3.connect((snap / 'index.sqlite').as_uri() + '?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        emit([dict(r) for r in db.execute("SELECT source, session, line, timestamp, kind, text FROM records WHERE human=1 AND scope='ADM-path-evidence' ORDER BY timestamp DESC LIMIT 12")])
        return
    if '--capture-errors' in sys.argv:
        last = sorted((ARCHIVE / 'snapshots').iterdir())[-1]
        obj = json.loads((last / 'manifest.json').read_text(encoding='utf-8'))
        emit([{'path': e['path'], 'error': e['error']} for e in obj['files'] if e.get('error')])
        return
    if '--review-memory' in sys.argv:
        _, manifest = current()
        names = {'MEMORY.md', 'team-working-method.md', 'direct-profiles-design.md', 'direct-profiles-where-we-left-off.md', 'proximavpn-provisioning.md', 'portal-peer-not-found-name-vs-id.md', 'per-site-exit-keys.md', 'proxima-agent-tls-accept-hang.md'}
        only = sys.argv[sys.argv.index('--only') + 1] if '--only' in sys.argv else None
        for e in manifest['files']:
            name = Path(e['path']).name
            if e['category'] == 'shared-memory' and (name == only if only else name.startswith('adm-') or name in names):
                text = redact(Path(e['archive_path']).read_text(encoding='utf-8-sig'))
                print('\nSOURCE: ' + e['path'])
                print('\n'.join(f'{n}: {s}' for n, s in enumerate(text.splitlines(), 1)))
        return
    safe = {'$schema', 'mcpServers', 'hooks', 'permissions', 'model', 'provider', 'plugin', 'instructions', 'enabledPlugins'}
    configs = []
    for p in [HOME / '.config/opencode/opencode.json', HOME / '.config/opencode/opencode.jsonc', HOME / '.claude/settings.json', ROOT / '.claude/settings.json', ROOT / '.claude/settings.local.json', ROOT / '.codex/config.toml']:
        item = {'path': str(p), 'exists': p.exists()}
        if p.exists() and p.suffix in ('.json', '.jsonc'):
            try:
                obj = json.loads(p.read_text(encoding='utf-8-sig'))
                item.update(safe_keys=sorted(safe.intersection(obj)), top_level_count=len(obj))
            except ValueError:
                item['parse'] = 'not plain JSON; values not inspected'
        configs.append(item)
    codex = []
    for p in (HOME / '.codex/sessions').rglob('*.jsonl'):
        o = next(records(p), (0, {}))[1]
        payload = o.get('payload', {})
        source = payload.get('source')
        codex.append({'path': str(p), 'record_type': o.get('type'), 'cwd': payload.get('cwd'), 'id': payload.get('id'), 'source_shape': type(source).__name__, 'source_safe_fields': sorted(set(source).intersection({'path', 'session_id', 'sessionId', 'type', 'source_path', 'claude_session_id'})) if isinstance(source, dict) else [], 'known_metadata_fields': sorted(set(payload).intersection({'cwd', 'id', 'source', 'originator', 'forked_from_id', 'git'}))})
    remote = subprocess.check_output(['git', 'config', '--get', 'remote.origin.url'], cwd=ROOT, text=True).strip()
    # Emit only a validated GitHub owner/repository pair, never a URL.
    match = re.search(r'github\.com[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$', remote)
    imports = []
    safe_import_keys = {'version', 'imports', 'sessions', 'source', 'source_path', 'sourcePath', 'sourceSessionId', 'session_id', 'sessionId', 'thread_id', 'threadId', 'rollout_path', 'rolloutPath', 'external_session_id', 'externalSessionId'}
    for p in [HOME / '.codex/external_agent_session_imports.json', HOME / '.codex/claude-cowork-import-history.json']:
        if p.exists():
            obj = json.loads(p.read_text(encoding='utf-8'))
            shapes = []
            def walk(v):
                if isinstance(v, dict):
                    source_path = v.get('source_path')
                    if isinstance(source_path, str) and source_path.lower().endswith('.jsonl') and 'proxima' in source_path.lower():
                        imports.append({'source_path': source_path, 'uuid_values': [x for x in v.values() if isinstance(x, str) and re.fullmatch(r'[0-9a-f-]{36}', x)]})
                    shape = sorted(set(v).intersection(safe_import_keys))
                    if shape and shape not in shapes:
                        shapes.append(shape)
                    for x in v.values():
                        walk(x)
                elif isinstance(v, list):
                    for x in v:
                        walk(x)
            walk(obj)
            imports.append({'path': str(p), 'shape': type(obj).__name__, 'count': len(obj), 'safe_shapes': shapes})
    result = {'root': str(ROOT), 'git_root': subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT, text=True).strip(), 'repository': '/'.join(match.groups()) if match else 'not emitted', 'configs': configs, 'codex': codex, 'imports': imports}
    write(ARCHIVE / 'audit.json', result)
    emit({'root': result['root'], 'repository': result['repository'], 'configs': configs, 'codex_count': len(codex), 'imports': imports})
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
