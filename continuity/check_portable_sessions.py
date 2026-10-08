"""Test a relocated session package against an isolated native OpenCode store.

Only disposable test copies/data are written outside this project. No models,
historical tools, live session imports or global configuration are invoked.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
import sessions as portable


def run(command, cwd, env):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                            encoding='utf-8', timeout=120)
    if result.returncode:
        raise RuntimeError(f'Isolated command failed (exit {result.returncode}); captured contents not emitted.')
    return result.stdout


def main():
    base = Path(tempfile.mkdtemp(prefix='proxima-portable-', dir=Path(os.environ['LOCALAPPDATA']) / 'Temp/opencode'))
    copied = base / 'different user project folder'
    (copied / 'continuity').mkdir(parents=True)
    shutil.copy2(portable.ROOT / 'continuity/sessions.py', copied / 'continuity/sessions.py')
    shutil.copytree(portable.STORE, copied / 'continuity/sessions', ignore=shutil.ignore_patterns('restore'))
    env = os.environ.copy()
    for variable, folder in [('XDG_DATA_HOME', 'data'), ('XDG_CONFIG_HOME', 'config'),
                             ('XDG_CACHE_HOME', 'cache'), ('XDG_STATE_HOME', 'state'),
                             ('APPDATA', 'roaming'), ('LOCALAPPDATA', 'local'),
                             ('HOME', 'home'), ('USERPROFILE', 'home')]:
        path = base / folder
        path.mkdir(exist_ok=True)
        env[variable] = str(path)
    # Offline/provider-free operations must work with no tools on PATH.
    minimal = env | {'PATH': ''}
    script = str(copied / 'continuity/sessions.py')
    verified = json.loads(run([sys.executable, '-B', script, 'verify'], copied, minimal))
    assert verified['ok'] and verified['sessions'] > 0
    original = portable.catalog()['sessions'][-1]
    prepared = json.loads(run([sys.executable, '-B', script, 'prepare', original['key']], copied, minimal))
    data = json.loads(Path(prepared['prepared']).read_text(encoding='utf-8'))
    assert data['info']['directory'] == str(copied) and data['info']['projectID'] == 'global'
    original = portable.verified_entry(original['key'])
    assert data['info']['id'] != original['origin_id']
    assert not any(p.get('state', {}).get('status') in ('running', 'pending')
                   for m in data['messages'] for p in m.get('parts', []) if p.get('type') == 'tool')
    binary = portable.executable()
    paths = run([binary, 'debug', 'paths', '--pure'], copied, env)
    path_map = dict(line.split(None, 1) for line in paths.splitlines() if line.strip())
    for key in ('data', 'config', 'cache', 'state'):
        assert portable.norm(path_map[key]).startswith(portable.norm(base) + '/'), 'Native store isolation failed'
    run([binary, 'import', prepared['prepared'], '--pure'], copied, env)
    listed = json.loads(run([binary, 'session', 'list', '--format', 'json', '--pure'], copied, env))
    restored = next(s for s in listed if s['id'] == prepared['session_id'])
    assert portable.norm(restored['directory']) == portable.norm(copied)
    exported = json.loads(run([binary, 'export', restored['id'], '--pure'], copied, env))
    assert len(exported['messages']) == len(data['messages'])
    assert [m['info']['id'] for m in exported['messages']] == [m['info']['id'] for m in data['messages']], 'Conversation order changed on import'
    texts = lambda value: {p['id']: p['text'] for m in value['messages'] for p in m['parts'] if p.get('type') == 'text'}
    assert texts(exported) == texts(data)
    assert any(len(t) > 100 and not t.startswith('[redacted:') for t in texts(data).values())
    assert 'canary_value' not in portable.conversation_text('password=canary_value')
    again = json.loads(run([sys.executable, '-B', script, 'restore', original['key']], copied, env))
    assert again['already_present'] and not again['imported']
    # A corrupt copy must fail rather than being imported as a valid snapshot.
    damaged = copied / 'continuity/sessions' / original['transcript']
    with damaged.open('ab') as stream:
        stream.write(b'\nSynthetic test-only corruption\n')
    rejected = subprocess.run([sys.executable, '-B', script, 'verify'], cwd=copied,
                              env=minimal, capture_output=True, timeout=30)
    assert rejected.returncode == 2
    result = {'project': portable.ROOT.name, 'checked_utc': datetime.now(timezone.utc).isoformat(), 'ok': True,
              'corrupt_copy_rejected': True,
              'visible_conversation_text_roundtrip': True,
              'conversation_order_preserved': True,
              'repeat_restore_did_not_overwrite': True,
              'copied_folder': str(copied), 'provider_free_verify': True,
              'provider_free_prepare': True, 'native_store_isolated': True,
              'native_import_list_reexport': True, 'messages': len(data['messages']),
              'original_session_id': original['origin_id'], 'restored_session_id': restored['id'],
              'inflight_tools_not_reexecuted': True, 'live_store_imported': False,
              'model_invoked': False, 'ui_tab_layout_tested': False}
    target = portable.ROOT / 'continuity/PORTABLE-SESSION-CHECK.json'
    portable.write_json(target, result)
    portable.emit(result)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
