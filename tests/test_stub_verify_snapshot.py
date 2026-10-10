"""Downstream bundle snapshot identity, separate from byte equality or tip drift."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from universal_law_query import stub_verify as verifier

# Synthetic immutable-reference shapes; no existence or live snapshot claim.
SNAPSHOT = 'a' * 40
OLDER = 'b' * 40
PAYLOAD = b'unchanged README bytes\n'
BUNDLE = 'CANDIDATE_DOWNSTREAM_GATE_STUBS.json'


def row(key, commit=SNAPSHOT):
    return {
        'key': key, 'repository': 'Math-', 'visibility': 'public',
        'commit': commit, 'path': 'frontiers/example/' + key + '.md',
        'bytes': len(PAYLOAD), 'sha256': hashlib.sha256(PAYLOAD).hexdigest(),
    }


class DownstreamSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.portable = self.root / 'portable'
        self.portable.mkdir()

    def write_bundle(self, data, name=BUNDLE):
        (self.portable / name).write_text(json.dumps(data), encoding='utf-8')

    def bundle(self, tip=SNAPSHOT):
        return {'scientific_status_authority': False, 'math_tip': tip,
                'artifacts': [row('first', tip), row('readme', tip)]}

    def test_coherent_current_and_historical_snapshots_are_valid(self):
        # No hardcoded current main requirement: each coherent snapshot is valid.
        for tip in (SNAPSHOT, OLDER):
            with self.subTest(tip=tip):
                data = self.bundle(tip)
                self.write_bundle(data)
                self.assertEqual(verifier.load_candidates(self.root), data['artifacts'])
                result = verifier.check_math_tip_drift(
                    self.root, fetch_raw_fn=lambda *args: PAYLOAD)
                self.assertEqual(result['math_tip_recorded'], tip)
                self.assertEqual(result['checked'], ['first', 'readme'])
                self.assertEqual(result['drifted'], [])

    def test_same_bytes_at_different_commit_are_rejected_by_loader(self):
        data = self.bundle()
        # Alter only the second row's commit. Digest/length/bytes stay correct.
        data['artifacts'][1]['commit'] = OLDER
        self.write_bundle(data)
        with self.assertRaisesRegex(SystemExit, 'REFUSED:.*math_tip'):
            verifier.load_candidates(self.root)

    def test_cli_rejects_mixed_snapshot_before_any_pinned_fetch(self):
        data = self.bundle()
        data['artifacts'][1]['commit'] = OLDER
        self.write_bundle(data)
        fetch = mock.Mock(return_value=PAYLOAD)
        with mock.patch.dict(os.environ, {'QUERY_STUB_VERIFY': '1'}), \
                contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(SystemExit, 'REFUSED:.*math_tip'):
            verifier.main([], load_candidates_fn=lambda: verifier.load_candidates(self.root),
                          fetch_fn=fetch)
        fetch.assert_not_called()

    def test_direct_tip_check_preflights_all_rows_before_any_fetch(self):
        data = self.bundle()
        data['artifacts'][1]['commit'] = OLDER
        self.write_bundle(data)
        fetch = mock.Mock(return_value=PAYLOAD)
        with self.assertRaisesRegex(SystemExit, 'REFUSED:.*math_tip'):
            verifier.check_math_tip_drift(self.root, fetch_raw_fn=fetch)
        fetch.assert_not_called()

    def test_missing_or_malformed_snapshot_is_refused_on_both_paths(self):
        for value in ('MISSING', None, 7, True, [], {}, '', 'main',
                      'a' * 39, 'a' * 41, 'A' * 40, 'G' * 40):
            with self.subTest(value=value):
                data = self.bundle()
                if value == 'MISSING':
                    del data['math_tip']
                else:
                    data['math_tip'] = value
                self.write_bundle(data)
                with self.subTest(entrypoint='loader'):
                    with self.assertRaisesRegex(SystemExit, 'REFUSED:.*math_tip'):
                        verifier.load_candidates(self.root)
                with self.subTest(entrypoint='direct-tip'):
                    fetch = mock.Mock(return_value=PAYLOAD)
                    with self.assertRaisesRegex(SystemExit, 'REFUSED:.*math_tip'):
                        verifier.check_math_tip_drift(self.root, fetch_raw_fn=fetch)
                    fetch.assert_not_called()

    def test_tip_format_is_checked_even_without_rows(self):
        # Commit comparisons cannot substitute for validating the declaration.
        for value in (None, 7, True, [], {}, '', 'main',
                      'a' * 39, 'a' * 41, 'A' * 40, 'G' * 40):
            with self.subTest(value=value):
                self.write_bundle({'scientific_status_authority': False,
                                   'math_tip': value, 'artifacts': []})
                with self.subTest(entrypoint='loader'):
                    with self.assertRaisesRegex(SystemExit, 'REFUSED:.*math_tip'):
                        verifier.load_candidates(self.root)
                with self.subTest(entrypoint='direct-tip'):
                    fetch = mock.Mock(return_value=PAYLOAD)
                    with self.assertRaisesRegex(SystemExit, 'REFUSED:.*math_tip'):
                        verifier.check_math_tip_drift(self.root, fetch_raw_fn=fetch)
                    fetch.assert_not_called()

    def test_empty_coherent_bundle_keeps_existing_behavior(self):
        self.write_bundle({'scientific_status_authority': False,
                           'math_tip': SNAPSHOT, 'artifacts': []})
        self.assertEqual(verifier.load_candidates(self.root), [])
        result = verifier.check_math_tip_drift(
            self.root, fetch_raw_fn=lambda *args: self.fail('unexpected fetch'))
        self.assertEqual(result['checked'], [])
        self.assertEqual(result['drifted'], [])
        self.assertEqual(result['math_tip_recorded'], SNAPSHOT)

    def test_other_repository_commit_is_not_bound_to_math_snapshot(self):
        data = self.bundle()
        data['artifacts'][1]['repository'] = 'main'
        data['artifacts'][1]['commit'] = OLDER
        self.write_bundle(data)
        self.assertEqual(verifier.load_candidates(self.root), data['artifacts'])
        result = verifier.check_math_tip_drift(self.root, fetch_raw_fn=lambda *args: PAYLOAD)
        self.assertEqual(result['drifted'], [])

    def test_duplicate_key_does_not_hide_inconsistent_snapshot(self):
        data = self.bundle()
        data['artifacts'][1]['key'] = 'first'
        data['artifacts'][1]['commit'] = OLDER
        self.write_bundle(data)
        with self.assertRaisesRegex(SystemExit, 'REFUSED:.*math_tip'):
            verifier.load_candidates(self.root)

    def test_current_checkout_retains_ten_unique_candidate_keys(self):
        keys = [item['key'] for item in verifier.load_candidates(ROOT)]
        self.assertEqual(len(keys), 10)
        self.assertEqual(len(set(keys)), 10)
        self.assertIn('downstream-hard-gate', keys)
        self.assertEqual(keys.count('rn-fixed-remote-window-replay'), 1)

    def test_other_public_and_single_stub_formats_keep_distinct_commits(self):
        public = {'scientific_status_authority': False,
                  'artifacts': [row('public-a', SNAPSHOT), row('public-b', OLDER)]}
        self.write_bundle(public, 'CANDIDATE_PUBLIC_REPLAY_STUBS.json')
        single = row('rn-single', '1' * 40)
        self.write_bundle(single, 'RN_FIXED_REMOTE_REPLAY_STUB.json')
        self.assertEqual(verifier.load_candidates(self.root), [single, *public['artifacts']])
        fetch = mock.Mock(return_value=PAYLOAD)
        self.assertEqual(verifier.check_math_tip_drift(self.root, fetch_raw_fn=fetch),
                         {'checked': [], 'drifted': [], 'math_tip_recorded': None})
        fetch.assert_not_called()

    def test_snapshot_identity_does_not_hide_real_tip_byte_drift(self):
        self.write_bundle(self.bundle())
        result = verifier.check_math_tip_drift(
            self.root, fetch_raw_fn=lambda *args: b'changed current main bytes\n')
        self.assertEqual(result['math_tip_recorded'], SNAPSHOT)
        self.assertEqual([item['key'] for item in result['drifted']], ['first', 'readme'])

    def test_frozen_history_is_not_loaded_as_current_candidate(self):
        self.write_bundle(self.bundle())
        history = self.portable / 'history'
        history.mkdir()
        (history / BUNDLE).write_text('{"historical": "not a current candidate"}')
        self.assertEqual([item['key'] for item in verifier.load_candidates(self.root)],
                         ['first', 'readme'])


if __name__ == '__main__':
    unittest.main()
