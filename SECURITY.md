# Security and privacy

Scope: one macOS user, one configured personal outbound SIP destination, controller-owned
Codex sessions. This is experimental software, not a safety-critical approval system.

- Both control surfaces use Unix sockets in owner-only directories, socket mode 0600.
  PCM sockets are also private. No controller binds 0.0.0.0 or an unauthenticated TCP port.
  The SIP client itself needs network signaling/media; production config enables TLS and
  SRTP with ICE. Actual encrypted provider negotiation is NOT yet verified.
- Outbound destinations are restricted to the exact configured personal Linphone URI.
  No tel:, PSTN, arbitrary domain, caller-name authentication or incoming voice authorization.
- User decisions are data, not shell commands. Subprocesses use argument arrays, never shell=True.
  Dynamic product/design responses do not answer native Codex approvals. File/command approvals
  need an interactive local terminal displaying the exact request and requiring its ID.
  Permissions, MCP elicitation and unfamiliar approval shapes stay pending for native handling.
- A local process running as the same user can read private data and control sockets. Unix
  permissions do not protect against malware with that user's authority or a stolen unlocked Mac.
- config.json is a deliberately small local secret store, plaintext mode 0600 within 0700.
  It contains the required account pair/password and cloud project/voice settings. We do not inspect Keychain
  wholesale, read unrelated secrets, log credentials or put passwords in process arguments.
- SQLite retains questions and confirmed answers so no decisions disappear. These contain private
  task context. Codex also persists its own thread history. Model computation uses the existing
  Codex plan; the confirmed answer is sent to Codex and is not fully local.
- Production audio streams to LiveKit Inference and selected cloud STT/LLM/TTS providers.
  Only the open question and conversation are supplied, not an automatic repository upload.
  SDK recording/observability is disabled; this is not a blanket zero-retention guarantee.
  Credentials remain in the private LiveKit CLI store; local caps do not guarantee provider bills.
- SIP audio is transient; local TTS/STT files are deleted in finally blocks and normal shutdown.
  Hard kill/power loss can leave owner-only temp directories; no unqualified zero-retention promise.
  Logs retain IDs/states/error class only, not transcripts, prompts, SIP URIs or raw SIP packets.
- Linphone's privacy policy documents account/registration metadata and call logs, including
  participants, times and durations; activity logs are retained for 12 months. Provider push
  involves Apple infrastructure. Cloud speech adds the providers described above.
- TLS+SRTP is transport/media protection, not a proof of end-to-end authenticated speaker identity.
  Outgoing peer URI is checked; device/account compromise and call forwarding remain risks.
- Cancellation, restart, timeout, turn mismatch and unknown requests fail closed. Unconfirmed
  speech never produces a successful dynamic decision response. Retry is explicit and bounded.

Before publishing: run tests, inspect staged files and full history for credentials, personal
paths, accounts and transcripts. Only source/docs/synthetic test phrases may be tracked.
Runtime, downloaded source references, model files and local evidence stay under `.local/`.
No third-party executables or model weights are redistributed in this repository.

Report vulnerabilities privately through the repository owner's available private contact route;
do not include live credentials or private transcripts in public issues.

## Experimental Linphone interoperability patches

Installation builds libre 4.12.0 at pinned commit 65555dad439de9d6a81b3ee6092b9c096585249b in `.local/re-sips`. The patch accepts SIPS routes only over verified TLS and rejects insecure transport overrides. A private SRTP module resets both sender and receiver when the negotiated cipher changes. These builds are used only by bridge child processes; global Homebrew libraries remain intact. Upstream portions retain their BSD licenses in `native/RE-LICENSE.txt` and `native/BARESIP-LICENSE.txt`; own code remains MIT. STUN uses the public `stun.cloudflare.com:3478` address-discovery endpoint; no TURN credentials, relay purchase or paid telephone service is configured. STUN providers see public network address metadata.
