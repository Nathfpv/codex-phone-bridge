# Unabhaengige Claude-Code-Umsetzungspruefung

Datum: 24.10.2026. Snapshot: f10bb92. Autor: lokale Claude Code CLI 2.1.308.
Modellmetadaten: claude-opus-5-5[1m]
Methode: unveraenderter Quellcode-Snapshot und vorhandene Audit-/Planvorlage; keine Tools, keine Implementierung, keine Anrufe. Aussagen im Bericht sind Review, kein Laufzeitnachweis.

# Unabhängiger Review: Calling-Umsetzungsplan für codex-phone-bridge (Snapshot `f10bb92`)

**Grundlage:** Nur die übergebenen Dateien. `voice_models.py`, `mcp_server.py`, `storage.py`, die Tests und die installierte LiveKit-Version 1.8.8 liegen mir nicht vor. Aussagen darüber sind als **zu prüfen** markiert. Ich habe nichts ausgeführt, nichts geändert und niemanden angerufen. Kein Punkt dieses Berichts ist PASS.

---

## 1. Urteil in drei Sätzen

Die Richtung des Codex-Plans stimmt: ein reiner `CallController`, eine gemeinsame Session-Fabrik, ein typisiertes Worker-Protokoll und das Auflegen durch Parent/SIP. In drei Punkten widerspreche ich:

- Der Plan bündelt Providerwechsel (AssemblyAI, Cartesia, `turn_detection='stt'`) mit der Steuerungsänderung.
- Die Zustandsmaschine ist zu breit geschnitten.
- Zwei echte Zustimmungslücken im aktuellen Code fehlen im Plan (Abschnitt 2.1 und 2.2). Sie sind schwerer als die Fragment-Frage.

Der sinnvollste Weg:

1. Controller, Lebenszyklus und Unterbrechbarkeit **auf dem bestehenden Provider-Stack** bauen und offline beweisen.
2. Danach Provider einzeln als A/B-Profile messen.

---

## 2. Befunde im Code, die der Plan nicht abdeckt

### 2.1 Zustimmung zu einem veralteten Vorschlag nach einer Korrektur (L3, schwerwiegend)

`Decision.confirm()` prüft nur vier Dinge: Es gibt einen Vorschlag, `read_back_at` ist gesetzt, `turn > read_back_at`, und der *letzte* Text ist eine Zustimmung. Ein dazwischenliegender Nicht-Zustimmungs-Turn entwertet nichts.

Ablauf:

1. Readback von X.
2. Nutzer: „Nein, eher Y.“ → `confirmation_pending`.
3. Das LLM fragt nach: „Meinst du Y mit Z?“
4. Nutzer: „Ja.“

`item_added` ruft `decision.confirm()` auf und liefert **X** aus, sofern das LLM nicht vorher `propose_decision(Y)` aufgerufen hat. Das verletzt die Invariante „aktueller, vollständig vorgelesener Vorschlag“ direkt.

**Regel für den Controller:** Zustimmung zählt nur im **ersten** Nutzer-Turn nach dem vollständigen Readback. Jeder andere Nutzer-Turn und jede Agentenausgabe außer dem Readback beendet `AWAITING_CONFIRM`.

### 2.2 Readback-Wettlauf zwischen zwei Vorschlägen (L3, plausibel)

`propose()` überschreibt `proposal` und setzt `read_back_at=None`. Ein noch laufendes `read_back_proposal` für den alten Text ruft danach `decision.read_back()` auf und markiert damit den **neuen, ungehörten** Text als vorgelesen.

Das tritt auf, wenn das SDK parallele Tool-Aufrufe ausführt. Ob es das tut, ist für 1.8.8 und das MAFFEO-Modell **zu prüfen**. Abhilfe: versionierter Readback wie im Plan, zusätzlich in `DECISION` parallele Tool-Aufrufe abschalten oder serialisieren.

### 2.3 Sprachbeginn vor Readback-Ende zählt heute als „neue“ Äußerung

Die Turn-Zählung ordnet nach dem Zeitpunkt, an dem die Nachricht hinzugefügt wird, nicht nach dem Sprechbeginn. Sobald der Readback unterbrechbar wird, kann ein „Ja“ zählen, obwohl die Person schon in die letzten Silben hineingesprochen hat, unterhalb der Unterbrechungsschwelle.

**Regel:** Der VAD-Sprechbeginn des Zustimmungs-Turns (`user_state_changed → speaking`, im Adapter monoton gestempelt) muss **nach** dem letzten gesendeten Readback-Paket liegen. Dieses Kriterium ist lokal konservativ, aber nicht vollständig. Die Telefonlatenz zum iPhone bleibt eine messbare Restunsicherheit.

### 2.4 Nacktes „Ja“ mit anschließender Einschränkung

„Ja … aber nur, wenn Z“ mit Denkpause dazwischen: Der erste Turn bestätigt sofort. Der Plan behandelt Fragmente, aber nicht ein vollständiges „Ja“, auf das eine Einschränkung folgt.

**Vorschlag:** ein Commit-Aufschub. Nach einem gültigen Zustimmungs-Turn wartet der Controller ein kurzes Fenster ab dem Turn-Ende-Ereignis. Setzt in diesem Fenster erneute Sprache ein, wird der Commit verworfen und der Text zusammengeführt. Der Wert wird separat gemessen, nicht aus VAD- und Endpointing-Schwellen addiert. Das kostet höchstens Bruchteile einer Sekunde beim Abschluss, nicht beim normalen Dialog.

### 2.5 OPEN-Modus scheitert am Turn-Limit als Fehler

`item_added` ruft `decision.heard()` auch im OPEN-Modus auf. Ab dem 21. Nutzer-Turn wird `RuntimeError('Conversation turn limit reached')` geworfen. Das ergibt eine Fehler-Payload und damit `FAILED`. Ein freies Gespräch endet so als technischer Fehler.

### 2.6 Der bestehende OPEN-`end_conversation` legt nur zufällig richtig auf

Der Ablauf heute:

1. Das Tool setzt `result`.
2. `report()` schreibt die erste stdout-Zeile.
3. `converse` kehrt zurück.
4. `prepared.close()` schickt SIGTERM.
5. Danach folgt `sip.close()` → `hangup`.

Folgen:

- Das „Bis bald.“ wird abgeschnitten.
- Der Worker-`finally` läuft nicht, weil es keinen SIGTERM-Handler gibt.
- Das Tool gibt ein dict zurück (`reply_required=True`), es kann also parallel noch eine LLM-Antwort entstehen.
- Das Auflegen hängt allein am LLM, ist also nicht deterministisch.
- `'Gespräch beendet'` steht im Feld `answer`, wo sonst Entscheidungen stehen. Die Bridge ignoriert den Wert im OPEN-Modus, aber dieselbe Struktur ist eine Fehlerquelle.

### 2.7 `sip.close()` beweist kein Auflegen

`hangup()` verschluckt `RuntimeError`, `OSError` und Timeout, schließt sofort den Writer und beendet baresip. Auf `CALL_CLOSED` wird nicht gewartet.

`disconnected` wird außerdem auch bei `CONTROL_LOST` gesetzt (`read_events`). Ein gesetztes `disconnected` beweist also kein `CALL_CLOSED`.

**Widerspruch zum Plan:** Auch ein `CALL_CLOSED` nach lokalem Hangup belegt nur, dass der **lokale Dialog beendet** ist. Dass das iPhone den BYE erhalten und die Verbindung getrennt hat, beweist es nicht. Dafür gibt es zwei getrennte Felder: `local_dialog_closed` und `device_hangup_observed`. Das zweite lässt sich nur im Menschentest belegen.

### 2.8 Weitere Lücken

- Worker-`stderr=DEVNULL` verstößt gegen die globale Logging-Regel.
- `proc.stdin.close()` direkt nach `connected` macht jede spätere Rückmeldung vom Parent an den Worker unmöglich. Für ein `outcome_ack` muss stdin offen bleiben.

---

## 3. Widersprüche zum Codex-Plan

1. **Providerwechsel gehört nicht in die erste Implementierung.**
   - Der Plan nennt AssemblyAI-Streaming, `turn_detection='stt'` und Cartesia „bevorzugt“. Ein gleichzeitiger Wechsel verändert Fragmentbildung, Turn-Ende, Echo-Verhalten und Latenz auf einmal. Ein PASS oder FAIL wäre dann keiner Ursache zuordenbar.
   - Unterbrechung funktioniert über Silero-VAD auch mit Groq-Batch-Erkennung.
   - Ob der vorhandene LiveKit-Zugang AssemblyAI mit `de` und Cartesia mit einer deutschen Stimme tatsächlich anbietet, ist für mich **unbestätigt**. Ich hatte keine Webtools.
   - `turn_detection='stt'` überlässt das Turn-Ende der Provider-Heuristik. Ob diese Denkpausen respektiert, ist unbewiesen und widerspricht im Zweifel der Anforderung.
   - Reihenfolge daher: Controller und Lebenszyklus auf dem heutigen Stack, danach STT A/B, danach Stimme A/B.

2. **Die Zustandsmaschine spiegelt SDK-Zustände.**
   - `THINKING` und `SPEAKING` sind Tatsachen des SDK (`agent_state_changed`), keine Entscheidungssemantik. Spiegelt der Controller sie, wird er flach: zwei Quellen derselben Wahrheit, mehr Interface, mehr Testfläche.
   - Der Controller sollte nur Zustimmung, Halten und Schließen besitzen.

3. **„Ja“ nach abgebrochenem Readback.**
   - Der Plan sagt: „bietet einen kurzen erneuten Readback an“. Das bedeutet einen weiteren LLM-Umlauf und eine weitere Frage.
   - Besser: Der Controller liest **sofort selbst** dieselbe Fassung als neue Version erneut vor. Das wahrscheinliche Anliegen ist Zustimmung. Ein deterministischer Readback ohne LLM ist schneller und kann nichts umformulieren.

4. **VAD-Unterbrechung bei 0,3 s.**
   - Richtig ist die Unterscheidung: Pausieren ist dank `resume_false_interruption` und echtem `pause/resume` umkehrbar, also darf es früh greifen. Das endgültige Löschen der Ausgabe sollte von einem nicht leeren Transkript abhängen.
   - 0,3 s ist ein Kandidat und erst nach dem Echo-Gate zulässig.
   - `min_interruption_words` größer null hat mit Batch-Erkennung kaum Wirkung (Interims fehlen). Dazu gibt es keine Aussage, bevor Streaming gemessen ist.

5. **AEC-Warmup.**
   - Der Plan will ihn „erst nach Echo-Prüfung entfernen“. Solange er aktiv ist, kann die Begrüßung grundsätzlich nicht unterbrochen werden. Das Ziel „jederzeit unterbrechbar“ ist mit Warmup also nicht erfüllbar.
   - Ehrliche Formulierung: Die Anforderung hängt vom Echo-Gate ab. Fällt dieses durch, ist R2 nicht erfüllt. Ein Kompromiss (z. B. eine nur ca. 1 s lange Begrüßung) muss offen als Kompromiss benannt werden.

6. **„Ja, passt, leg auf“.**
   - Dem vorgeschlagenen Default stimme ich zu, nur in `AWAITING_CONFIRM(v)`: bestätigen und beenden. Andernfalls ginge eine klar geäußerte Entscheidung verloren.
   - Bedingung: Der Zustimmungsteil muss *für sich* den strengen Klassifizierer bestehen.
   - Der Abschied sagt hörbar, was passiert ist: „Festgehalten. Tschüss.“ beziehungsweise „Nichts festgehalten. Tschüss.“
   - Die Produktsemantik muss der Eigentümer trotzdem bestätigen. Das ist ein Gate.

7. **ENDED_BY_REQUEST bei Codex-Thread-Fragen.**
   - Der Plan sagt nicht, was mit dem wartenden `phone_decision`-RPC geschieht. Heute bleibt er bis zur Deadline (900 s) offen, danach folgt `turn/interrupt`.
   - Vorschlag: Die Bridge antwortet sofort mit einem ausdrücklichen **Nicht-Entscheidungs**-Ergebnis, etwa `{"decision": null, "status": "ended_by_owner_no_decision"}`. Ein unbestätigter Vorschlagstext wird nie mitgeschickt, nur ein Flag `unconfirmed_proposal_existed`.

---

## 4. Zielarchitektur nach Deep-Module-Prinzip

**Modul 1: `call_control.py`** (rein, ohne SDK und I/O, Uhr injiziert). Kleines Interface:

```python
ctl = CallController(mode, now)
ctl.user_turn(msg_id, text, onset) -> Step       # RESPOND | SUPPRESS | READ_BACK(v, text) | CLOSE(outcome, farewell_key)
ctl.propose(text) -> Step                        # READ_BACK(v, text) | REJECT(reason)
ctl.readback_finished(v, complete, ended_at) -> Step
ctl.agent_spoke()                                # beendet AWAITING
ctl.tick() -> Step                               # Commit-Aufschub, Limits
ctl.peer_closed() / ctl.timed_out() -> Step
ctl.outcome                                      # Outcome(kind, decision?, version?, reason)
```

Intern, als interne Seams mit Tabellentests:

- `classify(text) -> CONFIRM | END | CONFIRM_END | HOLD | INCOMPLETE | OTHER`
- `msg_id`-Deduplizierung
- Limits

Der Controller **gibt Schritte zurück** und erzeugt keine Seiteneffekte. Gegen dieses Interface laufen zwei Adapter, der SDK-Adapter und ein Test-Fake. Das ist eine echte Naht.

**Zustandsmaschine `DECISION`:**

```
NONE ──propose──▶ READING_BACK(v)
READING_BACK(v) ──finished(v, complete)──▶ AWAITING(v, t_end)
READING_BACK(v) ──finished(v, ¬complete)──▶ DRAFT(v)
AWAITING(v) ──CONFIRM, erster Turn, onset ≥ t_end──▶ PENDING_COMMIT(v)
PENDING_COMMIT(v) ──tick, Fenster ohne neue Sprache──▶ COMMITTED(v) → CLOSING
PENDING_COMMIT(v) ──neue Sprache──▶ DRAFT(v)   (Text zusammenführen)
AWAITING(v) ──OTHER | agent_spoke──▶ DRAFT(v)
DRAFT(v) ──CONFIRM──▶ READ_BACK(v+1, derselbe Text)
* ──propose(neu)──▶ READING_BACK(v+1)   (alte Callbacks wirkungslos)
* ──END──▶ CLOSING(ENDED_BY_REQUEST)
AWAITING(v) ──CONFIRM_END──▶ PENDING_COMMIT(v, then_close)
* ──peer_closed──▶ CLOSED(PEER_CLOSED; COMMITTED bleibt COMMITTED)
```

`HOLD` ist ein orthogonales Flag. In diesem Zustand werden LLM-Antworten mit `SUPPRESS` unterdrückt. Der nächste Nutzer-Turn, der kein `HOLD` ist, hebt das Flag auf. Das 300-s-Limit bleibt.

**`OPEN`:** nur `LISTENING`, `HOLD`, `CLOSING` und `CLOSED`. `propose` liefert immer `REJECT`, und das Werkzeug ist dort gar nicht registriert. Ein Outcome mit `decision` ist im OPEN-Modus per Konstruktion unmöglich. Das ist ein eigener Test.

**Modul 2: `voice_session.py`.** `build_session(profile, stt, llm, tts, vad)` liefert eine `AgentSession` mit allen Produktionsoptionen. Tests verwenden dieselbe Fabrik und injizieren nur die Modelle.

**Modul 3: `worker_protocol.py`** (rein). `encode(type, **fields)`, `decode(line) -> Message | ProtocolError`, Versionskonstante, Größenlimit. Worker und Parent nutzen dasselbe Modul. Die Python-Versionen sind verschieden (3.12 und 3.9), also nur Syntax verwenden, die 3.9 versteht.

`voice_decision.Decision` und die Forcing-Logik in `DecisionAgent` gehen im Controller auf.

**Deletion-Test:** Nach der Migration sind beide löschbar, ohne dass Komplexität bei den Aufrufern wiederkehrt. Das ist das Ziel. `DecisionAgent` wird zu einem `CallAgent` mit `on_user_turn_completed`. Es wird in beiden Modi genutzt, nur die Tool-Liste unterscheidet sich.

---

## 5. Änderungen je Datei

**`src/codex_phone/call_control.py` (neu)**
- Inhalt wie in Abschnitt 4.
- Klassifizierer-Regeln:
  - Zustimmung = affirmativer Kopf aus geschlossener Menge plus optionale Abschlussformel aus geschlossener Menge.
  - Abgelehnt werden:
    - nacktes `okay`/`ok`
    - `ja ja`
    - Fragezeichen
    - alles, was auf Pronomen, Konjunktion oder Füllwort endet (`ich`, `du`, `es`, `das`, `und`, `aber`, `weil`, `ähm`, `also`)
    - jedes Inhaltswort außerhalb der Menge
  - END wird nur als ganze Äußerung oder klar abgegrenzter Satz erkannt:
    - zählt: „leg auf“, „auflegen“, „beende/schließ das Gespräch“, „tschüss“, „das war's“
    - zählt nicht: Negation („leg nicht auf“), Frage („was heißt leg auf?“), Zitat oder Konditional („wenn …, dann leg auf“)
  - HOLD: „Moment“, „warte“, „ich überlege“, „lass mich nachdenken“.

**`src/codex_phone/voice_session.py` (neu)**

| Option | Wert |
|---|---|
| `allow_interruptions` | `True` |
| `discard_audio_if_uninterruptible` | `False` |
| `aec_warmup_duration` | per Profil-Flag, Ziel `None` nach Echo-Gate |
| `turn_detection` | vorerst `'vad'` |
| `min_endpointing_delay` | vorerst unverändert, nur nach Messung tunen |
| `resume_false_interruption` | `True` |
| `preemptive_generation` | `False` |
| `min_interruption_duration` | Profilwert (Kandidat 0,3 s) |

Ob alle Parameternamen in 1.8.8 so heißen, ist **zu prüfen**. `discard_audio_if_uninterruptible` und `aec_warmup_duration` stammen aus dem Audit.

**`src/codex_phone/cloud_voice.py`** (wird zum SDK-Adapter)
- Session über `build_session`.
- `CallAgent.on_user_turn_completed(turn_ctx, new_message)`:
  - Deduplizierung über `new_message.id`
  - erster VAD-Sprechbeginn seit dem letzten Turn als `onset`
  - `ctl.user_turn` aufrufen, Step ausführen
  - bei allem außer `RESPOND`: `raise StopResponse`
- **Zu prüfen:** ob die Nutzernachricht bei `StopResponse` im Chat-Kontext bleibt. Ein Test muss belegen, dass kein Text verloren geht.
- Der Bestätigungspfad in `item_added` entfällt; dort bleibt nur Diagnose.
- `confirm_decision` entfällt.
- `propose_decision`:
  - `ctl.propose` aufrufen, bei `READ_BACK` ein unterbrechbares `say` ausführen
  - Vollständigkeit über `playout_complete(handle, out, before)` bewerten: kein Exception, nicht unterbrochen, Samples größer null, keine neuen `failed_playbacks`
  - danach `ctl.readback_finished(v, …)`
  - Rückgabe `ToolResult(output=…, reply_required=False)`
- Ein gemeinsames `end_call`-Tool für beide Modi ruft denselben Controller-Pfad (END) auf. Ebenfalls `reply_required=False`.
- `agent_state_changed → speaking`, sofern die Ausgabe kein Readback ist: `ctl.agent_spoke()`.
- Ausgabelängen-Limit an der Satzgrenze in einem `tts_node`-Override. Readback und Abschied sind ausgenommen. Ob `say` durch `tts_node` läuft, ist **zu prüfen**.
- Begrüßung:
  - OPEN: „Hallo, hier ist Codex. Ich höre.“
  - DECISION: höchstens zwei Sätze beziehungsweise ca. 200 Zeichen der Frage. Der Rest bleibt LLM-Kontext.
  - Zunächst keine MCP-Schemaänderung, weil eine Schemaänderung Client-Reconnects erzwingt.
- Abschiede werden beim Start vorab synthetisiert: „Festgehalten. Tschüss.“, „Okay, ich lege auf.“, „Nichts festgehalten. Tschüss.“
- `main()`:
  - Protokollversion aus der Options-Zeile vor `ready` prüfen, bei Abweichung `{"type":"error","code":"protocol"}`
  - SIGTERM-Handler: `loop.add_signal_handler(SIGTERM, main_task.cancel)`
  - Logging in einen strukturierten, inhaltsfreien stderr-Logger statt `logging.disable`
- Prompts neu ordnen: Anliegen und Korrekturen → Beenden und Warten → (nur DECISION) Prozedur.
  - Raus: „Du kennst nur die folgende Frage“ und „Ich setze um, ich mache weiter“.
  - Rein: „Wenn du etwas nicht weißt, sag es“ und „Höchstens zwei Sätze“.

**`src/codex_phone/cloud_audio.py`**
- `stderr` in einen begrenzten Reader, der in eine private rotierende Logdatei schreibt (z. B. 128 KiB plus 2 Backups). Felder per Allowlist, Rate-Limit.
- stdin bleibt nach `connected` offen.
- `converse` wird zur Protokollschleife (Abschnitt 6) und gibt ein `Outcome` zurück statt `(answer, metrics)`.
- `PreparedVoice.close()`: erst stdin-EOF, 3 s warten, dann SIGTERM, 2 s, dann SIGKILL.

**`src/codex_phone/sip.py`**
- `read_events` setzt bei `CALL_CLOSED` zusätzlich ein eigenes `self.call_closed` Event, getrennt von `disconnected`.
- Neu: `async def hangup_and_wait(timeout) -> bool`. Sendet `hangup`, wartet begrenzt auf `call_closed`, gibt `True` nur bei beobachtetem `CALL_CLOSED` zurück.
- `close()` ruft das zuerst auf und erst danach `terminate`.

**`src/codex_phone/bridge.py`**
- Outcome-Abbildung:

| Outcome | Modus | Folge |
|---|---|---|
| CONFIRMED | DECISION | wie heute `deliver` / `ANSWERED` |
| ENDED_BY_REQUEST, PEER_CLOSED | DECISION, Codex-Thread | Nicht-Entscheidungs-Antwort an Codex, Frage `ENDED_NO_DECISION` statt `FAILED` |
| ENDED_BY_REQUEST, PEER_CLOSED, TIMED_OUT, LIMIT | OPEN | `COMPLETED` mit Grund |
| alles | alle | niemals automatischer Neuanruf |

- Aufruf-Status mit `close_reason`, `local_dialog_closed` und `outcome`.
- `finally`-Reihenfolge: `sip.hangup_and_wait` vor `prepared.close`.
- Ob die `calls`-Tabelle eine `outcome`-Spalte per Migration bekommt oder `error` dafür missbraucht wird: Migration, ohne Ledger oder Antworten zu verändern. `storage.py` habe ich nicht gesehen, **zu prüfen**.

**`src/codex_phone/mcp_server.py`** (nicht gesehen)
- Statustexte für die neuen Outcomes.
- Ausdrücklicher Satz: „Nicht automatisch erneut anrufen.“
- `phone_call` bleibt argumentlos.

**`voice_models.py`** (nicht gesehen)
- Profil = Modell, Stimme und Sprache, atomar validiert.
- Kein stiller Fallback.
- Rollback über den bestehenden Selektor.

**Tests (neu):**
- `tests/test_call_control.py`
- `tests/test_voice_session.py`
- `tests/test_worker_protocol.py`
- `tests/test_bridge_outcome.py` (Fake-SIP, Fake-Worker)
- `tests/test_sip_hangup_local.py` (zwei lokale baresip-Instanzen über Loopback, `Sip(cfg=None, local_port, peer)`, ohne Cloud; Skip, wenn baresip fehlt)

---

## 6. Lebenszyklus Worker, Parent, SIP

Ablauf beim Schließen:

1. Ein Controller-Step `CLOSE` oder ein Commit setzt `CLOSING`.
   - Der Adapter führt `interrupt(force=True)` aus.
   - Weitere LLM-Antworten werden mit `StopResponse` unterdrückt.
2. Worker → `{"v":2,"type":"outcome","call_id","kind","decision"?,"version"?}`. Genau einmal, danach gesperrt.
3. Parent validiert Call-ID, Modus, Version und Länge.
   - Bei CONFIRMED: **erst persistieren** (`deliver` beziehungsweise `ANSWERED`), dann `{"type":"outcome_ack"}` senden.
   - Nach dem Persistieren gibt es kein Zurück mehr.
4. Worker spielt den vorab synthetisierten Abschied, maximal ca. 1,5 s.
   - „Festgehalten“ nur nach `outcome_ack`.
   - Kommt nach einer kurzen Frist kein Ack, folgt der neutrale Abschied „Ich lege auf.“. So gibt es keine falsche Zusage.
5. Worker → `ready_to_close` und beendet die SDK-Sitzung geordnet (`aclose`).
6. Parent → `sip.hangup_and_wait(1–1,5 s)` und meldet `local_dialog_closed`.
7. Worker-Exit abwarten, dann EOF → SIGTERM → SIGKILL, jeweils begrenzt.
8. Rückgabe an exakt den ursprünglichen Bridge- beziehungsweise MCP-Aufruf.

**Peer-BYE-Wettlauf:** `disconnected` wird früher gesetzt als die Outcome-Zeile gelesen ist. Der Parent liest dann noch begrenzt (ca. 1,5 s) weiter. Ein gültiges CONFIRMED wird gespeichert, mit `close_reason=PEER_CLOSED`. Ohne Outcome lautet das Ergebnis PEER_CLOSED, niemals eine Interpretation als Zustimmung.

**Fehlerfälle:**
- Kaputte oder zu lange Zeile, falsche Call-ID, falsche Version → FAILED mit Code, Hangup, kein Neuanruf.
- Fehlendes `CALL_CLOSED` → `local_dialog_closed=false`, gemeldet als ungeprüfter Abschluss.

**Daemon:** Er hält alten Parent-Code im Speicher. Der Versionscheck vor `ready` verhindert, dass ein Mismatch erst nach dem Klingeln auffällt. Neu laden nur bei IDLE.

---

## 7. Reihenfolge

| # | Paket | Abschluss-Check |
|---|---|---|
| 0 | Rote Reproduktionen am heutigen Code: Korrektur-dann-Ja (2.1), `Okay, ich`, paralleler Readback (2.2), OPEN-Turn-Limit (2.5), Peer-BYE-Wettlauf, abgeschnittener Abschied | Tests rot, Ursache belegt |
| 1 | `call_control.py` und Tabellentests | Unit-Tests grün, Paket 0 auf Controller-Ebene grün |
| 2 | `voice_session.py`, Adapter in `cloud_voice.py`, `CallAgent`, Entfernen von `confirm_decision` und Forcing | Offline-SDK-Tests mit Fake-Modellen grün, bestehende `test_pcm_pause` und `test_turn_playout` grün |
| 3 | Protokoll, `cloud_audio`, `sip.hangup_and_wait`, Bridge-Outcomes, MCP-Texte, stderr-Log | Protokoll-, Bridge- und lokale SIP-Tests grün, volle Suite grün mit Voice-venv |
| 4 | Diagnose pro Turn (siehe unten) | Felder vorhanden, keine Inhalte gespeichert |
| 5 | Unabhängiges Review des Diffs in frischem Kontext | Befunde geschlossen |
| 6 | `scripts/test-cloud-sip.py --mcp` mit Freigabe für das freie Kontingent | Latenzen pro Turn, n angegeben |
| 7 | STT-A/B (Groq-Baseline gegen Streaming-Kandidat), dann Stimmauswahl | Messung beziehungsweise Hörabnahme durch den Eigentümer |
| 8 | Menschliche iPhone-Abnahme auf ausdrückliche Anrufanweisung | Protokollierte Szenarien |

**Diagnose pro Turn (Paket 4):**
- monotone Zeiten für Sprechbeginn, Sprechende, Turn-Ende, LLM-Start, erstes RTP
- Pause→Resume getrennt von Pause→Clear
- `output_cleared_pending` getrennt von `output_cleared_empty`
- Outcome-Grund

---

## 8. Abnahmetests je Nutzeranforderung

**A1 – Wirklich selbst auflegen**
- `test_call_control`: END in jeder Phase (Begrüßung, Antwort, READING_BACK, AWAITING, HOLD) liefert `CLOSE(ENDED_BY_REQUEST)`. Ein reines „Leg auf“ bestätigt nie. Negativtabelle: Negation, Frage, Zitat, Konditional ergeben kein CLOSE.
- `test_voice_session`: Fake-STT liefert „Leg auf.“ während laufender Ausgabe. Erwartet: keine LLM-Anfrage, `interrupt` aufgerufen, Outcome-Zeile gesendet.
- `test_bridge_outcome`: ENDED_BY_REQUEST ergibt nicht FAILED. Hangup vor dem Worker-Kill, genau ein `dial`.
- `test_sip_hangup_local`: Die Gegenstelle beobachtet `CALL_CLOSED` innerhalb eines dokumentierten Budgets nach `ready_to_close`.
- Mensch: dreimal „Leg auf“ in verschiedenen Phasen, jedes Mal ohne rote Taste.

**A2 – Jederzeit unterbrechbar, auch Begrüßung und Readback**
- Fabrik-Test: die Optionen aus Abschnitt 5 aktiv.
- Frame-Zählung wie im Audit: Während Begrüßung und Readback erreichen echte Frames die Spracherkennung, und es werden keine Frames als Stille ersetzt.
- Gesteuerte VAD-Sprache während der Begrüßung ergibt `output_paused` innerhalb des Budgets.
- Echo-Szenarien offline: eigene Ausgabe verzögert und gedämpft zurück in den Eingang (Echo-only) ergibt kein Clear; Double-talk ergibt Clear. Das prüft nur das SDK-Verhalten, nicht die AEC von Linphone.
- Mensch: Unterbrechung der Begrüßung und des Readbacks.

**A3 – Denkpausen und „warte“**
- „Moment“ ergibt HOLD. Über 10 s Fake-Stille entsteht keine LLM-Anfrage.
- „Also ich würde, ähm“ ergibt SUPPRESS. Der Folgesatz ist samt Fragment im Chat-Kontext.
- Synthetischer Providertest mit eingebauten 1,5–2-s-Pausen. Gemessen wird die Unterbrechungsrate, ohne vorher eine Erfolgsquote zu behaupten.

**A4 – Natürliches Hochdeutsch**
- Automatisch nur: Profilvalidierung (`language='de'`) und eine Stimme aus einer Allowlist mit Herkunft und Datum.
- Abnahme: Hörtest des Eigentümers mit bis zu drei Kandidaten, original und nach G.711-Roundtrip.
- Ohne diesen Hörtest bleibt A4 UNVERIFIED.

**A5 – Kurze Antworten, Korrekturen, Themenwechsel**
- Ein nacktes „Ja“ als erster Turn nach vollständigem Readback bestätigt (nach dem Commit-Fenster).
- **2.1-Test:** „Nein, eher Y“ → Agentenfrage → „Ja“ bestätigt X **nicht**.
- Längenlimit: Eine LLM-Antwort mit fünf Sätzen wird nach zwei Sätzen an der Satzgrenze gekappt; der Readback nicht.
- OPEN-Themenwechsel: kein Decision-Werkzeug, keine Bestätigungsfrage.

**A6 – Sichere Zustimmung nur nach vollständigem aktuellem Vorschlag**
- `Okay, ich`, `Ja ich`, `Stimmt das`, `Ja ja` und „Ja, aber …“ bestätigen nicht.
- Unterbrochener oder transportfehlerhafter Readback (`failed_playbacks`), danach „Ja“: kein Commit, sondern Readback v+1.
- Später Callback von v nach `propose(v+1)` ist wirkungslos.
- Sprechbeginn vor dem Readback-Ende bestätigt nicht.
- „Ja“ mit Nachsatz im Commit-Fenster bestätigt nicht.
- „Ja, passt, leg auf“ mit und ohne AWAITING.

**A7 – Kein Replay, keine verlorenen Entscheidungen**
- Doppelte Outcome-Zeile wird ignoriert.
- Peer-BYE zusammen mit CONFIRMED: Die Entscheidung wird gespeichert.
- Crash nach dem Ack: Antwort persistent.
- Kein Neuanruf nach Fehler oder ENDED.
- Ergebnis an derselben Verbindung, zwei Clients werden nicht vermischt.

**A8 – OPEN und DECISION getrennt**
- Ein OPEN-Outcome hat niemals ein `decision`-Feld.
- Das OPEN-Turn-Limit führt nicht zu FAILED.
- Die DECISION-Werkzeuge fehlen in OPEN.

---

## 9. Risiken und alternative Wege

**Risiken**
- **Echo.** Die Selbstunterbrechung über die iPhone- beziehungsweise Linphone-AEC ist unbekannt und nur im echten Anruf prüfbar.
- **SDK-Verhalten von 1.8.8:** `StopResponse` und Chat-Kontext, `say` durch `tts_node`, parallele Tools. Jeweils mit einem Test belegen, bevor darauf gebaut wird.
- **Batch-STT** könnte nach Paket 3 der Engpass bleiben.
- **G.711** begrenzt die Klangqualität jeder Stimme.
- **Protokoll und alter Daemon:** Ein Mismatch ist durch den Versionscheck abgefangen, aber nur, wenn der Daemon wirklich neu geladen wurde.

**Alternative Wege**
1. **Erst Providerwechsel:** abgelehnt, weil Ursachen dann nicht mehr zuzuordnen sind.
2. **Speech-to-Speech-Realtime-Modell:** Das Modell übernimmt das Turn-Taking, der Controller sieht nur noch asynchrone Transkripte. Zustimmungsschutz und Datenschutz würden schwerer, Kosten sind unbekannt. Nur, wenn die Gates nach Paket 7 scheitern.
3. **Lokaler semantischer Turn-Detector:** neue Abhängigkeit und Modelldownload, mit Batch-STT unbewiesen. Ein Kandidat nach Messung.
4. **Codec G.722/Opus:** eigenes Paket mit eigener Regression am gepatchten Transport.

Providerkandidaten bleiben Kandidaten, bis sie gemessen sind:
- AssemblyAI-Streaming und Cartesia über LiveKit (aus dem Codex-Plan, für mich unbestätigt)
- eine deutsche Standardstimme bei Fish

Ich nenne keine Voice-IDs. Restguthaben ist UNKNOWN. Es gibt keine Annahme eines unbegrenzten Gratisangebots.

---

## 10. Endurteil

**Sinnvollster Weg:** Pakete 0 bis 5 auf dem bestehenden Stack: Groq-Erkennung, MAFFEO-Dialog, aktuelle TTS, SIP/G.711. Kern ist ein flacher, aber tiefer `CallController` mit nur Zustimmungs-, Halte- und Schließsemantik. Dazu gehören:

- eine gemeinsame Session-Fabrik
- ein versioniertes Protokoll mit Persistieren vor dem Ack
- ein Hangup durch Parent und SIP mit beobachtetem `CALL_CLOSED`

Die Fixes für 2.1 und 2.2 sind **Pflicht vor jeder weiteren Gesprächsfreiheit**, weil sie die Zustimmungsinvariante betreffen. Erst danach folgen Provider-A/B und Stimmauswahl.

**Gates, die vor einem ehrlichen „fertig“ offen bleiben:**
1. Volle Offline-Suite einschließlich der neuen Reproduktionen grün mit dem Voice-venv, und Diff-Review in frischem Kontext.
2. Lokaler SIP-Hangup-Test grün (`local_dialog_closed`).
3. Freigabe des Eigentümers für die Semantik von „Ja, passt, leg auf“ und für die Nicht-Entscheidungs-Antwort an Codex.
4. Echo-Gate im echten Anruf. Erst dann ist `aec_warmup_duration=None` zulässig und A2 erfüllbar.
5. Synthetischer Cloud-Test mit Freigabe für das Kontingent: Latenz pro Turn mit Stichprobengröße, keine Summenrechnung.
6. Stimm-Hörabnahme durch den Eigentümer (A4).
7. Menschliche iPhone-Abnahme auf ausdrückliche Anrufanweisung:
   - Auflegen in drei Phasen
   - Unterbrechen von Begrüßung und Readback
   - Denkpause mit „Moment“
   - Korrektur nach Readback
   - Zustimmung

   Erst dieser Test belegt `device_hangup_observed` und die wahrgenommene Latenz.

Bis alle sieben Gates geschlossen sind, ist der Status: **technisch begründet planbar, nicht implementiert, nicht verifiziert.**


## Nachprüfung durch Codex (24.10.2026, keine Implementierung)

Die unabhängige Autorenfassung oben bleibt unverändert. Nach Erstellung wurden
die veraltete Zustimmung (2.1), fehlende Readback-Versionierung als kontrollierte
Ereignisfolge (2.2) und die drei Fragmentannahmen im bestehenden Decision-Modul
ausgeführt und bestätigt. Der reale parallele SDK-Tool-Race wurde dabei nicht
ausgeführt. Volle Offline-Suite: 59 Tests grün in 5,963 s.

CALL_CLOSED ist ein lokaler Nachweis. Die vorgeschlagene automatische Wiederholung
eines Readbacks muss zusätzlich ausschliessen, dass der Vorschlag durch Korrektur
veraltet ist. Provider- und SDK-Fragen bleiben mit den jeweils genannten Grenzen
offen. Dieser Bericht löst weder Implementierung noch neue Anrufe aus.
