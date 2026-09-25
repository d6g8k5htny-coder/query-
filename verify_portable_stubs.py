"""Verify portable candidate stubs against exact public GitHub raw bytes.

Uses only declared commits/paths from portable/*.json. Network read of public
raw.githubusercontent.com content; no private sandbox fetch, no catalog edit,
no scientific acceptance. Skip offline with QUERY_STUB_VERIFY=0.

Pass --check-math-tip to also compare downstream-gate stubs to Math- default
tip bytes (detect tip drift that still verifies against older pinned commits).
"""
from __future__ import annotations

import argparse
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


def fetch_raw(repository: str, ref: str, path: str, max_bytes: int) -> bytes:
    url = f'https://raw.githubusercontent.com/d6g8k5htny-coder/{repository}/{ref}/{path}'
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read(max_bytes + 1)


def fetch(row: dict) -> bytes:
    return fetch_raw(row['repository'], row['commit'], row['path'], row['bytes'])


def check_math_tip_drift() -> dict:
    bundle_path = ROOT / 'portable/CANDIDATE_DOWNSTREAM_GATE_STUBS.json'
    if not bundle_path.is_file():
        return {'checked': [], 'drifted': [], 'math_tip_recorded': None}
    data = json.loads(bundle_path.read_text())
    drifted = []
    checked = []
    for row in data['artifacts']:
        validate_row(row)
        try:
            tip_raw = fetch_raw(row['repository'], 'main', row['path'], 10000000)
        except urllib.error.URLError as error:
            raise SystemExit('REFUSED: tip fetch failed for ' + row['key'] + ': ' + str(error)) from error
        tip_digest = hashlib.sha256(tip_raw).hexdigest()
        checked.append(row['key'])
        if len(tip_raw) != row['bytes'] or tip_digest != row['sha256']:
            drifted.append({
                'key': row['key'],
                'stub_bytes': row['bytes'],
                'tip_bytes': len(tip_raw),
                'stub_sha256': row['sha256'],
                'tip_sha256': tip_digest,
            })
    return {
        'checked': checked,
        'drifted': drifted,
        'math_tip_recorded': data.get('math_tip'),
        'meaning': 'tip drift vs portable stubs only; not catalog land or theorem acceptance',
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--check-math-tip',
        action='store_true',
        help='fail if downstream-gate stubs no longer match Math- default tip bytes',
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
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
    report = {
        'verified': checked,
        'meaning': 'exact public bytes at declared commits only; not catalog land or theorem acceptance',
    }
    if args.check_math_tip:
        tip = check_math_tip_drift()
        report['math_tip_check'] = tip
        if tip['drifted']:
            print(json.dumps(report, indent=2, sort_keys=True))
            print('REFUSED: TIP_DRIFT ' + ','.join(x['key'] for x in tip['drifted']), file=sys.stderr)
            return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
