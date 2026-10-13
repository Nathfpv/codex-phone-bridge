# Installation

1. Inspect `./scripts/install.sh`. It builds two native modules, installs only missing
   Baresip/Whisper formulae, and downloads a SHA-256-verified multilingual base model from
   the upstream Whisper model repository. Homebrew may update transitive dependencies;
   no sudo, full Homebrew upgrade, shell profile change or LaunchAgent is used.
2. Use an existing Codex CLI signed in with ChatGPT. `codex login status` should say ChatGPT;
   API-key-only authentication is rejected to avoid accidentally creating metered API costs.
3. Install [official Linphone on iOS](https://www.linphone.org/en/getting-started/).
   Select a Linphone account, rather than an unrelated third-party provider preset.
   Create a personal account manually and validate the email. Phone number is optional
   in the provider's web email-registration route. Enable microphone, notifications and
   incoming-call/push permissions offered by the app. Check that the account is registered.
4. Manually create a separate personal Mac account at
   https://subscribe.linphone.org/register/email. Do not share accounts with other people.
   Current documentation does not explicitly promise two accounts per person; if creation
   is refused, stop and establish the provider's permitted configuration. Do not evade limits.
5. Run `./bin/codex-phone config` in your local interactive terminal. Supply the two full
   `sip:username@sip.linphone.org` addresses and the Mac password with hidden input.
   Username/domain must be your own; no mobile telephone number is dialed.
6. Run start and test-call while the iPhone is unlocked first. Take the call, listen to the
   test question, speak a sentence, then say exactly “Antwort bestätigen” after read-back.
   Repeat with screen locked and Linphone in background, then mobile data if available.
   Record what caller/app text appears and whether both audio directions work. Do not
   claim PASS based only on a successful Mac command.

The default runtime is the checkout's ignored `.local/runtime/`, with directory mode 0700,
configuration/database mode 0600. The SIP password is in that private local secret store,
not Keychain; protect your account and disk accordingly. Baresip gets a temporary mode-0600
accounts file because its interface requires a credential. Credentials never enter argv.
During each call private sockets and audio files live in an owner-only temporary directory;
normal shutdown removes it. An abrupt kill may leave private temporary files: see troubleshooting.

No global command symlink is installed. `./bin/codex-phone` works directly; shell PATH setup
is optional and manual. `CODEX_PHONE_HOME` can select another private runtime location.
No `.env` loader exists. Quiet hours can be configured as a list of local hour numbers in
private config `quiet_hours`, e.g. `[0,1,2,3,4,5,6,23]`. There is no automatic retry after them;
the question waits for an explicit local retry or answer.

Deinstall bridge-generated artifacts with `./scripts/uninstall.sh`. This preserves your
private unanswered questions and credentials. It prints their location for explicit manual
retention/deletion. It never removes shared Homebrew dependencies or other projects.
