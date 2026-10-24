# Calling fixes — 2026-10-24

## Scope

Implemented against f10bb92. No personal phone call was made for this release.
The existing exact MAFFEO dialogue model, recognition backend, private stores,
provider hard-cap evidence, destination restriction and no-replay boundary remain.

- One pure conversation controller handles OPEN/DECISION, explicit ending, hold,
  incomplete turns and delayed confirmation. OPEN never returns a decision.
- Corrections and generated speech invalidate readback eligibility. Invalidation
  advances its epoch. Old completion callbacks cannot authorize a newer draft.
- The first observed speech onset must follow complete successful local readback.
  New speech during the short commit window cancels pending confirmation. This
  cannot detect an arbitrarily late qualification or prove device audio receipt.
- Closed confirmation phrases reject incomplete, quoted, conditional and question
  forms. Completed user turns are processed once; model tools cannot confirm.
- Shared production SDK options enable interruption during greeting and readback,
  disable audio discard/AEC warmup, and support real PCM pause/resume. Generated
  replies are limited to two sentences; exact readbacks are exempt.
- HOLD/partial turns suppressed with StopResponse are explicitly retained because
  LiveKit 1.8.8 otherwise drops them. No automatic silence monologue is configured.
- Private protocol v2 validates call identity before dialing. A confirmed receipt
  is persisted before acknowledgement. A farewell has a bounded completion budget.
  SIP hangup is observed before graceful worker cleanup. Control loss does not
  count as CALL_CLOSED. Stored answers survive subsequent cancellation/orphaning.
- Worker errors are redacted to lifecycle stage/error class in a bounded private
  log. No transcripts, raw provider payloads or credentials enter that log.

## Executed evidence

- Full installed voice-environment suite: 75 tests PASS (14.165 s final rerun).
- Real SDK production interruption options: false interruption resumes the exact
  remaining PCM; recognized user speech interrupts output.
- Real SDK turn hook: HOLD reaches the controller and stays in actual chat context
  for the following turn. New generated speech invalidates late readback callbacks.
- Real loopback SIP: both peers observe CALL_CLOSED after local hangup.
- Real stdio MCP + controller + local SIP/RTP + existing cloud providers: decision
  persisted exactly once; 425600 returned audible bytes, first audible RTP 0.211 s.
- Same composed path with German Cartesia profile: decision persisted once;
  341120 returned audible bytes, first audible RTP 0.248 s.
- German-profile synthesis alone: 113101 samples, first audio 0.254 s, 7.069 s audio.
- OPEN with German profile: synthetic “Moment” produced a measured silent hold,
  then a natural ending request completed without a decision. 71040 returned
  audible bytes, local_dialog_closed=true, farewell_completed=true,
  outcome=ended_by_request, zero dialogue-model tokens. First audible RTP 0.531 s.
- Fresh live daemon: IDLE and voice_protocol=2. No active call was interrupted.

The RTP timings are loopback measurements, not iPhone latency. The cloud checks
consume only the existing hard-capped project allowance. Remaining balance stays
UNKNOWN. No new account, subscription, upgrade or custom voice was created.

Independent reviews found and prompted fixes for stale readback epochs, durable
receipt preservation, natural end grammar, question/quote guards, retry epochs,
first-onset preservation and queued generated speech. The final independent
subagent review found no further concretely demonstrated consent/protocol blocker;
its 13 targeted offline tests passed. Claude separately reviewed the implementation
snapshot; both of its blocking findings were reproduced or covered and fixed.

## Voice profile and rollback

`cloud_voice.synthesis_profile=cartesia-de` selects `cartesia/sonic-3` with the
standard German Conversational Woman voice. `fish` retains the existing Fish voice
ID and offers explicit rollback; there is no silent fallback.

Sources: [LiveKit Cartesia integration](https://docs.livekit.io/agents/models/tts/cartesia/)
provides standard voices through existing LiveKit credentials;
[the provider integration catalog](https://signalwire.com/docs/platform/voice/tts/cartesia)
identifies the German standard voice. The actual existing-project synthesis and
composed tests above verified availability. They do not prove subjective quality.

## Remaining human acceptance

Not executed: the owner's voice preference, real iPhone echo/double-talk, interruption
of the real-device greeting/readback, perceived thinking-pause timing and physical
phone hangup. A new call requires an explicit owner request. The code and synthetic
path are verified; these device and subjective claims remain UNVERIFIED.

Reproduce: `PYTHONPATH=src .local/voice-venv/bin/python -B -m unittest discover -s tests`.
Cloud reproduction is `scripts/test-cloud-sip.py --mcp --use-free-allowance` with the
existing project/voice and `--synthesis-profile cartesia-de`; add `--open-hangup` for
hold/ending. It calls only a loopback peer, never the configured personal account.
