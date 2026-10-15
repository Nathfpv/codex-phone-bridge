# Cloud migration acceptance — PARTIAL

Checked 2026-10-15. This document concerns the new cloud conversation backend,
not historical Whisper/say device proofs. No complete cloud E2E success claimed.

## Executed evidence

- 23 safety/persistence/decision tests: PASS.
- Installed SDK dependency consistency (74 packages): PASS.
- Offline SDK/Unix PCM roundtrip, paced playback, clearing during playback: PASS.
- Real authenticated inference LLM request with neutral text: PASS.
- Real Fish TTS and AssemblyAI streaming recognition with neutral synthesized
  speech: PASS. This does not measure a human's dialect or phone quality.
- Two local Baresip processes with real SIP/RTP, cloud STT/dialogue/Fish TTS,
  synthetic caller and explicit confirmation through the separate worker:
  PASS; 31.414 seconds conversation, 600960 bytes of audible return PCM.
  This is explicitly NOT an iPhone or human test.
- Real provider registration: PASS.
- First real iPhone cloud call: FAIL, worker FileNotFoundError after connection.
  Added wait for the native media-source socket after CALL_ESTABLISHED.
- Second real iPhone cloud call: user confirmed voice audible. No confirmed
  decision returned within the 120-second conversation limit; timed out.
  The owner subsequently confirmed a two-way conversation. Confirmation delivery,
  interruption quality and original-task continuation remain unaccepted. Added
  metadata-only worker status diagnostics, without transcript recording.
- LiveKit dashboard: free Build plan verified; next invoice displayed $0.00 at
  setup. No payment, upgrade, phone-number rental or automatic recharge made.
  Final settled inference usage is not yet independently reconciled.

## Required device/task acceptance

| Test | New cloud backend | Evidence or missing proof |
| --- | --- | --- |
| T1 SIP registration | PASS | Actual provider REGISTERED result |
| T2 iPhone call | PASS | Actual ringing/connected calls, voice heard by owner |
| T3 Locked CallKit | PASS, one owner-confirmed attempt | Owner confirmed ringing while locked through the system display; reliability series outstanding |
| T4 Both directions | PASS | Owner explicitly confirmed a two-way conversation on the real iPhone |
| T5 SIP human speech → cloud STT | PASS, limited | Owner confirmed agent responses to speech; this implementation uses only cloud STT; transcript accuracy series outstanding |
| T6 TTS heard in SIP call | PASS | Owner: voice audible on second real call |
| T7 Codex question → new cloud call | PASS | A real coding task invoked its dynamic question and caused the iPhone call |
| T8 Exact thread/turn decision | PASS, technical | Confirmed result delivered to the exact pending request in the resumed thread/turn; owner semantic check pending |
| T9 Same task visibly continues | PASS | Same resumed turn created policy/decision/tests after receipt; two task tests independently rerun and passed |
| T10 Missed/failed call persists | PASS, limited | Unit persistence checks and failure records; complete device decline series outstanding |
| T11 Locked/mobile-data delivery | BLOCKED_BY_USER | New device series outstanding |
| T12 Restart/secrets/ports/limits | PASS, limited | Local restart, private CLI store, no new public listener, reservation tests; full operational series outstanding |

Next: one real controller-owned coding task is being tested with explicit
read-back consent. Its result is not yet accepted. Do not replace the evidence
above with provider claims, browser previews or offline fixtures.

## Owner feedback and subsequent fixes

The owner confirmed real two-way dialogue, locked-iPhone system ringing and
pleasantly short response pauses. They also confirmed having spoken assent in a
call where no confirmed result arrived. This was not accepted as live delivery:
the controller left the task unchanged. The new closing logic validates a new
positive user message after the saved proposal independently of a model tool
call. The artificial two-minute cap was expanded to five minutes. A subsequent
real local SIP/cloud regression passed. Caller name, direct opening and pre-dial
preparation were then changed at the owner's request; the updated local SIP/cloud
regression passed as well. Their new device outcome is still pending.

The first coding turn ended with its dynamic phone tool failed after prolonged
waiting. Its files remained unchanged. Recovery explicitly resumes the same
thread with a new turn; it does not claim to reuse the ended turn.

## Successful technical task continuation

After the closing fix and pre-dial preparation, a real coding task's confirmed
phone result was delivered to its exact pending request. The same resumed turn
then completed the task. The isolated navigation policy now returns an expandable
menu on mobile and retains the desktop header from width 768 upward. Its two
unittests were independently executed: PASS. Request state is ANSWERED, original
thread identity is retained, and delivery turn equals that task's resumed turn.
Owner confirmation of the final decision and latest caller/startup presentation
is pending. This proof is not a production website change.

Setup changes: livekit-cli 2.19.0 and its PortAudio 19.7.0 dependency via Homebrew;
74 locked Python packages inside the project's optional Python 3.12 environment;
private CLI project authorization and local cloud voice selection. Homebrew also
automatically refreshed its taps during CLI installation; no full package upgrade
was performed. No LaunchAgent or energy/security policy was changed.

## Final repository/runtime checks

The cloud installer was executed successfully against its locked 74-package
environment. The 23 tests passed again from a clean committed source archive
without runtime credentials; the archive was then removed. Staged source was
compared against the actual configured credentials and private identities before
publication: none were present. The public main branch was updated, and the
service restarted on the current implementation without initiating another call.

At final dashboard read, Build remained active and next invoice was $0.00.
Credit balances were temporarily unavailable: exact remaining provider allowance
is UNKNOWN. Local conservative reservations stand at 10 of 12 this month,
including real cloud regression tests, leaving two calls before the local stop.
No automatic reset or recharge was performed. This local reservation count is
not the provider's charged usage.
