# Completion recovery — 2026-10-23

The owner clarified that the last call was ended manually after repeated spoken
assent. The worker returned no confirmed decision. Private numeric diagnostics
showed 19 final speech transcripts, but no proposal or confirmation events.
This establishes that the formal proposal stage was never reached; it does not
reconstruct the caller's exact recognized words (transcripts are not recorded).

Two reproducible defects were addressed:

- The model could keep asking questions without calling `propose_decision`.
  `DecisionAgent` now requests that named tool when the latest user message is
  an unambiguous affirmative and no proposal exists. The model still summarizes
  the conversation; the controller still reads the saved proposal aloud and
  requires a NEW affirmative after successful playback. A tool-result continuation
  cannot recursively force another proposal. Qualified assent and questions keep
  the normal conversational path.
- Explicit finish phrases such as “Ja, wir schicken ab” and “Ja, wir schliessen ab”
  were rejected by the confirmation classifier. These bounded phrases now count;
  negations, conditions and additional instructions still do not.

The same classifier owns both the proposal handoff and final confirmation syntax.
No call is replayed and no failed historical call is retrospectively marked confirmed.

Executed checks:

- Confirmation regression reproduced rejection on the original implementation,
  then passed with the change; readback and new-turn gates remain enforced.
- Actual AgentSession + actual OpenAI plugin + loopback HTTP regression reproduced
  endless chat when the model omitted the proposal. The new forced choice executes
  exactly one proposal and leaves it unconfirmed. Negative cases cover qualified
  assent, questions, refusal and preservation of an existing proposal.
- Existing MAFFEO endpoint accepted the named tool choice and produced the expected
  synthetic mobile/desktop proposal in 0.535 s, finish_reason=tool_calls.

- Full installed voice-environment suite: 53 tests PASS.
- Fresh stdio MCP + controller + loopback SIP/RTP + real MAFFEO/Groq/Fish:
  PASS using synthetic spoken “Ja, wir schicken ab”; confirmed response returned
  to the originating invocation and persisted ANSWERED, exactly one call.
  468480 audible return bytes; first audible local RTP 0.129 s.

Independent Claude review found no code-level blockers and requested backend
compatibility and preemptive-generation checks. The real backend check above
passed. Installed SDK source defaults preemptive generation to enabled, so this
session now explicitly disables it: proposal forcing uses completed input rather
than speculative partial assent. Final repeated composed check with that setting:
PASS, 462080 audible bytes, first local audible RTP 0.130 s. Full suite still
53 tests PASS.

No additional human call is authorized or required for these automated checks.
A subsequent real-device completion remains unverified until observed.
