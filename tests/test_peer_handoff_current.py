"""Offline checks for the dated foreground offer, not catalog acceptance."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
KEYS = ['rn-fixed-remote-window-replay', 'p15-price-budget-replay', 'three-fronts-replay']

class CurrentPeerHandoff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.handoff = json.loads((ROOT / 'portable/PEER_HANDOFF.json').read_text())

    def test_current_snapshot_not_historical_open_record(self):
        h = self.handoff
        self.assertEqual(h.get('active_snapshot_field'), 'current_handoff')
        now = h['current_handoff']
        self.assertEqual(now['meta_pr_state'], 'MERGED')
        self.assertEqual(now['meta_merge_commit'], 'd049f3aafee045529b81734e0bbdfc2f1b335e83')
        self.assertEqual(h['legacy_field_scope'], 'HISTORICAL_2026_09_25_NOT_CURRENT_VERIFICATION_OR_AUTHORIZATION')
        self.assertEqual(h['verified_against']['checked_at_utc'], '2026-09-25T18:46:17Z')

    def test_exact_three_key_offer_without_catalog_promotion(self):
        now = self.handoff.get('current_handoff', {})
        self.assertEqual(now.get('offered_keys'), KEYS)
        self.assertEqual(now['candidate_bundle_git_blob'], 'cc546d7672893be11edd9cda525b15d902eed817')
        self.assertEqual(now['catalog_integration'], 'NOT_VERIFIED_IN_THIS_UPDATE')
        self.assertFalse(now['claims_current_gate_alignment'])
        self.assertFalse(now['claims_fresh_research_execution'])

    def test_no_automatic_watch_or_owner_stop_restart(self):
        h = self.handoff
        self.assertIn('foreground', h['next_query_action'].lower())
        now = h.get('current_handoff', {})
        self.assertIs(now.get('automatic_execution_authorized'), False)
        self.assertIs(now['restart_cursor_authorized'], False)
        self.assertEqual(now['owner_stop_date'], '2026-09-27')

    def test_no_scientific_authority(self):
        h = self.handoff
        self.assertFalse(h['scientific_status_authority'])
        self.assertFalse(h['lemma_closed'])
        self.assertEqual(h['scientific_effect'], 'NONE')
        self.assertEqual(h['standing_operating_mode'], 'coordinate_with_peer_models_before_each_action')
        self.assertTrue(h['do_not_wait_on_dylan'])
        self.assertEqual(h['still_pending_after_meta6'], KEYS)

if __name__ == '__main__': unittest.main()
