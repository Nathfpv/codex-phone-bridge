# Acceptance — experimental / PARTIAL

Evidence date: 2026-10-13. Real physical-iPhone tests require the owner's accounts and observations.
The local SIP test uses actual processes, network signaling and audio; the routing unit tests
use a transport double and do not establish phone behavior.

| Test | Status | Evidence / missing gate |
| --- | --- | --- |
| T1 personal SIP registration | BLOCKED_BY_USER | Personal Mac/iPhone accounts not configured; loopback accounts have no provider registration. |
| T2 real free SIP call to iPhone | BLOCKED_BY_USER | Accounts absent; no iPhone call claimed. |
| T3 locked-iPhone CallKit | BLOCKED_BY_USER | Device observation needed. Official support alone is insufficient. |
| T4 two-way participant audio | BLOCKED_BY_USER | Two-way real local SIP/RTP PASSED; real iPhone participant audio pending. |
| T5 STT of SIP speech | BLOCKED_BY_USER | Local real SIP-decoded synthetic German/English speech recognized; human iPhone speech pending. |
| T6 TTS heard by participant | BLOCKED_BY_USER | Local TTS crosses actual RTP and is decoded/transcribed; iPhone audibility pending. |
| T7 genuine question → automatic iPhone call | BLOCKED_BY_USER | Real Codex dynamic question queued and call attempted; safely failed on missing config. |
| T8 right thread/turn | PASS | Real signed-in Codex task, original dynamic request answered locally; wrong-turn/stale/duplicate negative tests pass. Spoken route still blocked. |
| T9 same task continued | BLOCKED_BY_USER | Real same-thread/turn continuation and file creation PASSED with local text answer; phone-mediated continuation pending. |
| T10 missed/rejected call persistence/retry | NOT_TESTED | Restart/persistence/dedup/queue logic tests PASS; real rejected/offline iPhone call pending. |
| T11 mobile data/background/locked | BLOCKED_BY_USER | Device test pending. |
| T12 restart/shutdown/secrets/ports/sandbox | PASS | Executed local unit tests and start/status/stop lifecycle; Unix-only control with restrictive permissions; separate approval path. Hard power loss, sleep behavior and production encrypted provider negotiation NOT_TESTED. |

A complete E2E success must be recorded separately: true required decision → locked iPhone ring
→ audible real question → human SIP answer → confirmed correct transcript → same task continues.
Neither loopback nor local text-routing evidence substitutes for that sequence.
