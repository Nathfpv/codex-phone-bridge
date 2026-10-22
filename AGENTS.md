# codex-phone-bridge

For changes to providers, quotas or recovery, read
`docs/INTEGRATION-2026-10-22.md` and `SECURITY.md` first. Runtime facts come from
the private configuration and actual account UI, not historical acceptance notes.

Verify with the installed voice environment:
`PYTHONPATH=src .local/voice-venv/bin/python -B -m unittest discover -s tests`.
The system Python may skip SDK tests. `scripts/test-cloud-pcm.py` is offline;
`scripts/test-cloud-sip.py --mcp` exercises the composed MCP/controller path with
ONLY a synthetic loopback SIP peer, but requires explicit free-allowance opt-in.
Real iPhone calls need owner authorization; synthetic tests do not prove delivery.

The local reservation ledger records attempts, not cloud credits. Preserve it.
Renew Build-plan evidence only after an authenticated dashboard check for the
selected project. Unknown balance remains UNKNOWN. `can_call` is bounded preflight
eligibility; actual provider connectivity and device delivery remain separate.

The saved proposal must finish successful, uninterrupted, non-silent playback
before a new explicit confirmation can count. A tool call is never spoken consent.
Keep same-request delivery, cancellation and no-replay-after-send invariants.

The installed MAFFEO router is a dependency in another repository. Its root is a
development checkout; production runs from `.worktrees/main`. Reuse its loopback
endpoint and read that project's `AGENTS.md` before changing it. Keep credentials
in their existing private stores and SDK observations distinct from provider bills.

Already-running MCP processes retain imported code. Verify new behavior through
a fresh stdio client; reconnect old clients rather than erasing ledgers or killing
unrelated agent sessions. Runtime selectors provide explicit provider rollback.
