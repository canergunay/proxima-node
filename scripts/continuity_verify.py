"""ADM migration checks. No application execution or historical commands.

--record writes only this workspace's private snapshot verification report.
--delivery preserves authored migration files and safe audit metadata separately.
"""
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
sys.dont_write_bytecode = True
import continuity as c

def run(*args, expected=0):
    p = subprocess.run([sys.executable, str(c.ROOT / 'scripts/continuity.py'), *args], cwd=c.ROOT, capture_output=True, encoding='utf-8')
    assert p.returncode == expected, (args[0], p.returncode, expected)
    return json.loads(p.stdout)

def main():
    snap, m = c.current()
    known_missing = [e for e in m['files'] if e.get('source_error')]
    integrity = run('verify', expected=1 if known_missing else 0)
    assert integrity['archive_ok']
    assert {r['path'] for r in integrity['source_failures']} == {e['path'] for e in known_missing}
    assert all(r['error'] == 'missing' for r in integrity['source_failures'])
    assert c.exact(str(c.ROOT / 'adm'))
    assert not c.exact(str(c.ROOT) + '-other')
    assert not c.exact(r'D:\Nextcloud\Projects\proxima')
    assert not c.exact(r'C:\Users\caner\.claude\projects\d--Nextcloud-Projects-proxima')
    marker = 'SYNTHETIC_VALUE_ONLY'
    assert marker not in c.flatten({'api_token': marker, 'nested': {'password': marker}})
    assert marker not in c.flatten(json.dumps({'secret': marker}, indent=2))
    pem = 'a\n-----BEGIN PRIVATE KEY-----\n' + marker + '\n-----END PRIVATE KEY-----\nz'
    assert marker not in c.redact(pem) and len(c.redact(pem).splitlines()) == len(pem.splitlines())
    assert marker not in c.redact('ss://' + marker)
    retrieval = []
    for term, sid in [('SiteGate', '88824aa7-bbbe-47c2-bc5d-d55b7ea5d7d4'), ('userspace', '96ed35d2-52b3-4fbf-aea3-4a5115d1aa12'), ('allowed_profiles', 'b7badd97-87c7-42c0-a6d9-15821cd5f293')]:
        hits = run('search', term, '--session', sid, '--limit', '100')
        hit = next((h for h in hits if h['scope'] == 'ADM-path-evidence'), hits[0])
        opened = run('open', '--source', hit['source'], '--line', str(hit['line']), '--context', '1')
        exact = next(h for h in opened if h['line'] == hit['line'])
        assert exact['raw_record_opened'] and exact['source'] == hit['source']
        assert len(opened) >= 2
        humans = run('humans', sid, '--latest', '--limit', '5')
        assert all(h['human'] == 1 for h in humans)
        retrieval.append({'topic': term, 'session': sid, 'source': hit['source'], 'line': hit['line'], 'raw_line_sha256': exact['raw_line_sha256'], 'context_records': len(opened), 'human_records_checked': len(humans)})
    resolved = run('resolve', str(c.ROOT / 'adm/backend/core/proxima_client.py'), '--limit', '5')
    assert resolved['files'] and resolved['revision_count'] > 0
    run('search', 'zzzz_absent_2e746764', expected=1)
    run('open', '--source', 'zzzz_absent', expected=1)
    run('resolve', 'zzzz_absent', expected=1)
    run('search', '"unterminated', expected=2)
    assert run('locations', 'image', '--limit', '1')['matches'] > 0
    assert run('locations', 'tool_result', '--limit', '1')['matches'] > 0
    # Evaluate actual allow-list on every archive descendant, not display names.
    ps = "$u=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value; $bad=@(); $count=0; Get-ChildItem -LiteralPath '" + str(c.ARCHIVE).replace("'", "''") + "' -Recurse -Force | ForEach-Object { $count++; $a=Get-Acl -LiteralPath $_.FullName; $s=@($a.Access | ForEach-Object {$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value}); if (($s | Sort-Object -Unique).Count -ne 2 -or $s -notcontains $u -or $s -notcontains 'S-1-5-18' -or @($a.Access | Where-Object {$_.AccessControlType -ne 'Allow' -or $_.FileSystemRights -ne 'FullControl'}).Count) {$bad+=$_.FullName} }; @{checked=$count; unexpected=$bad} | ConvertTo-Json -Compress"
    all_acl = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', ps], text=True))
    assert not all_acl['unexpected']
    links = json.loads((snap / 'file-links.json').read_text(encoding='utf-8'))
    missing = [x for x in links if x['backup_name'] and not x['archive_paths']]
    missing_adm = [x for x in missing if x['scope'] == 'ADM']
    sources = {c.norm(e['path']) for e in m['files']}
    ids = {Path(e['path']).stem for e in m['files'] if e['category'] == 'transcript'}
    missing_origins, local_refs, frame_records = [], [], []
    for e in m['files']:
        if e['category'] == 'shared-memory':
            text = Path(e['archive_path']).read_text(encoding='utf-8-sig')
            match = re.search(r'originSessionId:\s*([0-9a-f-]{36})', text)
            if match and match[1] not in ids:
                missing_origins.append({'source': e['path'], 'session': match[1], 'scope': 'ADM-focused' if Path(e['path']).name.startswith('adm-') else 'shared-memory'})
        if Path(e['path']).suffix == '.jsonl':
            def paths(v):
                if isinstance(v, dict):
                    for key, value in v.items():
                        if key in ('file_path', 'filePath', 'path', 'output_file', 'outputFile', 'trackingPath') and isinstance(value, str) and re.match(r'^[A-Za-z]:[\\/]', value):
                            yield value
                        if isinstance(value, (dict, list)):
                            yield from paths(value)
                elif isinstance(v, list):
                    for x in v:
                        yield from paths(x)
            for line, obj in c.records(Path(e['archive_path'])):
                if obj.get('type') == 'frame-link':
                    frame_records.append({'source': e['path'], 'line': line, 'local_path': obj.get('path'), 'url': c.redact(obj.get('frameUrl', '')), 'status': 'reference only; cloud body/comments not captured'})
                for path in paths(obj):
                    if c.norm(path) not in sources:
                        local_refs.append({'source': e['path'], 'line': line, 'path': path, 'exists': Path(path).is_file(), 'ADM': c.exact(path)})
    db = sqlite3.connect((snap / 'index.sqlite').as_uri() + '?mode=ro', uri=True)
    notifications = db.execute("SELECT count(*) FROM records WHERE human=1 AND text LIKE '%<task-notification>%' AND text NOT LIKE '%tool_use%'").fetchone()[0]
    # References embedded in a genuine user's prose may mention this marker;
    # standalone records are tested explicitly.
    for text, in db.execute('SELECT text FROM records WHERE human=1'):
        assert not re.fullmatch(r'(?:(?:input_)?text\n)?\s*<task-notification>.*</task-notification>\s*', text, re.S)
    queue = db.execute("SELECT count(*) FROM records WHERE kind='attachment' AND human=1").fetchone()[0]
    db.close()
    refs = json.loads((snap / 'external-references.json').read_text(encoding='utf-8'))
    frames = frame_records + [r for r in refs if re.search(r'claude\.ai/(?:chat|public/artifacts)|codex\.ai|/canvas|/artifact', r['url'])]
    result = {'snapshot': snap.name, 'integrity': integrity, 'acl_descendants': all_acl, 'retrieval': retrieval, 'exit_code_checks': True, 'redaction_checks': True, 'path_boundary_checks': True, 'revision_resolution_count': resolved['revision_count'], 'human_queued_attachments': queue, 'notification_mentions_in_human_prose': notifications, 'categories': dict(c.Counter(e['category'] for e in m['files'])), 'unique_objects': len({e['sha256'] for e in m['files']}), 'unique_object_bytes': sum({e['sha256']: e['bytes'] for e in m['files']}.values()), 'missing_revision_references': missing, 'missing_ADM_revision_references': missing_adm, 'memory_origin_not_in_attributed_transcripts': missing_origins, 'unarchived_structured_local_references': local_refs, 'external_reference_count': len(refs), 'cloud_artifact_references': frames}
    result['unique_missing_revision_names'] = len({(x['session'], x['backup_name']) for x in missing})
    result['unique_missing_ADM_revision_names'] = len({(x['session'], x['backup_name']) for x in missing_adm})
    result['unique_unarchived_local_paths'] = len({c.norm(x['path']) for x in local_refs})
    result['unique_missing_local_paths'] = len({c.norm(x['path']) for x in local_refs if not x['exists']})
    result['source_matches_now'] = len(m['files']) - len(integrity['source_failures'])
    result['claude_top_level_transcripts'] = sum(e['category'] == 'transcript' and Path(e['path']).parent.parent.name == 'projects' for e in m['files'])
    result['mapped_revision_references'] = sum(bool(x['archive_paths']) for x in links)
    assert result['mapped_revision_references'] > 0
    authored = ['AGENTS.md', 'CONTINUITY.md', 'continuity/HANDOFF.md', 'continuity/MIGRATION.md', 'scripts/continuity.py', 'scripts/continuity_audit.py', 'scripts/continuity_verify.py']
    literal_secret = re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b|^-----BEGIN [A-Z ]*PRIVATE KEY-----', re.M)
    for name in authored:
        assert not literal_secret.search((c.ROOT / name).read_text(encoding='utf-8')), 'Literal secret pattern in authored file'
    subprocess.run(['git', 'diff', '--exit-code', '--quiet'], cwd=c.ROOT, check=True)
    result['authored_literal_secret_scan'] = 'no high-confidence matches; not exhaustive'
    result['tracked_git_diff_empty'] = True
    if '--delivery' in sys.argv:
        delivery = c.ARCHIVE / 'delivery' / c.datetime.now(c.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        delivery.mkdir(parents=True)
        entries = []
        for name in authored:
            source = c.ROOT / name
            target = delivery / name
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            with target.open('xb') as f:
                f.write(data)
            assert c.digest(source) == c.digest(target)
            entries.append({'source': str(source), 'archive_path': str(target), 'bytes': len(data), 'sha256': c.digest(target)})
        c.write(delivery / 'delivery-manifest.json', entries)
        metadata = []
        for name in ('discovery.json', 'audit.json', 'import-provenance.json'):
            source = c.ARCHIVE / name
            target = delivery / ('metadata-' + name)
            data = source.read_bytes()
            with target.open('xb') as f:
                f.write(data)
            assert c.digest(source) == c.digest(target)
            metadata.append({'source': str(source), 'archive_path': str(target), 'bytes': len(data), 'sha256': c.digest(target), 'category': 'migration metadata derivative'})
        c.write(delivery / 'metadata-manifest.json', metadata)
        c.acl(delivery / 'delivery-manifest.json', False)
        result['delivery_manifest'] = str(delivery / 'delivery-manifest.json')
    if '--record' in sys.argv:
        c.write(snap / 'verification.json', result)
    c.emit({k: v for k, v in result.items() if k not in ('missing_revision_references', 'missing_ADM_revision_references', 'memory_origin_not_in_attributed_transcripts', 'unarchived_structured_local_references', 'cloud_artifact_references')} | {'missing_revision_references': len(missing), 'missing_ADM_revision_references': len(missing_adm), 'missing_memory_origin_ids': len({r['session'] for r in missing_origins}), 'missing_ADM_memory_origin_ids': sorted({r['session'] for r in missing_origins if r['scope'] == 'ADM-focused'}), 'unarchived_local_references': len(local_refs), 'cloud_artifact_references': len(frames)})
if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
