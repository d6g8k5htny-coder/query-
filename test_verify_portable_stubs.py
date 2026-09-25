"""Controls for verify_portable_stubs.py (offline-safe unit checks)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import verify_portable_stubs as v

ROOT = Path(__file__).resolve().parent


class VerifyPortableStubs(unittest.TestCase):
    def test_load_candidates_includes_replay(self):
        keys = {row['key'] for row in v.load_candidates()}
        self.assertIn('rn-fixed-remote-window-replay', keys)
        self.assertIn('p15-price-budget-replay', keys)
        self.assertIn('downstream-hard-gate', keys)

    def test_validate_row_rejects_mutable_commit(self):
        row = {
            'repository': 'Math-',
            'visibility': 'public',
            'commit': 'main',
            'sha256': 'a' * 64,
            'path': 'x.py',
            'bytes': 1,
            'key': 'x',
        }
        with self.assertRaises(SystemExit):
            v.validate_row(row)

    def test_cli_skip(self):
        env = dict(__import__('os').environ)
        env['QUERY_STUB_VERIFY'] = '0'
        proc = subprocess.run(
            [sys.executable, '-B', '-S', str(ROOT / 'verify_portable_stubs.py')],
            capture_output=True, text=True, timeout=10, check=False, env=env,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn('SKIPPED_STUB_VERIFY', proc.stdout)

    def test_fetch_match(self):
        row = {
            'key': 't',
            'repository': 'Math-',
            'visibility': 'public',
            'commit': '1' * 40,
            'path': 'frontiers/x.py',
            'bytes': 4,
            'sha256': __import__('hashlib').sha256(b'data').hexdigest(),
        }
        v.validate_row(row)
        with mock.patch.object(v, 'fetch', return_value=b'data'):
            # exercise main path via temporary candidate list
            with mock.patch.object(v, 'load_candidates', return_value=[row]):
                self.assertEqual(v.main(), 0)


if __name__ == '__main__':
    unittest.main()
