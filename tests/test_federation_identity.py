"""The control the src migration deleted, replaced by one that cannot rot silently.

Before the migration, `.github/workflows/query-ci.yml` asserted inline that
`research_query.py` was exactly 5577 bytes / 54105dcd... . The migration turned that
file into a 541-byte compatibility wrapper AND removed the assertion in the same
change, so nothing reported the transition.

Restoring a pin on 5577 bytes would be false -- the wrapper really is 541 now. So
this pins the CURRENT identity, reads both identities from
`portable/FEDERATION_IDENTITY_TRANSITION.json`, and additionally asserts the part
that actually matters across repositories: the four names
`trial/federation/test_federation.py` imports from the wrapper.

Scientific effect NONE. A byte identity is custody, not correctness, currentness or
acceptance, and nothing here reads or moves a claim status.
"""
from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'portable/FEDERATION_IDENTITY_TRANSITION.json'


def record() -> dict:
    return json.loads(RECORD.read_text(encoding='utf-8'))


class FederationIdentity(unittest.TestCase):
    def test_transition_record_exists_and_denies_scientific_authority(self):
        data = record()
        self.assertFalse(data['scientific_status_authority'])
        self.assertEqual(data['scientific_effect'], 'NONE')
        self.assertEqual(data['subject'], {'repository': 'query-', 'path': 'research_query.py'})

    def test_current_wrapper_identity_matches_the_record(self):
        """Pins what is true now. Edit the wrapper and this fails, which is the point."""
        data = record()
        raw = (ROOT / 'research_query.py').read_bytes()
        self.assertEqual(len(raw), data['current_identity']['bytes'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), data['current_identity']['sha256'])

    def test_the_superseded_identity_is_preserved_and_is_not_the_current_one(self):
        """The old bytes are recorded, not re-asserted. If these ever coincide the record
        is describing a transition that did not happen."""
        data = record()
        old, new = data['superseded_identity'], data['current_identity']
        self.assertEqual(old['bytes'], 5577)
        self.assertEqual(old['sha256'],
                         '54105dcd723e71b19263afc8f449a7d77b78cec27148f13603f33be7727e6b6b')
        self.assertNotEqual(old['sha256'], new['sha256'])
        self.assertNotEqual(old['bytes'], new['bytes'])

    def test_wrapper_exports_every_name_trial_federation_imports(self):
        """The cross-repository interface. trial/federation/test_federation.py does
        `import research_query as q` and uses exactly these; dropping one breaks another
        repository's suite, which no test inside query- would otherwise notice."""
        import research_query as wrapper
        for name in record()['wrapper_must_export']:
            with self.subTest(name=name):
                self.assertTrue(hasattr(wrapper, name), name)

    def test_the_recorded_canonical_modules_all_exist(self):
        for rel in record()['canonical_implementation_now']:
            with self.subTest(module=rel):
                self.assertTrue((ROOT / rel).is_file(), rel)

    def test_every_downstream_consumer_row_states_an_effect_and_a_reason(self):
        """A consumer listed without a stated effect is an unexamined one."""
        rows = record()['downstream_consumers']
        self.assertGreaterEqual(len(rows), 4)
        for row in rows:
            with self.subTest(consumer=f"{row['repository']}/{row['path']}"):
                self.assertTrue(row.get('effect_of_this_transition'))
                self.assertTrue(len(row.get('reason', '')) > 40)

    def test_the_commit_pinned_replay_consumer_is_recorded_as_unaffected(self):
        """trial/federation/replay.py pins an immutable commit, so the superseded bytes stay
        reachable there forever. If a future edit repoints that pin at a branch tip instead,
        this record becomes wrong and should fail review, not pass quietly."""
        rows = {f"{r['repository']}/{r['path']}": r for r in record()['downstream_consumers']}
        row = rows['trial/federation/replay.py']
        self.assertEqual(row['effect_of_this_transition'], 'NONE')
        self.assertEqual(len(row['pins']['commit']), 40)
        self.assertEqual(row['pins']['sha256'], record()['superseded_identity']['sha256'])


if __name__ == '__main__':
    unittest.main()
