"""Build a public catalog artifact stub from local bytes; no network or acceptance.

Usage:
  python catalog_entry_helper.py --file ../Math-/frontiers/remote_window_20260924/run_validation.py \\
    --repository Math- --path frontiers/remote_window_20260924/run_validation.py \\
    --key rn-fixed-remote-window-replay \\
    --scope 'Same-author finite algebra/implementation checks; not numerical Gaussian integration'

The printed object is a candidate registry entry. It does not edit meta-framework,
prove currentness, or determine scientific acceptance. Commit must be an exact
40-character SHA; omit --commit only when git can resolve the file's last commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


class HelperError(ValueError):
    pass


PUBLIC_REPOS = {
    'Math-',
    'google-drive',
    'governance-',
    'main',
    'meta-framework',
    'query-',
    'trial',
}


def valid_repo_path(text: str) -> PurePosixPath:
    if not isinstance(text, str) or not text or '\\' in text or ':' in text:
        raise HelperError('unsafe path')
    path = PurePosixPath(text)
    if not path.parts or path.is_absolute() or '..' in path.parts or str(path) != text:
        raise HelperError('unsafe path')
    if path.parts[0] == 'sandbox' or any(part == 'sandbox' for part in path.parts):
        raise HelperError('private sandbox path refused')
    return path


def read_public_bytes(path: Path) -> bytes:
    if path.is_symlink():
        raise HelperError('symlink payload refused')
    if not path.is_file():
        raise HelperError('missing payload file')
    resolved = path.resolve()
    if resolved.is_symlink():
        raise HelperError('symlink payload refused')
    raw = resolved.read_bytes()
    if not 0 <= len(raw) <= 10000000:
        raise HelperError('invalid byte count')
    return raw


def resolve_commit(file_path: Path, explicit: str | None) -> str:
    if explicit is not None:
        if not re.fullmatch('[0-9a-f]{40}', explicit):
            raise HelperError('exact commit required')
        return explicit
    try:
        proc = subprocess.run(
            ['git', '-C', str(file_path.parent), 'log', '-1', '--format=%H', '--', file_path.name],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except OSError as error:
        raise HelperError('git commit lookup failed: ' + str(error)) from error
    commit = (proc.stdout or '').strip()
    if proc.returncode != 0 or not re.fullmatch('[0-9a-f]{40}', commit):
        raise HelperError('exact commit required; pass --commit or use a git-tracked file')
    return commit


def build_entry(
    *,
    file_path: Path,
    repository: str,
    repo_path: str,
    key: str,
    scope: str,
    commit: str | None,
) -> dict:
    if repository not in PUBLIC_REPOS:
        raise HelperError('repository not allowed for public catalog stubs')
    if repository == 'sandbox':
        raise HelperError('private sandbox path refused')
    if not isinstance(key, str) or not key or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', key):
        raise HelperError('invalid artifact key')
    if not isinstance(scope, str) or not scope.strip():
        raise HelperError('exact scope required')
    rel = valid_repo_path(repo_path)
    raw = read_public_bytes(file_path)
    return {
        'bytes': len(raw),
        'commit': resolve_commit(file_path, commit),
        'key': key,
        'path': str(rel),
        'repository': repository,
        'scope': scope.strip(),
        'sha256': hashlib.sha256(raw).hexdigest(),
        'visibility': 'public',
        'catalog_is_not_acceptance': True,
        'meaning': 'candidate public identity stub; not catalog integration or theorem acceptance',
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', required=True, type=Path)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--path', required=True, help='repository-relative POSIX path')
    parser.add_argument('--key', required=True)
    parser.add_argument('--scope', required=True)
    parser.add_argument('--commit', help='exact 40-character commit; otherwise git log -1')
    args = parser.parse_args(argv)
    try:
        entry = build_entry(
            file_path=args.file,
            repository=args.repository,
            repo_path=args.path,
            key=args.key,
            scope=args.scope,
            commit=args.commit,
        )
        print(json.dumps(entry, indent=2, sort_keys=True))
    except (OSError, ValueError, TypeError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
