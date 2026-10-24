import unittest
from codex_phone.call_control import CallController, intent


class CallPolicy(unittest.TestCase):
    def controller(self, conversation=False):
        clock = [10.]
        ctl = CallController(conversation=conversation, now=lambda: clock[0])
        return ctl, clock

    def test_end_is_not_consent_and_negations_are_not_end(self):
        for text in ('Leg auf', 'Beende das Gespräch', 'Tschüss', 'Ja, beende das Gespräch bitte',
                     'Gut. Beende das Gespräch.', 'Beende nun das Gespräch',
                     'Ich möchte das Gespräch beenden'):
            c, _ = self.controller(); self.assertEqual(c.user_turn('1', text), 'CLOSE')
            self.assertEqual(c.outcome, {'kind': 'ended_by_request'})
        for text in ('Leg nicht auf', 'Was heißt leg auf?', 'Wenn ich ja sage dann leg auf', 'Sag nicht leg auf', 'Ja, leg auf?', '„Ja, leg auf“',
                     'Wenn ich sage ja. Leg auf.'):
            self.assertNotIn(intent(text), ('END', 'CONFIRM_END'))

    def test_late_yes_cannot_confirm_or_corrected_proposal(self):
        c, clock = self.controller(); d = c.decision
        d.propose('X'); d.read_back(d.version, ended_at=9.)
        c.speech_started(); c.user_turn('1', 'Nein, eher Y')
        c.speech_started(); c.user_turn('2', 'Ja')
        clock[0] += 1; c.tick(); self.assertIsNone(c.outcome)

    def test_commit_requires_new_onset_and_quiet_commit_window(self):
        c, clock = self.controller(); d = c.decision
        d.propose('X'); d.read_back(d.version, ended_at=9.)
        c.speech_started(); c.user_turn('1', 'Ja')
        self.assertIsNone(c.outcome)
        c.speech_started(); c.user_turn('2', 'aber nur morgen')
        clock[0] += 1; c.tick(); self.assertIsNone(c.outcome)
        d.propose('Morgen'); d.read_back(d.version, ended_at=10.)
        c.speech_started(); c.user_turn('3', 'Ja')
        clock[0] += 1; c.tick()
        self.assertEqual(c.outcome, {'kind': 'confirmed', 'answer': 'Morgen'})

    def test_correction_during_readback_invalidates_late_callback(self):
        c, clock = self.controller(); d = c.decision
        d.propose('X'); version = d.version
        c.speech_started(); c.user_turn('1', 'Nein, eher Y')
        self.assertFalse(d.read_back(version, ended_at=11.))
        clock[0] = 12; c.speech_started(); c.user_turn('2', 'Ja')
        clock[0] += 1; c.tick(); self.assertIsNone(c.outcome)

    def test_early_onset_does_not_confirm(self):
        c, clock = self.controller(); c.speech_started()
        c.decision.propose('X'); c.decision.read_back(1, ended_at=11.)
        clock[0] = 12; c.user_turn('1', 'Ja'); clock[0] += 1; c.tick()
        self.assertIsNone(c.outcome)

    def test_first_onset_cannot_be_replaced_by_later_noise(self):
        c, clock = self.controller(); c.speech_started()
        c.decision.propose('X'); c.decision.read_back(c.decision.version, ended_at=11.)
        clock[0] = 12; c.speech_started(); c.user_turn('1', 'Ja')
        clock[0] = 13; c.tick(); self.assertIsNone(c.outcome)

    def test_hold_fragment_open_and_limit(self):
        c, clock = self.controller(True)
        self.assertEqual(c.user_turn('1', 'Moment'), 'SUPPRESS')
        clock[0] += 10; c.tick(); self.assertTrue(c.holding)
        self.assertEqual(c.user_turn('2', 'Also ich …'), 'SUPPRESS')
        self.assertEqual(c.user_turn('3', 'würde Y nehmen'), 'RESPOND')
        for i in range(4, 43): c.user_turn(str(i), 'Hallo')
        self.assertEqual(c.outcome, {'kind': 'limit'})
        self.assertNotIn('answer', c.outcome)
