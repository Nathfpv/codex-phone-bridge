# Current MAFFEO voice profile — 2026-10-22

Runtime selection: `dialogue_backend=maffeo`, `recognition_backend=groq`.
Dialogue uses the existing loopback MAFFEO Chat Completions endpoint, exact model
`gpt-oss-120b`, low reasoning and a 512-token completion bound. Groq Whisper uses
only the existing owner-only `~/.groq-key`; it is never copied into bridge config.
LiveKit Fish remains the voice provider. The prior model paths remain explicit
rollback options, not automatic cross-provider/model fallbacks.

A dashboard-verified Build plan has a provider-enforced hard cap. Its project-bound
observation is valid for seven days. Old local reservations remain an audit trail;
a fresh verified profile has no 12-attempt local cap. Unknown balance is not zero
and not unlimited. Never upgrade, reset history or enable paid fallback to fix a
quota error. Groq phone and chat requests share the existing account limits.

The controller reads back the saved proposal itself, checks successful non-silent
uninterrupted audio playout, then requires a new explicit confirmation. A failed
or interrupted readback cannot enable consent. SDK meter observations (audio
seconds, input/output tokens, TTS characters) are saved during the session, including
before failures. They are not invoices or exact remaining shared-project credit.
The final session snapshot is marked closed only after graceful shutdown; a hard
kill can leave partial observations. No additional text/audio recording is made.

The following sections document the original backend and its setup. Current
executed evidence and remaining device gates: [integration record](INTEGRATION-2026-10-22.md).

# Experimental cloud conversation backend

The SIP controller keeps the pending original Codex request. A separate, bounded
German conversation agent discusses only that question and returns a read-back,
explicitly confirmed product/design decision. No security approval is delegated.

Media: existing private Baresip Unix datagrams (16 kHz mono PCM16) → LiveKit Agents
custom AudioInput/AudioOutput → AssemblyAI cloud streaming recognition → Gemma
conversation model → Fish streaming voice → paced Baresip PCM. No additional SIP
trunk, public endpoint, microphone loopback, phone number or WebRTC room is needed
by this direct-IO implementation. Local Silero only detects speech activity; it
does not transcribe. The old Whisper/say call loop is disabled, without fallback.

## Setup

Python 3.12, uv and the existing native SIP installation are required. From the
repository root:

```sh
./scripts/install-cloud.sh
lk cloud auth
./bin/codex-phone cloud-config --project-id YOUR_PROJECT_ID --voice-id FISH_VOICE_ID --free-plan-verified
./bin/codex-phone start
./bin/codex-phone test-call
```

Choose only the free Build plan without payment details. Verify actual allowance
and quota behavior in the dashboard before setting `--free-plan-verified`.
The CLI stores credentials in its private user config; no API secrets belong in
arguments, shell history, Git or logs. The worker reads only the selected project.

Provider free allowances can change. This is NOT an unlimited-free promise.
Production calls reserve one of 12 local calls/month, including failed attempts,
and stop after five minutes or 20 user turns.
These conservative bounds are not a USD billing guarantee. Other project clients
can consume shared credit. No upgrade, automatic recharge or paid fallback is
implemented. Model/API failures preserve the unanswered Codex request.

The initial Fish voice is an official example voice, not verified to be the
owner's preferred preview voice. G.711 still limits the actual phone bandwidth.

## Privacy

Only the question and subsequent conversation enter cloud inference. No automatic
repository upload. Local audio recordings and SDK observability are disabled.
This does not promise that every provider retains zero operational metadata.
The project region and individual inference model regions can differ.

## Verification

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
.local/voice-venv/bin/python scripts/test-cloud-pcm.py
# Consumes free cloud allowance; uses a synthetic caller, no iPhone:
.local/voice-venv/bin/python scripts/test-cloud-sip.py --project YOUR_PROJECT_ID --use-free-allowance
```

Offline tests, synthetic SIP/cloud tests, and actual human iPhone/Codex tests are
separate evidence. See acceptance notes; none substitutes for locked-iPhone E2E.
Stopping uses `codex-phone stop`. `./scripts/uninstall.sh` stops the service and
removes generated native modules and the project-only cloud environment, while
preserving unanswered questions and credentials. Revoke LiveKit authorization
separately. Existing native/SIP uninstall remains documented in INSTALL.md.

Sources: [SDK quickstart](https://docs.livekit.io/agents/start/voice-ai/),
[AssemblyAI model contract](https://docs.livekit.io/agents/models/stt/assemblyai/),
[current prices](https://livekit.com/pricing). Implementation was also checked
against the installed SDK signatures and custom voice IO classes.

## Dependency licenses

Installed LiveKit SDK/Agents/Silero plugin metadata declares Apache-2.0;
ONNX Runtime and PyYAML declare MIT. Own bridge code remains MIT. Cloud services
are external services governed by their own terms; an open-source bridge does
not make hosted speech inference open source or permanently free. No dependency
binaries or provider model weights are committed to this repository.

## Caller presentation and startup

SIP display name is `Codex`. The opening is `Codex hier.` followed directly by
the actual question; there is no spoken cloud-processing or relay announcement.
The initial Fish audio and worker runtime are prepared in RAM before dialing.
This avoids model generation and process startup after the person answers.
`pcm_start_delay_seconds` measures first PCM emission after the connection event,
not the sound reaching the iPhone ear. Actual device delay remains a separate test.
The phone persona is Codex; the implementation still uses a separate conversation
model and must not falsely claim model identity or knowledge of unread files.

A completed new user message expressing clear assent after a saved proposal is
validated by the local decision state. A second discretionary model tool call is
not necessary. Duplicated message IDs, qualifications, corrections and questions
are excluded from automatic consent. Hangup after receipt of confirmed consent
does not erase the answer. Native Codex approval boundaries remain unchanged.
