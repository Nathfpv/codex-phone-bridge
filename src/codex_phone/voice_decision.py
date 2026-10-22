"""Small, provider-independent boundary for a spoken product decision."""
import re


class Decision:
    def __init__(self):
        self.turn = 0
        self.proposal = None
        self.proposed_at = None
        self.read_back_at = None
        self.last_text = ''

    def heard(self, text):
        self.turn += 1
        self.last_text = text

    def propose(self, text):
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
            raise ValueError('Invalid decision length')
        self.proposal = text.strip()
        self.proposed_at = self.turn
        self.read_back_at = None
        return self.proposal

    def read_back(self):
        """Called only after the exact saved proposal finished audio playout."""
        if self.proposal is None:
            raise ValueError('No proposal to read back')
        self.read_back_at = self.turn

    def confirm(self):
        # A second, explicit utterance is required; a tool call is not consent.
        normalized = ' '.join(re.sub(r'[^a-zäöüß ]', '', self.last_text.lower()).split())
        accepted = {'ja', 'ja genau', 'genau', 'passt', 'bestätigt', 'bestätigen',
                    'ja bitte', 'ja mach das', 'ja so machen', 'ja das passt',
                    'ja passt', 'richtig', 'stimmt', 'yes', 'correct', 'confirm',
                    'ja gerne', 'ja das ist richtig', 'ja das stimmt', 'so passt es',
                    'ja kannst du so machen', 'ja das kannst du so machen',
                    'ja bitte weitergeben', 'antwort bestätigen', 'jo', 'jo genau'}
        # Compose ordinary positive phrases, but reject questions, negations,
        # qualifications and new product content. The model cannot bypass this.
        words = normalized.split()
        positive = {'ja','jo','genau','richtig','passt','stimmt','einverstanden',
                    'bestätigt','bestätigen','jep','jap','yes','okay','ok'}
        continuation = positive | {'bitte','so','machen','mach','mache','wir','das',
                       'kannst','du','übernehmen','umsetzen','weitergeben','ist',
                       'für','mich','alles','bestätige','ich','antwort','gerne',
                       'können','kann','übernimm','es'}
        natural_yes = bool(words and words[0] in positive and
                           all(w in continuation for w in words))
        if (self.proposal is None or self.read_back_at is None or self.turn <= self.read_back_at or
                '?' in self.last_text or not (normalized in accepted or natural_yes)):
            raise ValueError('A new, unambiguous spoken confirmation is required')
        return self.proposal
