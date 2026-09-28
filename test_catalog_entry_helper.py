"""Controls for catalog_entry_helper.py (stdlib-only; no network)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import catalog_entry_helper as helper

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'catalog_entry_helper.py'


class CatalogEntryHelper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.payload = self.root / 'run_validation.py'
        self.payload.write_bytes(b'candidate\n')

    def test_build_entry(self):
        entry = helper.build_entry(
            file_path=self.payload,
            repository='Math-',
            repo_path='frontiers/remote_window_20260924/run_validation.py',
            key='rn-fixed-remote-window-replay',
            scope='synthetic stub, not acceptance',
            commit='1' * 40,
        )
        self.assertEqual(entry['bytes'], 10)
        self.assertEqual(entry['sha256'], hashlib.sha256(b'candidate\n').hexdigest())
        self.assertEqual(entry['commit'], '1' * 40)
        self.assertTrue(entry['catalog_is_not_acceptance'])
        self.assertEqual(entry['visibility'], 'public')

    def test_refuse_sandbox_repo(self):
        with self.assertRaisesRegex(helper.HelperError, 'not allowed|sandbox'):
            helper.build_entry(
                file_path=self.payload,
                repository='sandbox',
                repo_path='private.txt',
                key='x',
                scope='no',
                commit='1' * 40,
            )

    def test_refuse_traversal(self):
        with self.assertRaisesRegex(helper.HelperError, 'unsafe path'):
            helper.build_entry(
                file_path=self.payload,
                repository='Math-',
                repo_path='../sandbox/private.txt',
                key='x',
                scope='no',
                commit='1' * 40,
            )

    def test_refuse_symlink(self):
        target = self.root / 'outside'
        target.write_bytes(b'candidate\n')
        link = self.root / 'link.py'
        link.symlink_to(target)
        with self.assertRaisesRegex(helper.HelperError, 'symlink'):
            helper.build_entry(
                file_path=link,
                repository='Math-',
                repo_path='link.py',
                key='x',
                scope='no',
                commit='1' * 40,
            )

    def test_refuse_mutable_commit(self):
        with self.assertRaisesRegex(helper.HelperError, 'exact commit'):
            helper.build_entry(
                file_path=self.payload,
                repository='Math-',
                repo_path='run_validation.py',
                key='x',
                scope='no',
                commit='main',
            )

    def test_cli_prints_stub(self):
        proc = subprocess.run(
            [
                sys.executable, '-B', '-S', str(CLI),
                '--file', str(self.payload),
                '--repository', 'Math-',
                '--path', 'frontiers/remote_window_20260924/run_validation.py',
                '--key', 'rn-fixed-remote-window-replay',
                '--scope', 'synthetic stub, not acceptance',
                '--commit', 'a' * 40,
            ],
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload['key'], 'rn-fixed-remote-window-replay')
        self.assertEqual(payload['bytes'], 10)

    def test_cli_refusal_is_clean(self):
        proc = subprocess.run(
            [
                sys.executable, '-B', '-S', str(CLI),
                '--file', str(self.payload),
                '--repository', 'sandbox',
                '--path', 'private.txt',
                '--key', 'x',
                '--scope', 'no',
                '--commit', 'a' * 40,
            ],
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn('REFUSED:', proc.stderr)
        self.assertNotIn('Traceback', proc.stderr)

    def test_portable_replay_stub_schema(self):
        stub = json.loads((ROOT / 'portable/RN_FIXED_REMOTE_REPLAY_STUB.json').read_text())
        required = {'bytes', 'commit', 'key', 'path', 'repository', 'scope', 'sha256', 'visibility'}
        self.assertTrue(required <= set(stub))
        self.assertEqual(stub['key'], 'rn-fixed-remote-window-replay')
        self.assertEqual(stub['visibility'], 'public')
        self.assertRegex(stub['commit'], r'^[0-9a-f]{40}$')
        self.assertRegex(stub['sha256'], r'^[0-9a-f]{64}$')
        self.assertEqual(stub['bytes'], 4052)

    def test_candidate_replay_bundle_schema(self):
        bundle = json.loads((ROOT / 'portable/CANDIDATE_PUBLIC_REPLAY_STUBS.json').read_text())
        self.assertFalse(bundle['scientific_status_authority'])
        self.assertGreaterEqual(len(bundle['artifacts']), 1)
        keys = {row['key'] for row in bundle['artifacts']}
        self.assertIn('rn-fixed-remote-window-replay', keys)
        for row in bundle['artifacts']:
            self.assertEqual(row['visibility'], 'public')
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['sha256'], r'^[0-9a-f]{64}$')
            self.assertIsInstance(row['bytes'], int)

    def test_candidate_downstream_gate_bundle_schema(self):
        bundle = json.loads((ROOT / 'portable/CANDIDATE_DOWNSTREAM_GATE_STUBS.json').read_text())
        self.assertFalse(bundle['scientific_status_authority'])
        keys = {row['key'] for row in bundle['artifacts']}
        self.assertIn('downstream-hard-gate', keys)
        self.assertIn('downstream-hard-gate-scope', keys)
        self.assertIn('downstream-hard-gate-replay', keys)
        for row in bundle['artifacts']:
            self.assertEqual(row['visibility'], 'public')
            self.assertRegex(row['commit'], r'^[0-9a-f]{40}$')
            self.assertRegex(row['sha256'], r'^[0-9a-f]{64}$')
            self.assertTrue(row['path'].startswith('frontiers/downstream_gate_20260925/'))
        readme = next(r for r in bundle['artifacts'] if r['key'] == 'downstream-hard-gate')
        self.assertEqual(readme['path'], 'frontiers/downstream_gate_20260925/README.md')


if __name__ == '__main__':
    unittest.main()
