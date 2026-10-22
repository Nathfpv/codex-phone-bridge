# Codex and GitHub Copilot integration

This remains one standalone project/repository. No copy of the bridge is placed
inside other development projects. The local stdio MCP executable exposes:

- `phone_status`: bridge state, separate budget eligibility, explicit preflight checks and UNKNOWN provider balance.
- `phone_decision(kind, question)`: one bounded product/design decision. Include
  options/context directly in the question, at most 2000 characters.

The common daemon serializes calls. It generates a distinct persistent identity
for each external request. A confirmed answer returns directly on that request's
connection and then through its original MCP invocation. It never resumes another
Codex/Copilot session through guessed thread IDs. A cancelled invocation or closed
client connection cancels its operation; unresolved records survive as ORPHANED.
They are evidence, not requests that can be delivered to a new session silently.
No automatic retries occur. Each external invocation has a 600-second deadline;
phone conversations remain capped at 300 seconds. The MCP client timeout is 900
seconds and the private daemon-response timeout 650 seconds. Cancellation fails
closed when a conversation exceeds these bounds.

## Register on this Mac

Complete the SIP/cloud installation first, then:

```sh
./bin/codex-phone start
./.local/voice-venv/bin/python scripts/register-agents.py
```

The idempotent registration updates only `codex-phone` in the user-level Codex
TOML and Copilot MCP JSON. It preserves unrelated configuration values and rolls
back the MCP files if registration fails. It appends the marked policy from
[AGENT-POLICY.md](AGENT-POLICY.md) to both personal instruction files when absent.
Restart existing Codex/Copilot sessions to load the added server/instructions.
An existing running chat is not proven to hot-load a newly registered server.

The policy prioritizes phone calls for blocking product/design choices while
ordinary implementation proceeds autonomously. A status check avoids calls when
the local quota is exhausted. Tool availability is guidance, not a guarantee
that every model will identify every possible blocking decision.

Only `phone_decision` and `phone_status` are preapproved in Codex. Copilot retains
its ordinary per-project tool permission flow; approve only these two tools when
asked. For a deliberate noninteractive Copilot invocation, explicit narrow flags
are supported:

```sh
copilot --allow-tool='codex-phone(phone_status)' \
  --allow-tool='codex-phone(phone_decision)' -p 'Your development task'
```

There is no blanket shell/file permission grant or voice-based security approval.
Fresh MCP adapters start a missing daemon before sending a request. The Mac must be awake. There is no new LaunchAgent. Existing imported adapters require reconnection to load code changes.
Remote/cloud-hosted agents cannot access this local stdio server automatically.
The installed GitHub Copilot desktop app 1.1.29 also reads the shared Copilot
configuration. Its Customize → Installed page shows codex-phone as Connected
and enabled. An actual desktop chat invoked Phone Status and received the real
daemon state. VS Code is installed but has no Copilot extension installed in the
checked profile; no unrelated extension was installed. Browser/cloud Copilot and
other IDE clients are not covered by this local desktop proof.

## Executed checks (2026-10-15)

- PASS: 30 automated tests, including real stdio discovery, routing fixtures,
  failure handling, cancellation on disconnect and isolated external identities.
  Fixtures are not telephone acceptance.
- PASS: real installed Codex CLI discovers and invokes both tools. After narrowly
  preapproving these tools, the decision call reached the real daemon and returned
  the actual local-limit failure. The same agent task finished with no assumed
  decision. Its first attempt was blocked by tool approval before dispatch.
- PASS: real installed Copilot CLI discovers and invokes both tools, receives the
  real local-limit failure and leaves the design decision unresolved.
- PASS: normal GitHub Copilot desktop app 1.1.29 shows the server Connected
  and enabled. A status-only prompt in the bridge project completed with one
  actual tool, Codex Phone · Phone Status, returning IDLE, 12/12, can_call=false
  and provider allowance UNKNOWN. No call, file edit or quota change occurred.
  The project was opened in the app; repository-wide trust was skipped.
- PASS: registration repeated without duplicate entries or unrelated value changes.
- BLOCKED: new real Codex-MCP and Copilot-MCP phone → spoken confirmation →
  continuation tests. Local guard is already at 12/12; provider remaining free
  allowance is UNKNOWN. No guard reset, payment or paid fallback was performed.
- Historical real locked-iPhone cloud conversation and same-task Codex continuation
  are documented in [CLOUD-ACCEPTANCE.md](CLOUD-ACCEPTANCE.md). They used the original
  controller integration and do not substitute for the new MCP positive-path tests.

## Privacy and removal

Tool input questions and confirmed answers are visible to the invoking coding
agent and its normal session storage. Speech traverses the configured cloud STT,
dialogue and TTS providers. No additional transcript/audio recordings are added by
this MCP adapter. Credentials remain in the existing private stores, not MCP
configuration or process arguments. The adapter exposes no network listener;
the daemon uses a private Unix socket on this Mac. Same-user processes remain
inside the existing local trust boundary.

```sh
./.local/voice-venv/bin/python scripts/unregister-agents.py
./bin/codex-phone stop
# Optional: existing project dependency uninstaller
./scripts/uninstall.sh
```

Unregistration removes only this executable's matching entries and marked policy
blocks. It preserves other servers and instructions. Restart client sessions.

Official interfaces checked: [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp),
[Copilot CLI MCP](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers),
[Copilot personal instructions](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference).
