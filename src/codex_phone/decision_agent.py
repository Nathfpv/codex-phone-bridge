"""Voice conversation agent with an explicit proposal handoff boundary."""
from dataclasses import replace

from livekit.agents import Agent

from .voice_decision import Decision


class DecisionAgent(Agent):
    def __init__(self, *, decision, **kwargs):
        super().__init__(**kwargs)
        self.decision = decision

    def llm_node(self, chat_ctx, tools, model_settings):
        latest = chat_ctx.items[-1] if chat_ctx.items else None
        if (self.decision.proposal is None
                and getattr(latest, 'role', None) == 'user'
                and Decision.is_confirmation(latest.text_content or '')):
            # A clear affirmative means prepare the concrete proposal now. This
            # never delivers consent: normal successful readback and a NEW yes
            # remain required. Tool-result continuations must not force again.
            model_settings = replace(model_settings, tool_choice={
                'type': 'function', 'function': {'name': 'propose_decision'}})
        return Agent.default.llm_node(self, chat_ctx, tools, model_settings)
