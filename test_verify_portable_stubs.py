"""Controls for verify_portable_stubs.py (offline-safe unit checks)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
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
            'sha256': hashlib.sha256(b'data').hexdigest(),
        }
        v.validate_row(row)
        with mock.patch.object(v, 'fetch', return_value=b'data'):
            with mock.patch.object(v, 'load_candidates', return_value=[row]):
                self.assertEqual(v.main([]), 0)

    def _gate_row(self, payload: bytes = b'data'):
        return {
            'key': 'downstream-hard-gate-code',
            'repository': 'Math-',
            'visibility': 'public',
            'commit': '1' * 40,
            'path': 'frontiers/downstream_gate_20260925/hard_gate.py',
            'bytes': len(payload),
            'sha256': hashlib.sha256(payload).hexdigest(),
        }

    def test_math_tip_check_no_drift_when_tip_matches(self):
        payload = b'data'
        fake = {
            'scientific_status_authority': False,
            'math_tip': 'tipsha',
            'artifacts': [self._gate_row(payload)],
        }
        with mock.patch.object(v, 'fetch_raw', return_value=payload):
            with mock.patch.object(Path, 'is_file', return_value=True):
                with mock.patch.object(Path, 'read_text', return_value=json.dumps(fake)):
                    out = v.check_math_tip_drift()
        self.assertEqual(out['drifted'], [])
        self.assertEqual(out['checked'], ['downstream-hard-gate-code'])

    def test_math_tip_check_detects_drift(self):
        fake = {
            'scientific_status_authority': False,
            'math_tip': 'tipsha',
            'artifacts': [self._gate_row(b'data')],
        }
        with mock.patch.object(v, 'fetch_raw', return_value=b'DIFF'):
            with mock.patch.object(Path, 'is_file', return_value=True):
                with mock.patch.object(Path, 'read_text', return_value=json.dumps(fake)):
                    out = v.check_math_tip_drift()
        self.assertEqual(len(out['drifted']), 1)
        self.assertEqual(out['drifted'][0]['key'], 'downstream-hard-gate-code')

    def test_peer_handoff_schema(self):
        handoff = json.loads((ROOT / 'portable/PEER_HANDOFF.json').read_text())
        self.assertFalse(handoff['scientific_status_authority'])
        self.assertFalse(handoff['lemma_closed'])
        self.assertEqual(handoff['scientific_effect'], 'NONE')
        self.assertEqual(handoff['standing_operating_mode'], 'coordinate_with_peer_models_before_each_action')
        self.assertIn('rn-fixed-remote-window-replay', handoff['still_pending_after_meta6'])
        self.assertEqual(handoff['gate_stubs_vs_meta6']['status'], 'aligned_to_meta6_tip_pins')


if __name__ == '__main__':
    unittest.main()
