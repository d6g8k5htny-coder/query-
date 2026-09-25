"""Verify portable candidate stubs against exact public GitHub raw bytes.

Uses only declared commits/paths from portable/*.json. Network read of public
raw.githubusercontent.com content; no private sandbox fetch, no catalog edit,
no scientific acceptance. Skip offline with QUERY_STUB_VERIFY=0.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUBLIC_REPOS = {
    'Math-', 'google-drive', 'governance-', 'main', 'meta-framework', 'query-', 'trial',
}


def load_candidates() -> list[dict]:
    rows = []
    single = ROOT / 'portable/RN_FIXED_REMOTE_REPLAY_STUB.json'
    if single.is_file():
        rows.append(json.loads(single.read_text()))
    for bundle_path in sorted((ROOT / 'portable').glob('CANDIDATE_*.json')):
        data = json.loads(bundle_path.read_text())
        if data.get('scientific_status_authority') is not False:
            raise SystemExit('REFUSED: candidate bundle must deny scientific authority: ' + bundle_path.name)
        rows.extend(data['artifacts'])
    # de-dupe by key, prefer first
    seen = set()
    out = []
    for row in rows:
        key = row['key']
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def validate_row(row: dict) -> None:
    if row.get('repository') not in PUBLIC_REPOS:
        raise SystemExit('REFUSED: non-public repository in stub: ' + str(row.get('repository')))
    if row.get('visibility') != 'public':
        raise SystemExit('REFUSED: stub visibility must be public')
    if not re.fullmatch('[0-9a-f]{40}', row.get('commit', '')):
        raise SystemExit('REFUSED: exact commit required for ' + row.get('key', '?'))
    if not re.fullmatch('[0-9a-f]{64}', row.get('sha256', '')):
        raise SystemExit('REFUSED: exact sha256 required for ' + row.get('key', '?'))
    path = row.get('path', '')
    if not path or '\\' in path or ':' in path or '..' in path.split('/') or path.startswith('/'):
        raise SystemExit('REFUSED: unsafe path for ' + row.get('key', '?'))
    if type(row.get('bytes')) is not int or not 0 <= row['bytes'] <= 10000000:
        raise SystemExit('REFUSED: invalid bytes for ' + row.get('key', '?'))


def fetch(row: dict) -> bytes:
    url = (
        f"https://raw.githubusercontent.com/d6g8k5htny-coder/"
        f"{row['repository']}/{row['commit']}/{row['path']}"
    )
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read(row['bytes'] + 1)


def main() -> int:
    if os.environ.get('QUERY_STUB_VERIFY', '1') == '0':
        print('SKIPPED_STUB_VERIFY')
        return 0
    checked = []
    for row in load_candidates():
        validate_row(row)
        try:
            raw = fetch(row)
        except urllib.error.URLError as error:
            print('REFUSED: fetch failed for ' + row['key'] + ': ' + str(error), file=sys.stderr)
            return 2
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            print('REFUSED: identity mismatch for ' + row['key'], file=sys.stderr)
            return 2
        checked.append(row['key'])
    print(json.dumps({
        'verified': checked,
        'meaning': 'exact public bytes at declared commits only; not catalog land or theorem acceptance',
    }, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
