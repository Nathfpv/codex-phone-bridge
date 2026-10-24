"""Small, provider-independent boundary for a spoken product decision."""
import re


class Decision:
    def __init__(self):
        self.turn = 0
        self.version = 0
        self.proposal_version = None
        self.readback_ended_at = None
        self.proposal = None
        self.proposed_at = None
        self.read_back_at = None
        self.last_text = ''

    def heard(self, text):
        self.turn += 1
        self.last_text = text
        if not self.is_confirmation(text):
            self.invalidate()

    def propose(self, text):
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
            raise ValueError('Invalid decision length')
        self.version += 1
        self.proposal_version = self.version
        self.proposal = text.strip()
        self.proposed_at = self.turn
        self.read_back_at = None
        return self.proposal

    def read_back(self, version=None, ended_at=None):
        """Called only after the exact saved proposal finished audio playout."""
        if self.proposal is None:
            raise ValueError('No proposal to read back')
        if version is not None and version != self.version:
            return False
        self.read_back_at = self.turn
        self.readback_ended_at = ended_at
        return True

    def invalidate(self):
        self.version += 1
        self.read_back_at = None
        self.readback_ended_at = None

    @staticmethod
    def is_confirmation(text):
        normalized = ' '.join(re.sub(r'[^a-zäöüß ]', '', text.lower()).split())
        accepted = {'ja', 'ja genau', 'genau', 'passt', 'bestätigt', 'bestätigen',
                    'ja bitte', 'ja mach das', 'ja so machen', 'ja das passt',
                    'ja passt', 'richtig', 'stimmt', 'yes', 'correct', 'confirm',
                    'ja gerne', 'ja das ist richtig', 'ja das stimmt', 'so passt es',
                    'ja kannst du so machen', 'ja das kannst du so machen',
                    'ja bitte weitergeben', 'antwort bestätigen', 'jo', 'jo genau',
                    'ja wir schicken ab', 'ja bitte abschicken', 'ja abschicken',
                    'ja wir schliessen ab', 'ja wir schließen ab',
                    'ja bitte abschliessen', 'ja bitte abschließen'}
        # Closed phrases: partial affirmations must never authorize a change.
        accepted |= {'einverstanden', 'ja genau bitte so machen',
                     'ja genau kannst du so machen', 'ja so machen wir das',
                     'okay bitte übernehmen', 'ok bitte übernehmen'}
        return '?' not in text and normalized in accepted

    def confirm(self):
        # A second, explicit utterance is required; a tool call is not consent.
        if (self.proposal is None or self.read_back_at is None or
                self.turn <= self.read_back_at or not self.is_confirmation(self.last_text)):
            raise ValueError('A new, unambiguous spoken confirmation is required')
        return self.proposal
