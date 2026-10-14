# Sources and licenses

Checked 2026-10-13. Provider terms and experimental protocols can change; verify again before use.
The code repository distributes only original bridge source under MIT. No downloaded upstream
source, model, Codex executable, Baresip/Whisper binary or Linphone app is included.

| Component | Inspected contract / license |
| --- | --- |
| Codex | [Official app-server](https://learn.chatgpt.com/docs/app-server), [source](https://github.com/openai/codex), Apache-2.0 executable used separately. Installed experimental schema generated locally; dynamic function tool, thread/start, thread/resume, turn/start, turn/interrupt, item/tool/call, serverRequest/resolved. |
| Baresip | [Source](https://github.com/baresip/baresip), BSD-3-Clause. ctrl_tcp.c documented JSON netstrings; menu static commands; bevent event encoding; include/baresip.h audio source/player callbacks. Own native modules compile against installed 4.12.0 headers. |
| libre | Separate Baresip runtime dependency, BSD-3-Clause; no binary bundled. |
| whisper.cpp | [Source/license](https://github.com/ggml-org/whisper.cpp), MIT; separate local executable. Multilingual base GGML model from [upstream model repository](https://huggingface.co/ggerganov/whisper.cpp), model-card license MIT; SHA-256 pinned by installer. |
| Linphone | [Terms](https://www.linphone.org/en/terms-of-use/), GPL v3 application used unmodified on the user's device; no app code bundled or linked. |
| macOS | Proprietary system TTS via installed `say`; [Apple AVSpeechSynthesizer documentation](https://developer.apple.com/documentation/avfaudio/avspeechsynthesizer) reviewed as an alternative. No Apple voice assets redistributed. |

Costs and provider conditions:
[Getting started](https://www.linphone.org/en/getting-started/) describes a free personal-user
SIP service without support guarantee. [Terms](https://www.linphone.org/en/terms-of-use/)
sections 4–5 describe personal accounts, conditional free use, optional phone number, and
prohibited automated/bulk account creation. No numerical minute quota was found in those
terms; that is not a promise of unlimited future usage. No explicit two-accounts-per-person
entitlement was found. Accounts must remain personal; never automatically provision them
for other people or resell the service. Manual provider acceptance is still needed.

[Push documentation](https://wiki.linphone.org/xwiki/wiki/public/view/Linphone/Sending%20push%20notification%20to%20Linphone%20mobile%20Apps/)
describes server delivery of VoIP push, app re-registration, and iOS CallKit presentation.
This supports the stack choice, not a claim that a particular locked iPhone has rung.
[Privacy policy](https://www.linphone.org/en/privacy-policy/) documents metadata retention,
including 12 months for activity logs, and hosting in France/Germany.

## Live interoperability investigation (2026-10-14)

- Cloudflare public STUN endpoint: https://developers.cloudflare.com/realtime/sfu/get-started/connection-patterns/ . Used only for NAT address discovery, not TURN, SFU, STT or TTS. Public availability is not a service guarantee.
- Linphone STUN returned legacy mandatory attributes rejected by libre 4.12; public Cloudflare STUN allowed actual ringing.
- libre 4.12 SIP request source rejects a SIPS route: https://github.com/baresip/re/blob/v4.12.0/src/sip/request.c . Provider supplied a SIPS Record-Route; isolated patch must preserve TLS and certificate verification.
