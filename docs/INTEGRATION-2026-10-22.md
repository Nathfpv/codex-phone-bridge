# MAFFEO phone integration — executed 2026-10-22

## Result and scope

Installed profile: existing MAFFEO router (`gpt-oss-120b`) for dialogue, existing
Groq credential for Whisper Large V3, existing LiveKit Fish voice. No new provider
account, model server, Azure resource, payment method or paid upgrade was created.
The Local-AI project and its production router/registry were not edited.

This is free within actual provider allowances, not an unlimited-free promise.
Phone and web dialogue share existing provider limits. No automatic switch to a
different dialogue model is added. Local Whisper models are not loaded.

## Account observations

Authenticated LiveKit dashboard: current project plan Build; next invoice $0.00.
The credits panel explicitly said balances were temporarily unavailable. Therefore
exact remaining inference credit stays UNKNOWN. The provider documents hard-stop
behavior for Build. Current project-bound dashboard evidence is retained privately
in runtime configuration and expires after seven days. Renew only after another
actual dashboard check. Stale or mismatched evidence blocks the exemption; old
reservation history is retained, never presented as remaining cloud credit.

The Local-AI cost-safety inventory passed. This audits local configuration and
allowlists; it does not independently prove every provider's billing settings.

## Executed checks

- Production MAFFEO router: streamed function call returned the expected function
  and arguments; first HTTP stream event 0.454s. Tool-result continuation returned
  a German confirmation question, HTTP 200. Router log identified Groq GPT-OSS120B.
- Actual installed voice SDK through MAFFEO: tool call completed in 0.628s.
- Existing Fish synthesis: first audio 1.316s, 2.608s of generated audio.
- Same synthetic Fish audio compared through Groq Whisper and AssemblyAI on three
  German sentences (choice, numbers, qualified assent). Whisper preserved the first
  choice sentence where AssemblyAI misrecognized words; both misrecognized part of
  the number sentence. Both preserved the qualified assent. This small synthetic
  comparison is not proof of Swiss-German human accuracy or general superiority.
  Whisper request times after full audio was available: 0.281–0.392s. AssemblyAI
  stream-close timing includes protocol finalization, so it is not a comparable
  conversational-latency measurement.
- Actual local SIP/RTP + MAFFEO + AssemblyAI + Fish: confirmed decision PASS;
  432640 received audio bytes, first audible RTP 0.152s after connection.
- Actual local SIP/RTP + MAFFEO + Groq Whisper + Fish: confirmed decision PASS;
  403200 received audio bytes, first audible RTP 0.128s after connection.
- Composed real stdio MCP + Bridge controller + local SIP/RTP + new cloud profile:
  PASS; 400000 received audio bytes, first audible RTP 0.134s. Verified response ID,
  confirmed decision persisted as ANSWERED, exactly one call. Only the synthetic
  loopback SIP transport was substituted, never the personal Linphone destination.
- SDK PCM roundtrip, pacing and interruption: PASS.
- Full voice-environment offline suite: 41 tests PASS. Includes no replay after
  send/disconnect, daemon recovery, cancellation cleanup, separate MCP identities,
  negative/qualified assent, failed/interrupted/silent readback, preserved answers,
  stale/mismatched plan evidence and missing-config readiness.
- Independent review: initial readback-error finding reproduced and fixed. Subsequent
  review reported no blocking findings on code reviewed. Final no-replay regression
  was added afterward and executed with the full suite.

The RTP timings measure local synthetic transport, not iPhone earpiece latency.
No inference from these checks establishes a user's preferred voice quality.

## Recovery, privacy and metrics

MCP daemon recovery happens only before sending a request. A disconnect after
sending cannot replay the call. Existing daemon singleton locking is retained.
Recovery marks expired requests EXPIRED and preserves answered decisions; six old
pending entries were removed from the active queue this way, with no row deletion.

The exact saved proposal is spoken by the controller. Successful, uninterrupted,
non-silent readback must finish before a NEW explicit confirmation is accepted.
A tool call itself is never consent. Voice does not grant shell/account approvals.

Numeric SDK observations are saved throughout the session, including before later
failure. They exclude unobserved provider-side work and may be partial after process
termination; they are not bills or remaining balance. No extra transcript/audio
recordings are created. Synthetic audio used for comparisons stayed in RAM.

## Remaining real-device boundary

One previously authorized attempt reached SIP RINGING and ended in TimeoutError;
this does not prove actual iPhone ringing. No spoken answer was accepted.
The owner subsequently prohibited further calls in this task. All later telephone
checks used loopback synthetic peers only. Real iPhone lock-screen delivery,
mobile-data reliability and personal Swiss-German speech/voice assessment remain
NOT TESTED for the new profile, deliberately excluded by the owner's instruction.

Existing MCP processes can retain old imported adapter code and show the old fixed
12-attempt status. Fresh stdio MCP processes were verified with the new readiness
output and full composed path. Reconnect old MCP server sessions to load changes;
other agent sessions are not terminated. Codex UI control was unavailable, so this
chat's already-running adapter was not forcibly restarted.

## Repeat and rollback

```sh
PYTHONPATH=src .local/voice-venv/bin/python -B -m unittest discover -s tests
.local/voice-venv/bin/python -B scripts/test-cloud-pcm.py
# Explicit free-allowance opt-in, ONLY synthetic loopback SIP:
.local/voice-venv/bin/python -B scripts/test-cloud-sip.py --project SELECTED_PROJECT --voice EXISTING_VOICE --use-free-allowance --mcp
```

Runtime selectors `dialogue_backend=livekit` and `recognition_backend=livekit`
restore the original provider path. Preserve selected project/voice, secrets and
all ledger/decision records; do not restore a stale database. Source rollback is
through Git. Restoring an older provider path still consumes its real allowance.

## Retained operational files

Only normal project source/docs and the existing private runtime remain. The new
`last-voice-usage.json` is a small operational meter snapshot, not a test recording.
The runtime config contains additional non-secret selectors and plan evidence.
Temporary SIP/MCP test directories are removed by their owners at test exit.
