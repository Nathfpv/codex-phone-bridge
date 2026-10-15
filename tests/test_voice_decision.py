import unittest
import os
import tempfile
from codex_phone.voice_decision import Decision
from codex_phone.cloud_audio import reserve_allowance


class SpokenDecisionTests(unittest.TestCase):
    def test_cannot_confirm_in_same_utterance(self):
        d = Decision()
        d.heard('Mach das mobil einfacher')
        d.propose('Mobile Navigation vereinfachen; Desktop unverändert')
        with self.assertRaises(ValueError):
            d.confirm()

    def test_correction_requires_a_new_confirmation(self):
        d = Decision()
        d.heard('Mobile vereinfachen')
        d.propose('Mobile vereinfachen')
        d.heard('Nein, Desktop auch ändern')
        with self.assertRaises(ValueError):
            d.confirm()
        d.propose('Mobile und Desktop ändern')
        with self.assertRaises(ValueError):
            d.confirm()
        d.heard('Ja, genau!')
        self.assertEqual(d.confirm(), 'Mobile und Desktop ändern')

    def test_incidental_yes_is_not_confirmation(self):
        d = Decision()
        d.propose('Option A')
        d.heard('Ja aber was bedeutet das?')
        with self.assertRaises(ValueError):
            d.confirm()

    def test_natural_confirmation_and_whitespace(self):
        d = Decision()
        d.propose('Option A')
        d.heard('Ja,  das ist richtig!')
        self.assertEqual(d.confirm(), 'Option A')

    def test_composed_confirmation_without_new_instructions(self):
        for phrase in ('Ja, genau, bitte so machen.', 'Ja genau kannst du so machen',
                       'Ja, so machen wir das', 'Okay, bitte übernehmen'):
            d = Decision(); d.propose('Option A'); d.heard(phrase)
            self.assertEqual(d.confirm(), 'Option A')
        for phrase in ('Ja aber nicht so', 'Ja, bitte Desktop auch ändern', 'Ja?',
                       'Ja nein', 'Ja vielleicht', 'Ja wenn es keine Fehler gibt'):
            d = Decision(); d.propose('Option A'); d.heard(phrase)
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
