# Acceptance — experimental / PARTIAL

Evidence date: 2026-10-14. Real physical-iPhone tests require the owner's accounts and observations.
The local SIP test uses actual processes, network signaling and audio; the routing unit tests
use a transport double and do not establish phone behavior.

| Test | Status | Evidence / missing gate |
| --- | --- | --- |
| T1 personal SIP registration | PASS | Real Mac provider registration returned 200 and REGISTERED with positive expiry. Owner reports iPhone app signed in; actual incoming call reached it. |
| T2 real free SIP call to iPhone | PASS | Real SIP call reached owner iPhone; owner confirmed incoming call. No PSTN or paid voice API used. Audio is a separate failing gate. |
| T3 locked-iPhone CallKit | BLOCKED_BY_USER | Device observation needed. Official support alone is insufficient. |
| T4 two-way participant audio | PASS | Owner confirmed complete real iPhone question and read-back; human speech reached local Whisper. Initial failures repaired with private SIPS/SRTP patches. |
| T5 STT of SIP speech | PASS | Human speech received over real iPhone SIP stream, transcribed locally and confirmed during the call; linked to live request. |
| T6 TTS heard by participant | PASS | Owner confirmed complete spoken question and read-back on iPhone after speaker activation. |
| T7 genuine question → automatic iPhone call | PASS | Controller-owned real Codex design question automatically triggered the SIP call. |
| T8 right thread/turn | PASS | Confirmed SIP speech delivered to original live dynamic request, same thread/turn; wrong-turn/stale/duplicate tests also pass. |
| T9 same task continued | PASS | Same live turn completed after confirmed SIP decision, creating a responsive HTML demo in isolated workspace. This call used an unlocked iPhone. |
| T10 missed/rejected call persistence/retry | NOT_TESTED | Restart/persistence/dedup/queue logic tests PASS; real rejected/offline iPhone call pending. |
| T11 mobile data/background/locked | BLOCKED_BY_USER | Device test pending. |
| T12 restart/shutdown/secrets/ports/sandbox | PASS | Executed local unit tests and start/status/stop lifecycle; Unix-only control with restrictive permissions; separate approval path. Hard power loss, sleep behavior and production encrypted provider negotiation NOT_TESTED. |

A complete E2E success must be recorded separately: true required decision → locked iPhone ring
→ audible real question → human SIP answer → confirmed correct transcript → same task continues.
Neither loopback nor local text-routing evidence substitutes for that sequence.
