# codex-phone-bridge

**Experimental / PARTIAL. Real cloud phone-to-Codex continuation has been verified technically. Locked-iPhone ringing and two-way cloud speech were owner-confirmed; reliability and final presentation checks remain open.**

A local macOS bridge for product/design decisions during controller-owned Codex tasks:
Codex asks a structured question, Baresip calls the owner's personal Linphone SIP account,
an experimental LiveKit backend streams SIP audio through cloud recognition, a separate
conversation model, and Fish voice. Local transcription is disabled for calls.
The owner must confirm the read-back before the answer is returned to the pending request
in the same Codex thread and turn. An unanswered call leaves the question unresolved.

This is SIP-to-SIP over the Internet without PSTN, Twilio or a new phone number.
Cloud speech consumes provider free allowances; unlimited-free operation is not promised.
No automatic paid fallback or recharge is implemented. Existing Internet/electricity
and Codex plan usage still apply.
Linphone's free service is conditional on its current terms and has no service guarantee.
The iOS app uses provider push and CallKit; actual lock-screen delivery depends on the device,
account, push registration and network. Do not infer a successful phone test from a local test.

## Quick start

Requirements: Apple Silicon macOS, Python 3.9–3.12, Xcode command-line tools,
Homebrew, signed-in Codex CLI (tested: 0.162.0-alpha.17.2), Baresip 4.12.0,
CMake, and isolated SIP dependency builds. The cloud worker uses a separate Python 3.12
environment. Complete [cloud voice setup](docs/CLOUD-VOICE.md) before calling.

```sh
./scripts/install.sh
./bin/codex-phone doctor
./bin/codex-phone config
./bin/codex-phone register
./bin/codex-phone start
./bin/codex-phone test-call
./bin/codex-phone launch --cwd /absolute/path/to/task 'Implement the task; ask phone_decision for a required design decision.'
./bin/codex-phone status
./bin/codex-phone stop
```

Use `./bin/codex-phone` directly, or add this repository's `bin` directory to your PATH yourself.
The installer does not modify shell startup files or global Codex settings.
Create your own two personal accounts manually; never send a SIP password in chat.
On iPhone use the official Linphone account setup, allow microphone and notifications,
and verify registration. See [INSTALL.md](INSTALL.md).

Additional real commands: `logs`, `answer QUESTION_ID TEXT`, `retry QUESTION_ID`,
`resume THREAD_ID [--prompt TEXT]`, `inspect-approval REQUEST_ID`, and `approval REQUEST_ID --decision accept|decline|cancel`.
Security approvals require an interactive local terminal and are never answered by speech.
`resume` explicitly resumes an owned thread after interruption/restart; it does not reuse a
stale server request. Old questions stay as ORPHANED evidence and must be asked again.

## Verified scope

The cloud migration has 23 passing safety/protocol tests plus real local SIP/cloud
tests and a real iPhone decision delivered to the exact pending Codex request.
That coding turn then implemented the isolated task; its two tests passed. See
[cloud acceptance](docs/CLOUD-ACCEPTANCE.md) for current evidence and remaining limits.
The Whisper-based items below are historical v1 evidence.

- Automated isolation/persistence/protocol tests execute with `python3 -m unittest discover -s tests -v`.
- `python3 scripts/test-local-audio.py` uses two real Baresip processes, SIP signaling and RTP
  with TTS → PCM → RTP → decoded PCM → Whisper in both directions. It does **not** call an iPhone.
- A real signed-in Codex task initiated an iPhone SIP call, received a spoken and read-back-confirmed
  design decision through local Whisper, and created its demo in the original thread/turn. The owner
  confirmed complete audible question/read-back, but the iPhone was unlocked; locked CallKit is still open.
- See [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) for T1–T12; no overall E2E PASS is claimed.

An arbitrary pre-existing Codex app/CLI thread is not automatically intercepted. Launch through
this controller. Generic text questions do not constitute a reliable event; the explicit
`phone_decision` tool is the integration contract. Built-in user-input/permission/MCP approvals
are retained for local handling, never routed into phone authorization.

No LaunchAgent is installed while the real device gate is open. The Mac must be awake and
online; this bridge does not change energy/security policy or promise delivery during sleep.
Incoming user calls are rejected in v1. Caller display name is not authentication.

[Architecture](ARCHITECTURE.md) · [Security](SECURITY.md) · [Troubleshooting](TROUBLESHOOTING.md)
· [Dependency licenses and source contracts](docs/SOURCES.md)
