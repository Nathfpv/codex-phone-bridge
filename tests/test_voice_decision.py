import unittest
import os
import tempfile
import time
from codex_phone.voice_decision import Decision
from codex_phone.cloud_audio import reserve_allowance


class SpokenDecisionTests(unittest.TestCase):
    def test_yes_before_readback_finishes_cannot_confirm(self):
        d = Decision()
        d.propose('Option A')
        d.heard('Ja')
        with self.assertRaises(ValueError):
            d.confirm()

    def test_cannot_confirm_in_same_utterance(self):
        d = Decision()
        d.heard('Mach das mobil einfacher')
        d.propose('Mobile Navigation vereinfachen; Desktop unverändert')
        d.read_back()
        with self.assertRaises(ValueError):
            d.confirm()

    def test_correction_requires_a_new_confirmation(self):
        d = Decision()
        d.heard('Mobile vereinfachen')
        d.propose('Mobile vereinfachen')
        d.read_back()
        d.heard('Nein, Desktop auch ändern')
        with self.assertRaises(ValueError):
            d.confirm()
        d.propose('Mobile und Desktop ändern')
        d.read_back()
        with self.assertRaises(ValueError):
            d.confirm()
        d.heard('Ja, genau!')
        self.assertEqual(d.confirm(), 'Mobile und Desktop ändern')

    def test_incidental_yes_is_not_confirmation(self):
        d = Decision()
        d.propose('Option A')
        d.read_back()
        d.heard('Ja aber was bedeutet das?')
        with self.assertRaises(ValueError):
            d.confirm()

    def test_natural_confirmation_and_whitespace(self):
        d = Decision()
        d.propose('Option A')
        d.read_back()
        d.heard('Ja,  das ist richtig!')
        self.assertEqual(d.confirm(), 'Option A')

    def test_composed_confirmation_without_new_instructions(self):
        for phrase in ('Ja, genau, bitte so machen.', 'Ja genau kannst du so machen',
                       'Ja, so machen wir das', 'Okay, bitte übernehmen'):
            d = Decision(); d.propose('Option A'); d.read_back(); d.heard(phrase)
            self.assertEqual(d.confirm(), 'Option A')
        for phrase in ('Ja aber nicht so', 'Ja, bitte Desktop auch ändern', 'Ja?',
                       'Ja nein', 'Ja vielleicht', 'Ja wenn es keine Fehler gibt'):
            d = Decision(); d.propose('Option A'); d.read_back(); d.heard(phrase)
            with self.assertRaises(ValueError):
                d.confirm()

    def test_no_proposal_or_oversize(self):
        d = Decision()
        d.heard('Ja')
        with self.assertRaises(ValueError):
            d.confirm()
        with self.assertRaises(ValueError):
            d.propose('x' * 2001)

    def test_free_use_reservation_survives_reopening(self):
        with tempfile.TemporaryDirectory() as directory:
            from unittest.mock import patch
            with patch.dict(os.environ, CODEX_PHONE_HOME=directory):
                for _ in range(12):
                    reserve_allowance()
                with self.assertRaisesRegex(RuntimeError, 'no paid fallback'):
                    reserve_allowance()

    def test_verified_provider_cap_preserves_ledger_without_twelve_attempt_block(self):
        from codex_phone.cloud_audio import allowance_status
        from unittest.mock import patch
        cfg = {'cloud_voice': {'project_id': 'selected'},
               'provider_plan_evidence': {'project_id': 'selected', 'plan': 'build',
                    'checked_at': time.time(), 'source': 'dashboard'}}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, CODEX_PHONE_HOME=directory):
            for _ in range(13):
                reserve_allowance(cfg)
            status = allowance_status(cfg)
            self.assertEqual(status['local_calls_used'], 13)
            self.assertIsNone(status['local_monthly_cap'])
            self.assertTrue(status['provider_enforced_hard_cap'])
            self.assertEqual(status['provider_remaining_allowance'], 'UNKNOWN')

    def test_wrong_project_or_stale_plan_cannot_remove_guard(self):
        from codex_phone.cloud_audio import allowance_status
        from unittest.mock import patch
        cfg = {'cloud_voice': {'project_id': 'selected'},
               'provider_plan_evidence': {'project_id': 'other', 'plan': 'build',
                    'checked_at': time.time(), 'source': 'dashboard'}}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, CODEX_PHONE_HOME=directory):
            self.assertFalse(allowance_status(cfg)['provider_enforced_hard_cap'])
            self.assertFalse(allowance_status(cfg)['budget_allows_call'])
            cfg['provider_plan_evidence'].update(project_id='selected', checked_at=time.time()-8*86400)
            self.assertFalse(allowance_status(cfg)['provider_enforced_hard_cap'])
            self.assertFalse(allowance_status(cfg)['budget_allows_call'])
