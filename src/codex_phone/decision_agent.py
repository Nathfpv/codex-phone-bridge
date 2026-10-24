"""SDK adapter: one completed-turn policy, no forced tools on generic yes."""
import re
from livekit.agents import Agent, StopResponse


async def short_speech(text):
    """Two complete sentences, at most 500 characters; readbacks bypass this node."""
    pending = ''
    sentences = 0
    count = 0
    async for chunk in text:
        pending += chunk
        while True:
            match = re.search(r'[.!?](?:\s|$)', pending)
            if not match:
                break
            sentence, pending = pending[:match.end()], pending[match.end():]
            if count + len(sentence) > 500:
                tail = sentence[:500-count].rsplit(' ', 1)[0]
                if tail:
                    yield tail.rstrip('.!? ') + '.'
                return
            yield sentence
            count += len(sentence)
            sentences += 1
            if sentences >= 2:
                return
        if count + len(pending) > 500:
            # No sentence punctuation: end at a complete word, bounded memory.
            remaining = pending[:500-count].rsplit(' ', 1)[0]
            if remaining:
                yield remaining + '.'
            return
    if pending and count + len(pending) <= 500:
        yield pending


class DecisionAgent(Agent):
    def __init__(self, *, decision=None, on_turn=None, **kwargs):
        super().__init__(**kwargs)
        self.decision = decision
        self.on_turn = on_turn
        self.reading_back = False

    async def on_user_turn_completed(self, turn_ctx, new_message):
        if self.on_turn is not None and await self.on_turn(new_message) != 'RESPOND':
            # LiveKit 1.8.8 drops StopResponse turns. Explicitly retain the user
            # message so HOLD/partial phrases and corrections are never lost.
            ctx = self.chat_ctx.copy()
            if not any(item.id == new_message.id for item in ctx.items):
                ctx.items.append(new_message)
                await self.update_chat_ctx(ctx)
            raise StopResponse()

    def tts_node(self, text, model_settings):
        return Agent.default.tts_node(self, text if self.reading_back else short_speech(text), model_settings)
