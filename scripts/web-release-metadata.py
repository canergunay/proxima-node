"""Reduce publisher JSON to validated public diagnostics; never echo raw input."""
import json
import re
import sys


def safe_metadata(raw):
    if len(raw) > 262144:
        raise ValueError('Oversized metadata')
    value = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    if not isinstance(value, dict):
        raise ValueError('Object required')
    result = {}
    for key in ('code', 'error_code', 'status', 'outcome'):
        item = value.get(key)
        if isinstance(item, str) and re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,79}', item):
            result[key] = item
    for key in ('revision', 'ui_revision'):
        item = value.get(key)
        if isinstance(item, str) and re.fullmatch(r'[0-9a-f]{40}', item):
            result[key] = item
    snapshot = value.get('snapshot')
    if (isinstance(snapshot, str) and len(snapshot) <= 1024
            and re.fullmatch(r'/var/lib/proxima-web-releases/[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)*', snapshot)
            and not any(part in ('.', '..') for part in snapshot.split('/'))):
        result['snapshot'] = snapshot
    for key in ('evidence_path', 'rollback_path', 'snapshot_path', 'snapshots_path',
                'snapshot_before_path', 'snapshot_after_path', 'durable_path'):
        item = value.get(key)
        if (isinstance(item, str) and len(item) <= 1024
                and re.fullmatch(r'/(?:[a-zA-Z0-9_.-]+/)*[a-zA-Z0-9_.-]+', item)
                and not any(part in ('.', '..') for part in item.split('/'))):
            result[key] = item
    # Full publisher snapshots stay in private evidence; do not serialize unknown fields.
    if not result:
        raise ValueError('No recognized safe metadata')
    return result


if __name__ == '__main__':
    try:
        print(json.dumps(safe_metadata(sys.stdin.read(262145)), sort_keys=True))
    except Exception:
        print(json.dumps({'error_code': 'publisher_metadata_invalid'}))
        sys.exit(1)
