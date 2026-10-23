# Voice interruption repair — 2026-10-23

## Observed problem and reproduced mechanism

The owner reported speech ending after roughly three seconds and silence while
an answer appeared to continue. The last successful human call returned a
confirmed decision and did not record a transport disconnect. Its old diagnostics
do not identify every silent interval; no claim is made that all gaps have one cause.

The installed LiveKit Agents 1.8.8 requires a pause-capable output to recover from
false interruptions. Our output advertised `pause=False`; short audio activity
could permanently interrupt speech after 250 ms, without recognized words.
A real SDK/Unix-datagram reproduction showed that `pause()` continued sending
three packets in 65 ms. New regression tests failed on that old implementation.

## Change

- Real PCM pause/resume preserves unsent audio and pacing, including final partial
  packets. Clearing cancels paused/deferred output and wakes blocked producers.
- False-interruption recovery is explicitly enabled; interruption threshold 700 ms,
  recovery timeout 800 ms. Word threshold remains zero because recognition is batch
  Whisper; waiting for words would defer genuine interruption until recognition.
- Turn endpoint delay is 700 ms rather than 450 ms, allowing longer natural pauses.
  This intentionally adds 250 ms of patience; it does not establish faster overall
  response time. Short complete responses avoid unnecessary spoken introductions.
- Opening question cannot be interrupted by incidental noise. Proposal readback
  remains protected and requires completed audible playback before new consent.
- All spoken model instructions/tool guidance request German, with natural Swiss
  German responses. The existing voice remains; native Swiss pronunciation and
  subjective fluency are not established by a prompt or synthetic tests.
- Numeric latency and pause/recovery diagnostics exclude transcript/audio content.

## Executed evidence

- Offline SDK/Unix-datagram pause, exact continuity, paced resume, paused tail,
  clear/cancellation, saturated socket and clean subsequent-segment tests: PASS.
- Actual offline AgentSession engine: empty-transcript noise resumes exact remaining
  speech; recognized speech cancels it. Failed partial readback is rejected even
  when the SDK SpeechHandle itself succeeds. Removing the output-failure guard
  reproduces erroneous acceptance; restoring it passes.
- Full installed voice-environment suite: 49 tests PASS. Independent final review:
  no remaining blocking findings.
- Existing SDK PCM roundtrip, pacing and interruption script: PASS.
- Fresh stdio MCP → real controller → real loopback SIP/RTP → MAFFEO/Groq/Fish:
  PASS, 490880 audible return-audio bytes, first audible RTP 0.148 s after local
  connection. Confirmed result returned to invocation 42, persisted ANSWERED,
  exactly one synthetic call. Final repeated composed check after the failure guard:
  PASS, 414720 audible bytes, first audible RTP 0.130 s. These measure local
  transport, not iPhone latency.

No new human call was made during this repair. Device/network reliability and
perceived Swiss-German voice quality require an authorized human assessment.
The prior human confirmation authorizes the four requested improvements; it does
not turn unexecuted device checks into PASS.

The installed controller starts a fresh voice worker for each call, so the next
authorized call loads this fix without terminating unrelated MCP sessions.
Only source/docs/tests and the existing private operational runtime remain;
synthetic test directories were removed on exit.
