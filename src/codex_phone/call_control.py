"""Pure conversation policy; the SDK owns speaking/thinking, not this module."""
import re
import time
from .voice_decision import Decision


def normalized(text):
    return ' '.join(re.sub(r'[^a-zäöüß ]', ' ', text.lower()).split())


END = {'leg auf', 'lege auf', 'bitte leg auf', 'bitte lege auf', 'auflegen',
       'beende das gespräch', 'beende bitte das gespräch', 'schließe das gespräch',
       'schliesse das gespräch', 'schließ das gespräch', 'schliess das gespräch',
       'beenden wir das gespräch', 'tschüss', 'tschüs', 'das wars', 'das war s'}
HOLD = {'moment', 'einen moment', 'warte', 'warte bitte', 'bitte warte',
        'ich überlege', 'lass mich nachdenken', 'ich muss nachdenken',
        'warte kurz', 'einen moment bitte', 'ich überlege noch',
        'lass mich kurz nachdenken', 'ich bin noch am überlegen',
        'stopp', 'stop', 'halt', 'lass mich ausreden', 'ich war noch nicht fertig'}


def end_command(text):
    n = normalized(text)
    # Whole command grammar, never a substring inside a negation/quote/example.
    if any(c in text for c in '\"„“«»') or re.search(r'\b(nicht|kein|wenn|falls|bedeutet|heißt|sag|zitiere)\b', n):
        return False
    n = re.sub(r'^(ja|gut|okay|ok|also) ', '', n)
    n = re.sub(r'\b(bitte|jetzt|nun|selbst)\b', '', n)
    n = ' '.join(n.split())
    return (n in END or n in {'ich möchte das gespräch beenden',
                              'ich will das gespräch beenden', 'ich möchte auflegen',
                              'kannst du auflegen', 'kannst du das gespräch beenden',
                              'wir beenden das gespräch', 'schluss machen'})


def intent(text):
    n = normalized(text)
    if (any(c in text for c in '\"„“«»')
            or re.search(r'\b(wenn|falls|nicht|kein|bedeutet|heißt|zitiere|sag)\b', n)
            or ('?' in text and not n.startswith('kannst du '))):
        return 'OTHER'
    # Explicit affirmative + end, checked before a plain ending; the controller
    # still requires the fully heard, current proposal and a fresh speech onset.
    for suffix in END:
        if n.endswith(' ' + suffix) and Decision.is_confirmation(n[:-len(suffix)].strip()):
            return 'CONFIRM_END'
    if end_command(text):
        return 'END'
    # An independent imperative sentence after ordinary discussion is an end.
    if not any(c in text for c in '\"„“«»') and '?' not in text:
        parts = [p.strip() for p in re.split(r'[.!]+', text) if p.strip()]
        if len(parts) > 1 and end_command(parts[-1]):
            return 'END'
    if '?' in text:
        return 'OTHER'
    if n in HOLD:
        return 'HOLD'
    if Decision.is_confirmation(text):
        return 'CONFIRM'
    if n and (n.split()[-1] in {'ich', 'du', 'weil', 'aber', 'und', 'also', 'äh', 'ähm'}
              or text.rstrip().endswith(('…', '...'))):
        return 'INCOMPLETE'
    return 'OTHER'


class CallController:
    def __init__(self, *, conversation=False, now=time.monotonic, commit_delay=.6):
        self.conversation = conversation
        self.now = now
        self.commit_delay = commit_delay
        self.decision = Decision()
        self.outcome = None
        self.holding = False
        self.seen = set()
        self.pending = None
        self.onset = None
        self.turns = 0
        self.fragment = ''
        self.retry_proposal = None

    def finish(self, kind, answer=None):
        if self.outcome is None:
            self.outcome = {'kind': kind}
            if answer is not None and not self.conversation:
                self.outcome['answer'] = answer
            self.pending = None
        return 'CLOSE'

    def speech_started(self):
        if self.onset is None:
            self.onset = self.now()
        if self.pending is not None:
            self.pending = None
            self.decision.invalidate()

    def readback_failed(self, version):
        # A correction during playback already advanced the epoch: never retry it.
        if self.decision.version == version:
            self.retry_proposal = self.decision.proposal
            self.decision.invalidate()

    def agent_spoke(self):
        self.pending = None
        self.decision.invalidate()

    def user_turn(self, message_id, text):
        if self.outcome is not None or message_id in self.seen:
            return 'SUPPRESS'
        self.seen.add(message_id)
        self.turns += 1
        kind = intent(text)
        onset, self.onset = self.onset, None
        if kind == 'END':
            return self.finish('ended_by_request')
        if self.turns > 40:
            return self.finish('limit')
        if kind not in ('CONFIRM', 'CONFIRM_END'):
            self.retry_proposal = None
        if kind == 'HOLD':
            self.holding = True
            self.decision.invalidate()
            return 'SUPPRESS'
        self.holding = False
        if kind == 'INCOMPLETE':
            self.fragment = (self.fragment + ' ' + text).strip()
            self.decision.heard(text)
            return 'SUPPRESS'
        # Never combine a deferred fragment into consent: it is discussion.
        if self.fragment:
            self.decision.heard(self.fragment + ' ' + text)
            self.fragment = ''
            return 'RESPOND'
        d = self.decision
        ended_at = d.readback_ended_at
        eligible = (not self.conversation and ended_at is not None
                    and onset is not None and onset > ended_at)
        d.heard(text if kind != 'CONFIRM_END' else 'Ja')
        if kind in ('CONFIRM', 'CONFIRM_END') and eligible:
            try:
                answer = d.confirm()
            except ValueError:
                pass
            else:
                self.pending = (self.now() + self.commit_delay, answer, d.version)
                return 'SUPPRESS'
        if kind == 'CONFIRM' and not eligible and d.proposal is not None:
            if self.retry_proposal is not None:
                return 'READ_BACK'
            if d.proposal_version == d.version or d.read_back_at is not None:
                # Premature yes: invalidate this callback, then allow a later
                # request to repeat exactly this unchanged proposal.
                self.retry_proposal = d.proposal
                d.invalidate()
                return 'SUPPRESS'
            # A correction already invalidated the draft. Let the model discuss
            # that correction; never automatically repeat the obsolete text.
        if kind == 'CONFIRM_END':
            return self.finish('ended_by_request')
        if kind == 'CONFIRM' and self.retry_proposal is not None and not self.conversation:
            return 'READ_BACK'
        return 'RESPOND'

    def tick(self):
        if self.pending is not None and self.now() >= self.pending[0]:
            _, answer, version = self.pending
            if version == self.decision.version:
                return self.finish('confirmed', answer)
            self.pending = None
        return 'SUPPRESS'
