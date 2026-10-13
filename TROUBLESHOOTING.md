# Troubleshooting

`./bin/codex-phone doctor` reports installed dependencies and configuration presence, not
successful account registration or CallKit delivery. `status` reports queued questions,
thread/turn states and pending local actions. `logs` contains sanitized transitions.
Private `.local/runtime/daemon.log` contains daemon startup diagnostics; do not publish raw logs.

- **No accounts yet:** configure locally after manual provider registration/email verification.
  Do not invent credentials or dial somebody else's account.
- **Registration not confirmed:** verify account/password, provider reachability and TLS settings.
  Registration is checked before dial; a failed test-call does not establish interoperability.
- **iPhone doesn't ring:** foreground Linphone once, check registration and push settings,
  permissions, Focus/Do Not Disturb and connectivity. Test unlocked, then locked/background,
  then mobile data. A displayed SIP ringing event is not proof that the iPhone rang.
- **No audio / unclear speech:** confirmation is withheld; speak close to the iPhone microphone,
  wait until TTS ends, use a clear pause. Automatic STT language detection supports German/English;
  Swiss German quality is unverified. Fixed RMS gating may miss quiet speech/noisy rooms.
- **Dropped/rejected/offline call:** question remains pending; no automatic redial. Use the local
  answer command or one explicit retry while its original turn remains live.
- **Service restart:** unresolved questions become ORPHANED. Do not answer an obsolete RPC ID.
  Explicitly `resume THREAD_ID` to resume a controller-owned thread and ask the question anew.
- **Mac sleeps/offline:** no call service guarantee. No energy-policy changes are installed.
- **Permission/approval request:** inspect it locally; speech cannot grant it. Unknown approval
  schemas are deliberately not supported. Use a native client rather than guessing a response.
- **Port conflict:** bridge control has no TCP ports; local audio tests allocate isolated SIP ports.
- **Baresip/audio ABI or Codex schema change:** regenerate local schemas with
  `codex app-server generate-json-schema --experimental --out .local/protocol`, compare contracts,
  rebuild native modules and rerun real tests. Do not claim compatibility from version numbers alone.
- **Hard-killed service:** first ensure no owned bridge/Baresip process remains. Inspect only the
  exact bridge-created temp directory before deleting it; never wildcard-delete unrelated `/tmp` data.

Reproduce local SIP/RTP speech: `python3 scripts/test-local-audio.py`.
Run deterministic safety tests: `python3 -m unittest discover -s tests -v`.
Stop: `./bin/codex-phone stop`; uninstall artifacts: `./scripts/uninstall.sh`.
