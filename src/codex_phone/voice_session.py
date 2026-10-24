"""One production session factory, also used with deterministic offline models."""
from livekit.agents import AgentSession, TurnHandlingOptions


def build_session(**models):
    return AgentSession(**models, aec_warmup_duration=None,
        turn_handling=TurnHandlingOptions(
            turn_detection='vad', preemptive_generation={'enabled': False},
            endpointing={'mode': 'fixed', 'min_delay': .7, 'max_delay': 2.},
            interruption={'enabled': True, 'mode': 'vad', 'min_duration': .3,
                          'min_words': 0, 'resume_false_interruption': True,
                          'false_interruption_timeout': .8,
                          'discard_audio_if_uninterruptible': False}),
        user_away_timeout=None)


def attach_controller(session, controller):
    @session.on('user_state_changed')
    def user_state(event):
        if event.new_state == 'speaking':
            controller.speech_started()

    @session.on('speech_created')
    def new_speech(event):
        # Generated speech can be queued while state remains 'speaking'. It
        # invalidates readback consent even before actual audio starts.
        if event.source == 'generate_reply':
            controller.agent_spoke()
