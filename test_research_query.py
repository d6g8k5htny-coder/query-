"""Local engineering controls for research_query.py (no sibling checkout)."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import research_query as q

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'research_query.py'


class ResearchQuery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'Math-').mkdir()
        (self.root / 'Math-/proof.txt').write_bytes(b'candidate\n')
        self.data = {
            'schema_version': 1,
            'scientific_status_authority': False,
            'repositories': {
                'Math-': {
                    'full_name': 'd6g8k5htny-coder/Math-',
                    'visibility': 'public',
                },
                'sandbox': {
                    'full_name': 'd6g8k5htny-coder/sandbox',
                    'visibility': 'private',
                },
            },
            'artifacts': [{
                'key': 'p',
                'repository': 'Math-',
                'path': 'proof.txt',
                'commit': '0' * 40,
                'visibility': 'public',
                'bytes': 10,
                'sha256': hashlib.sha256(b'candidate\n').hexdigest(),
                'scope': 'synthetic test candidate, not acceptance',
            }],
        }
        self.path = self.root / 'catalog.json'

    def load(self, data=None):
        self.path.write_text(json.dumps(self.data if data is None else data))
        return q.load_catalog(self.path)

    def reject_field(self, key, value):
        self.data['artifacts'][0][key] = value
        with self.assertRaises(q.CatalogError):
            self.load()

    def test_valid_lookup(self):
        self.assertTrue(q.lookup(self.load(), 'p')['catalog_is_not_acceptance'])

    def test_unknown_key(self):
        with self.assertRaisesRegex(q.CatalogError, 'UNKNOWN_KEY'):
            q.lookup(self.load(), 'not-known')

    def test_exact_bytes(self):
        self.assertEqual(q.verify(self.load(), self.root)['verified'], ['p'])

    def test_changed_same_length(self):
        data = self.load()
        (self.root / 'Math-/proof.txt').write_bytes(b'altered!!\n')
        with self.assertRaisesRegex(q.CatalogError, 'hash mismatch'):
            q.verify(data, self.root)

    def test_missing_payload(self):
        data = self.load()
        (self.root / 'Math-/proof.txt').unlink()
        with self.assertRaises(q.CatalogError):
            q.verify(data, self.root)

    def test_symlink(self):
        data = self.load()
        (self.root / 'outside').write_bytes(b'candidate\n')
        (self.root / 'Math-/proof.txt').unlink()
        (self.root / 'Math-/proof.txt').symlink_to(self.root / 'outside')
        with self.assertRaisesRegex(q.CatalogError, 'symlink'):
            q.verify(data, self.root)

    def test_private_repository(self):
        self.reject_field('repository', 'sandbox')

    def test_private_artifact(self):
        self.reject_field('visibility', 'private')

    def test_traversal(self):
        self.reject_field('path', '../sandbox/private.txt')

    def test_empty_path(self):
        self.reject_field('path', '.')

    def test_mutable_ref(self):
        self.reject_field('commit', 'main')

    def test_hash_required(self):
        self.reject_field('sha256', 'not-a-hash')

    def test_bool_size(self):
        self.reject_field('bytes', True)

    def test_duplicate_artifact_key(self):
        self.data['artifacts'].append(copy.deepcopy(self.data['artifacts'][0]))
        with self.assertRaises(q.CatalogError):
            self.load()

    def test_duplicate_json_key(self):
        self.path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(q.CatalogError, 'duplicate JSON'):
            q.load_catalog(self.path)

    def test_no_scientific_authority(self):
        self.data['scientific_status_authority'] = True
        with self.assertRaises(q.CatalogError):
            self.load()

    def test_bad_schema_types(self):
        for data in (
            [],
            {'schema_version': True},
            dict(self.data, repositories={'Math-': 'bad'}),
            dict(self.data, artifacts=['bad']),
        ):
            with self.assertRaises(q.CatalogError):
                self.load(data)

    def test_wrong_owner(self):
        self.data['repositories']['Math-']['full_name'] = 'outsider/Math-'
        with self.assertRaises(q.CatalogError):
            self.load()

    def test_cli_list_and_lookup(self):
        self.load()
        listed = subprocess.run(
            [sys.executable, '-B', '-S', str(CLI), '--registry', str(self.path)],
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(listed.returncode, 0)
        payload = json.loads(listed.stdout)
        self.assertFalse(payload['scientific_status_authority'])
        self.assertEqual(payload['keys'], ['p'])
        hit = subprocess.run(
            [sys.executable, '-B', '-S', str(CLI), '--registry', str(self.path), '--key', 'p'],
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(hit.returncode, 0)
        self.assertTrue(json.loads(hit.stdout)['catalog_is_not_acceptance'])

    def test_cli_refusal_is_clean(self):
        self.load()
        proc = subprocess.run(
            [sys.executable, '-B', '-S', str(CLI), '--registry', str(self.path), '--key', 'missing'],
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn('UNKNOWN_KEY', proc.stderr)
        self.assertNotIn('Traceback', proc.stderr)

    def test_cli_verify(self):
        self.load()
        proc = subprocess.run(
            [
                sys.executable, '-B', '-S', str(CLI),
                '--registry', str(self.path),
                '--verify', '--workspace', str(self.root),
            ],
            capture_output=True, text=True, timeout=10, check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)['verified'], ['p'])


if __name__ == '__main__':
    unittest.main()
