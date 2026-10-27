# Unabhängige Claude-Code-Analyse mit Quellenabgleich

Auftrag vom 23.10.2026; geprüftes Repository: `0213e16`.
Ausführung: lokal installierte Claude Code CLI 2.1.308, gemeldetes Modell
`claude-opus-5-5[1m]`. Der folgende Claude-Bericht ist unverändert wiedergegeben.
Keine Implementierung, kein Anruf, kein Providervergleich oder Deployment wurde
für diese Analyse ausgeführt. Claude berichtet 53 ausgeführte Offline-Tests.

## Quellenabgleich durch Codex nach Eingang des Berichts

Die zentralen Befunde sind im aktuellen Code nachvollzogen: Sprachmodell-Tools
enthalten keinen eigenen Auflegepfad; Begrüssung und Readback sind ausdrücklich
nicht unterbrechbar; das SDK ersetzt dabei Audio für STT durch Stille; der
Klassifizierer akzeptiert die unvollständigen Texte `Okay, ich` und `Ja ich`.
Diese Klassifizierer-Proben wurden zusätzlich direkt ausgeführt. Das SDK unterstützt
auch den vorgeschlagenen `ToolResult(reply_required=False)`.

Drei Aussagen im Bericht dürfen jedoch nicht als nachgewiesene Messwerte oder
allgemeine Garantien übernommen werden:

1. **Die Addition 0,55 s VAD + 0,7 s Endpointing = 1,25 s ist nicht belastbar.**
   Das installierte `audio_recognition.py:1462` datiert das Sprachende um die
   VAD-Stille zurück; `:1741-1743` zieht bereits verstrichene Zeit vom Endpointing
   ab. Daher lassen sich die beiden Schwellen nicht einfach addieren. Auch die
   daraus abgeleitete Gesamtantwortzeit von 3,2–3,5 s ist keine verifizierte
   Ende-zu-Ende-Messung. Tatsächliche Zeiten müssen pro Turn gemessen werden.
2. **18 `output_cleared`-Aufrufe beweisen keine 18 abgeschnittenen Antworten.**
   `SipOutput.clear_buffer()` zählt auch ohne ausstehendes Audio. Die Aussage
   „ungefähr jede Agentenantwort wurde abgebrochen“ lässt sich daraus nicht
   ableiten. Ob Echo, echte Unterbrechungen oder leere Clears vorlagen, bleibt
   unbekannt. Die im Bericht genannten Zahlen sind Aufrufzähler.
3. **„Zuverlässige Zustimmung“ ist keine allgemeine Produktgarantie.** Der
   Bericht belegt selbst eine Lücke bei unvollständigen Zustimmungsfragmenten.
   Ebenso erklärt schmalbandiges G.711 nicht für sich einen englischen Akzent;
   Referenzsprache und wahrgenommene Aussprache bleiben akustisch ungeprüft.

Die rekonstruierte Höchstdauer fürs Auflegen und die vorgeschlagenen Schwellen
sind Abnahmevorschläge, keine schon erreichten Eigenschaften. Die offene Frage
„Ja, passt, leg auf“ als Zustimmung plus Ende oder nur Ende ist eine noch nicht
entschiedene Produktsemantik. Für die reine Analyse wurde kein Rückruf ausgelöst.

## Originalbericht von Claude Code

# Review codex-phone-bridge: Gesprächsführung, Unterbrechung und Auflegen (Stand `0213e16`, 23.10.2026)

Das ist eine Einzelprüfung durch mich. Ein Subagent-Werkzeug steht in dieser Umgebung nicht zur Verfügung. Ich habe nichts geändert, nicht angerufen und keinen Provider aufgerufen. `git status` ist sauber.

---

## (a) Gesamturteil und die tatsächlichen Anforderungen

**Urteil:** Das System kann eine Entscheidung zuverlässig erst nach ausdrücklicher Zustimmung übernehmen. Ein Gesprächspartner ist es nicht. Dafür gibt es drei Gründe im Aufbau:

1. **Es gibt nur einen regulären Ausgang: eine bestätigte Entscheidung.** Einen Weg zum Auflegen kennt das System nicht. Alles andere läuft als Fehler.
2. **Die Ablaufteile sind gegen den Nutzer abgeschirmt.** Begrüssung samt ganzer Codex-Frage, Readback und Abschied sind nicht unterbrechbar. Was der Eigentümer währenddessen sagt, kommt bei der Spracherkennung als **Stille** an.
3. **Wann der Nutzer fertig ist, wird nur über eine feste Stille-Schwelle entschieden (ca. 1,25 s).** Die Spracherkennung ist eine Batch-Erkennung. Eine Antwort braucht nach meiner Schätzung trotzdem ca. 3 s.

Die letzten Fixes haben Codex' eigene Deutung der Beschwerden synthetisch auf PASS gebracht. Die tatsächlichen Beschwerden des Eigentümers lösen sie nicht. **Für die Erwartungen des Eigentümers ist das Produkt nicht reif.**

**Die korrekten Anforderungen, wie ich sie rekonstruiere:**
- **R1:** Der Eigentümer kann jederzeit per Stimme beenden. Das System legt innerhalb von 1–2 s auf, mit höchstens einem kurzen Abschiedssatz. Das Ergebnis heisst „vom Eigentümer beendet, keine Entscheidung“, ist kein Fehler und löst keinen Wiederholungsanruf aus.
- **R2:** Er kann jederzeit unterbrechen, auch bei Begrüssung und Readback. Die Stimme verstummt schnell und reagiert auf das Gesagte.
- **R3:** Denkpausen werden toleriert. Nach einem echten Ende kommt die Antwort trotzdem zügig.
- **R4:** Die Aussprache ist natürlich deutsch. Das ist eine Frage der Stimmwahl und des Audiowegs, kein Prompt-Thema.
- **R5:** Die Stimme folgt seinem Anliegen. Die Bestätigungsprozedur kommt einmal und kurz, am Ende.
- **R6:** Die Zustimmungsregeln bleiben: vollständiger Readback, danach ein neues Ja. Das widerspricht R1–R5 nicht, sobald Auflegen und Zustimmung getrennte Ausgänge sind.
- **R7:** Der Status ist ehrlich: Manuelles Auflegen ist kein technischer Abbruch.

---

## (b) Ursachen pro Beschwerde

Beweisstufen: L2 = Zeile benannt, L3 = Ablauf Schritt für Schritt durchgegangen, L4 = mit echtem Code ausgeführt.

### 1. „Leg auf / beende das Gespräch“ wird nicht umgesetzt — BELEGT (L2–L4)

- **Kein Weg zum Auflegen:**
  - Die Tools sind nur `propose_decision` und `confirm_decision` (`cloud_voice.py:263-281`).
  - Der Worker endet nur über `result`, also bestätigte Antwort, Fehler, 20 Turns oder 300 s (`cloud_voice.py:279-320, 382`).
  - Das SDK hätte ein Muster dafür (`livekit/agents/beta/tools/end_call.py`). Das ist allerdings an Room/Job gebunden und hier nicht direkt nutzbar.
- **Der Prompt erzeugt falsche Handlungszusagen:**
  - `'Sprich direkt als Codex: Ich setze um, ich mache weiter.'` (`cloud_voice.py:330`).
  - Dazu kommt `'…oder abschliessen möchte … propose_decision'` (`:334-336`). Das vermischt Auflegen mit der Entscheidung.
  - „Ich lege auf“ zu sagen, ohne es zu können, ist bei dieser Persona zu erwarten. Mangels Transkript ist das PLAUSIBEL.
- **Klassifizierer, ausgeführt (L4):** `Beende das Gespräch.`, `Leg auf.`, `Ja, leg auf.`, `Ja, beende das Gespräch.`, `Schliess das Gespräch.`, `Tschüss.` und `Ja, passt, leg auf.` liefern alle `False`. Es gibt also weder Erzwingen noch Bestätigung noch Auflegen.
- **Manuelles Auflegen gilt als Fehler:**
  - `cloud_audio.py:138-141` meldet `'Call disconnected or cloud conversation timed out'`.
  - `bridge.py:107-112` setzt daraus `FAILED`.
  - Das MCP gibt an Codex „FAILED“ weiter (`mcp_server.py:70-73`).
  - Belegt im letzten echten Anruf: 10:27:26 verbunden, 10:30:04 `call_failed RuntimeError` (`events.jsonl`).
- **Der Worker wird ohne Aufräumen beendet:**
  - `prepared.close()` schickt SIGTERM (`cloud_audio.py:75-82`).
  - In `cloud-status.json` fehlt `output_samples` aus dem `finally`, und `last-voice-usage.json` zeigt `session_closed: False`. Der `finally`-Block in `cloud_voice.py:398-404` lief also nicht. BELEGT.
- **Auch im Erfolgsfall ist der Abschied praktisch tot:**
  - Die Bestätigung wird *vor* dem Abschied gemeldet (`cloud_voice.py:392-396`).
  - Der Elternprozess kehrt auf die erste stdout-Zeile zurück und beendet den Worker sofort (`cloud_audio.py:136-155`).
  - Fish braucht laut Doku ca. 1,3 s bis zum ersten Audio. Der Abschied wird also abgeschnitten (L3).

### 2. Die Stimme lässt sich praktisch nicht unterbrechen — BELEGT für die Hauptsegmente (L4), PLAUSIBEL für den Rest

- **Die Begrüssung ist die ganze Codex-Frage und nicht unterbrechbar:**
  - `greeting = 'Codex hier. ' + options['question']` mit `allow_interruptions=False` (`cloud_voice.py:352, 379-381`).
  - Die Frage darf bis zu 2000 Zeichen lang sein (`mcp_server.py:21`). Die MCP-Anweisung verlangt sogar „enough context and options“ (`:12`). Bei rund 15 Zeichen/s sind 30 s bis über 2 min Monolog möglich.
  - Laut `VOICE-RECOVERY-2026-10-23.md` war das eine bewusste Entscheidung.
- **Der Readback ist ebenfalls nicht unterbrechbar:** `cloud_voice.py:186-187`, Vorschlag bis 2000 Zeichen (`voice_decision.py:18`).
- **Das SDK verwirft Nutzer-Audio** (`agent_activity.py:1671-1700`, `discard_audio_if_uninterruptible=True` als Default). Meine Laufzeit-Reproduktion mit den Produktionsoptionen (L4) zählt die Frames, die bei der Spracherkennung ankommen:
  ```
  nicht unterbrechbares say (Begrüssung/Readback):  echt=0   als Stille ersetzt=47
  unterbrechbar, erste 3 s (AEC-Warmup-Default 3.0): echt=0   als Stille ersetzt=47
  unterbrechbar, nach dem Warmup:                    echt=48  als Stille ersetzt=0
  ```
  Was der Eigentümer in diesen Phasen sagt, wird nie erkannt. Ein Satz über das Segmentende hinaus wird zum Fragment verstümmelt (PLAUSIBEL).
- **Der AEC-Warmup ist praktisch nebensächlich.** Er greift nur auf die erste Sprechphase, und die ist ohnehin die gesperrte Begrüssung (`agent_session.py:117, 2194-2207`). Ohne Room wird er nie abgeschaltet. Ich überbewerte ihn nicht.
- **Nutzer-Turns während gesperrter Rede werden komplett verworfen**, auch für den Controller: `agent_activity.py:2807-2813` kehrt zurück, bevor `conversation_item_added` aufgerufen wird. Das trifft nur, wenn ein Transkript aus vorherigem Audio genau dann eintrifft. Selten, aber real.
- **In unterbrechbaren LLM-Antworten funktioniert das Unterbrechen technisch, aber träge:**
  - Pausiert wird erst nach 0,7 s durchgehender Sprache (`min_interruption_duration`).
  - Endgültig abgebrochen wird erst, wenn das Groq-Transkript da ist: 0,55 s VAD-Stille plus Netzwerk.
  - Ein kurzes „Stopp“ wirkt also erst nach ca. 1–1,5 s (L3, SDK `agent_activity.py:2472-2487, 2556-2585`).
  - Adaptive Unterbrechung ist aus. Das habe ich geprüft: `is_hosted()` und `is_dev_mode()` sind beide False (`agent_activity.py:5232-5239`).
- **Echo:** UNKNOWN. Die Zähler lassen sich nicht von echtem Dazwischenreden unterscheiden (siehe nächster Punkt).
- **Zähler des letzten echten Anrufs** (`cloud-status.json`, 10:27–10:30, Code-Stand `906fc31`, also *vor* dem letzten Fix):

  | Zähler | Wert |
  |---|---|
  | `final_transcript` | 19 |
  | `message` | 36 |
  | `output_cleared` | 18 |
  | `output_paused` | 166 (Aufrufe, nicht einzelne Pausen) |
  | `output_resumed` | 39 |
  | `false_interruption` | 0 |
  | `proposal` | 0 |
  | `error` | 0 |

  Ungefähr **jede Agentenantwort wurde abgebrochen oder verworfen.** Drei Hypothesen bleiben ununterscheidbar:
  - H1: Die Stimme fällt in Denkpausen ins Wort, der Nutzer redet weiter (passt zu Beschwerde 3).
  - H2: Das Echo der eigenen Stimme wird als Nutzersprache erkannt.
  - H3: Der Eigentümer hat aktiv unterbrochen.

  Die Diagnose speichert nur den *letzten* Latenzwert, keine Verteilung pro Turn.
- **Audiokette:** Gesendet wird in Echtzeit-Takt (`cloud_voice.py:105-123`), baresip liest ein Paket pro 20 ms (`native/phoneaudio.c:19-24`). Nach einer Pause oder einem Clear laufen nur noch der Puffer `audio_buffer 20-160` (`sip.py:70`) und der Jitter-Puffer im iPhone nach. Das ist kein Hauptgrund (L3).

### 3. Unnatürliche Gesprächswechsel, Weiterreden in Denkpausen — BELEGT (L4 Konfiguration, L3 Ablauf)

- **Das Ende des Turns wird rein über Stille erkannt:**
  - Konfiguration: `turn_detection='vad'`, Endpointing `mode: fixed, min_delay 0.7`, Silero `min_silence_duration 0.55` (beides L4 ausgegeben).
  - Eine Pause von ca. 1,25 s beendet den Turn. `max_endpointing_delay=2` hat ohne Turn-Detector-Modell praktisch keine Wirkung.
  - Ein semantischer Turn-Detector ist nicht installiert (`ModuleNotFoundError: livekit.plugins.turn_detector`).
- **Die Prompt-Zeilen wirken nicht auf das Timing.** „Lass den Anrufer ausreden“ und „Beende jede kurze Antwort und warte“ (`cloud_voice.py:327-329`) erreichen das LLM erst, nachdem das SDK den Turn schon beendet hat.
- **Nach dem Readback redet die Stimme weiter:**
  - `propose_decision` gibt ein dict zurück, damit gilt `reply_required=True` (`llm/utils.py:972-1003`).
  - Nach „Soll ich das genau so umsetzen?“ erzeugt das SDK eine weitere LLM-Antwort. Der eigene Test belegt die zweite Anfrage (`test_decision_agent.py:83`). Ob dabei gesprochen wird, hängt vom Modell ab (PLAUSIBEL).
- **Das Tempo ist trotzdem langsam.** Schätzung aus den dokumentierten Einzelmessungen (PLAUSIBEL):

  | Schritt | Dauer |
  |---|---|
  | VAD-Stille | 0,55 s |
  | Endpointing | 0,7 s |
  | LLM bis zum ersten Token | ca. 0,5 s |
  | Fish bis zum ersten Audio | ca. 1,3 s |
  | Audioweg | ca. 0,2–0,4 s |
  | **Summe** | **ca. 3,2–3,5 s** |

  Das System fällt also zu früh ins Wort *und* antwortet langsam. `preemptive_generation=False` aus dem letzten Fix macht das um bis zu ca. 0,3–0,5 s schlimmer (PLAUSIBEL).

### 4. Englisch klingendes, billiges Deutsch — teils BELEGT, Ursache der Aussprache UNVERIFIED

- **Die Stimme wurde nie für Deutsch ausgewählt.** Die `voice_id` war seit `4377bd3` ein fest eingetragener Default im Testskript. `CLOUD-VOICE.md:65` sagt selbst: „official example voice, not verified to be the owner's preferred“.
- **In welcher Sprache die Referenzaufnahme dieser Stimme ist, steht nirgends im Repo.** Bei klonenden TTS überträgt sich der Akzent der Referenz. Das ist PLAUSIBEL, aber UNVERIFIED. Eine bessere Stimme kann ich nicht belegt benennen.
- **Der Audioweg ist schmalbandig.** Nur `g711.so` wird geladen (`sip.py:76`). Homebrew-baresip 4.12 hat auch nur `g711.so`, kein Opus oder G.722 (geprüft). 16-kHz-TTS wird auf 8 kHz Telefonband heruntergerechnet. Das ist eine harte Qualitätsgrenze für TTS und Whisper (BELEGT).
- **Weitere Fish-Optionen ungenutzt:** `latency`, `normalize`, `temperature` (`inference/tts.py:188-201`) werden nicht genutzt. Ihre Wirkung ist UNVERIFIED.
- Der Prompt „Hochdeutsch“ (`cloud_voice.py:325`) steuert nur die Wortwahl, nicht die Aussprache.

### 5. Die Stimme hängt an ihrer Prozedur statt am Anliegen — BELEGT (L3–L4)

- **Prompt-Gewicht:** Etwa die Hälfte der Anweisung betrifft Vorschlag und Bestätigung (`cloud_voice.py:333-338`).
  - `'Du kennst nur die folgende Frage'` (`:332`) verbietet faktisch, einem Themenwechsel zu folgen.
  - Die Frage steht ganz am Ende des Prompts und dominiert dadurch.
  - Zu Themenwechsel, Korrekturen als Priorität oder Beenden steht nichts drin.
- **Das Erzwingen reagiert auf jedes nackte Ja** (`decision_agent.py:16-23`). Ein „Ja“ auf eine Verständnisfrage, ein „Genau“ oder ein „Okay“ als Rückmeldung erzwingt `propose_decision`. Darauf folgen ein nicht unterbrechbarer Readback und die Bitte um ein weiteres Ja.
- **Der Klassifizierer ist zu grosszügig (L4):** `Okay.`, `Ok`, `Ja ja`, `Stimmt das` (ohne „?“, wie Whisper es manchmal liefert), **`Okay, ich`** und **`Ja ich`** ergeben alle `True`.
  - Bricht das Endpointing in einer Denkpause nach „Okay, ich …“ ab, und ein Vorschlag wurde vorgelesen, liefert der Controller die Entscheidung aus (`cloud_voice.py:311-318`).
  - Das ist **ein Risiko für die Zustimmungsregel**, nicht nur für die Bedienung. Es besteht seit `4377bd3` und wird durch das neue Erzwingen verstärkt.
- **Sackgasse nach unterbrochenem oder fehlgeschlagenem Readback:**
  - `propose()` speichert den Vorschlag, dann wirft `read_back_proposal`, und `read_back_at` bleibt `None` (`cloud_voice.py:183-191`).
  - Das LLM bekommt nur „An internal error occurred“.
  - `confirm_decision` antwortet: „Bitte um ein ausdrückliches Ja“ (`:278`). Jedes Ja scheitert aber (`voice_decision.py:58-60`), bis das LLM von sich aus neu vorschlägt. Das ist eine Schleife, die das System selbst erzeugt (L3).
- **Zwei Wege zur Bestätigung:** Der Controller bestätigt bereits in `item_added`. Das Tool `confirm_decision` bringt dem Modell nur zusätzliche Ablehnungen, auf die es mit Nachfragen reagiert.

---

## (c) Was die bisherigen Fixes bringen

| Fix | Bewertung |
|---|---|
| **`0213e16` Erzwingen bei Ja** | **Löst Beschwerde 1 nicht.** Reine Auflegesätze werden nicht erkannt (L4). Die Doku deutet die Beschwerde in „Zustimmung ohne Vorschlag“ um. **Verschlimmert 2, 3 und 5:** nacktes Ja oder Okay mitten im Gespräch führt zu einem zu frühen, nicht unterbrechbaren Readback und einem zweiten Ja. Testsatz in `test-cloud-sip.py` passend zur neuen Phrase geändert („Ja, wir schicken ab“). Dieser PASS beweist also nichts über die Formulierungen des Eigentümers. |
| `preemptive_generation=False` | Die Begründung trägt schwach, weil die Batch-Erkennung ohnehin fertige Transkripte liefert. Kostet Antworttempo. |
| Neue Abschlussphrasen | Hilft eng für genau diese Phrasen nach einem Readback. |
| `bf0eef2` PCM pause/resume | Technisch korrekt (Tests grün), hilft bei kurzem Lärm in unterbrechbaren Antworten. Ändert nichts an den gesperrten Segmenten. Der Test nutzt andere Parameter als die Produktion (siehe d). |
| Begrüssung bewusst nicht unterbrechbar (VOICE-RECOVERY) | **Schadet.** Direkte Ursache des „Aufsatzes“. |
| `906fc31` Prompt Hochdeutsch und „warten“ | Kosmetisch. Kein Einfluss auf Aussprache oder Turn-Timing. |
| Zustimmungsregeln, kein Replay, Abbruch | Halten im Code. Erhalten. |

---

## (d) Testlücken und gezielte Reproduktionen

**Lücken:**
- `test_turn_playout.py:84-87` testet mit `aec_warmup_duration=None`, Schwellen 0,1 s, einer **unterbrechbaren** `say` und einer sofort antwortenden Spracherkennung. Die Produktion nutzt 3,0 s Warmup, 0,7/0,8 s, eine **gesperrte** Begrüssung und echte Groq-Latenz. Der Test beweist Verkabelung, nicht die Anforderung.
- Es gibt keine gemeinsame Session-Fabrik. Tests bauen die Konfiguration von Hand nach und weichen so von der Produktion ab.
- `test_decision_agent.py` prüft nicht `Okay`, Fragmente oder Auflegen. Dass nach einem Tool weitergeredet wird, steht im Test als *gewollt*.
- Kein Test für Auflegen, für die Unterscheidung „Eigentümer hat aufgelegt“ vs. Fehler oder für den MCP-Status.
- Kein Latenzbudget mit echten Zeiten.

**Von mir ausgeführt:**
- Volle Suite: **53 Tests OK.** Hinweis: Die Ausgabe „Removed this project’s MCP entries…“ stammt aus `test_mcp.py:148-164` mit gepatchtem `Path.home`. Die echten `~/.codex` und `~/.copilot` sind unverändert (geprüft).
- Klassifizierer-Probe, Auflösung der SDK-Optionen und Frame-Zählung (siehe b).

**Vorgeschlagene Reproduktionen, die heute fehlschlagen müssten:**
- **R1:** Offline `AgentSession` mit LLM-Fixture, Nutzer sagt `Leg auf.` (ohne Vorschlag, nach Readback, während einer Antwort). Erwartet: Ausgang „beendet“ in ≤1 s. Heute: nie.
- **R2:** Produktions-Session-Fabrik, gesteuerte VAD-Sprache während der Begrüssung. Erwartet: `output_paused`. Heute: keine Pause, Audio verworfen.
- **R3:** Nach `propose_decision` genau eine LLM-Anfrage. Heute: 2.
- **R4:** Vorgelesener Vorschlag, dann `heard('Okay, ich')`, dann muss `confirm()` scheitern. Heute: Vorschlag wird geliefert.
- **R5:** Readback unterbrochen, dann „Ja“. Erwartet: definierter Weg mit neuem Readback und klarer Toolmeldung. Heute: Sackgasse.
- **R6:** Fragment „Also ich würde, ähm“ plus 1,3 s Stille. Erwartet: keine LLM-Anfrage. Heute: Anfrage.
- **R7:** Nur mit Freigabe für Providerverbrauch, synthetische Gegenstelle: Zeit vom Ende der Nutzersprache bis zum ersten Antwort-RTP-Paket messen.

---

## (e) Priorisierte Umsetzung (kein Neubau)

**Architektur:** Die Logik für Zustimmung und Beenden ist heute auf fünf Stellen verteilt: `Decision`, `DecisionAgent`, `item_added`, Tools sowie `converse`/`bridge`. Einen Ausgang ausser „Antwort oder Exception“ gibt es nicht. Vorschlag:
- Ein reines Python-Modul **`CallController`** ohne SDK.
  - Schnittstelle: `on_user_message(text) → Action` (`CONTINUE | CONFIRMED(answer) | END(reason)`), `proposal_read_back(ok)`, `outcome`.
  - Ausgänge: `confirmed | ended_by_owner | owner_hung_up | timeout | failed`.
- Der Worker übersetzt Actions nur noch in SDK-Aufrufe.
- Dazu eine gemeinsame `session_options()`, die Produktion und Tests nutzen. Das ist eine echte Naht mit zwei Adaptern, also gerechtfertigt.

**P0-1 Auflegen als eigener Ausgang**
- Betroffen: `cloud_voice`, `voice_decision` (wird zum Controller), `cloud_audio`, `bridge`, `mcp_server`.
- Bausteine:
  - Deterministische Erkennung der Absicht über die *ganze Äusserung*: „leg auf“, „auflegen“, „beende/schliess das Gespräch“, „tschüss“, „das wars“. Zusätzlich ein `end_call`-Tool.
  - Bei Treffer erzwungenes Interrupt, auch über gesperrte Rede, und ein beim Start vorab synthetisierter kurzer Abschied.
  - Danach Worker-Payload `{'outcome':'ended_by_owner'}`, Status `ENDED_BY_OWNER` statt `FAILED`, MCP-Anweisung „nicht wiederholen“.
  - Trennung trennt nach Ursache: Auflegen durch den Eigentümer vs. Timeout. Der `CALL_CLOSED`-Grund aus baresip kommt als Quelle in Frage (UNVERIFIED).
  - SIGTERM-Handler im Worker, damit `finally` läuft.
- **Produktentscheidung des Eigentümers nötig:** Soll „Ja, passt, leg auf“ nach dem Readback als Bestätigung *und* Auflegen gelten oder als Auflegen ohne Entscheidung?
- Abnahme: R1 grün. Menschentest: 3× „leg auf“ in verschiedenen Phasen, jedes Mal ohne rote Taste.

**P0-2 Kurze, unterbrechbare Sprechblöcke**
- Gesprochene Begrüssung ≤ ca. 300 Zeichen (Kurzfassung; ganze Frage nur als LLM-Kontext). Optionales Schemafeld oder strengere MCP-Anweisung.
- `allow_interruptions=True` für Begrüssung und Readback.
- Vorschlagslänge begrenzen.
- Unterbrochener Readback gibt ein `ToolResult` mit „unterbrochen, hör zu“ zurück, ohne Folgeantwort. Zustimmung bleibt unmöglich, bis ein Readback vollständig durchlief. Der bestehende Schutz bleibt.
- `aec_warmup_duration=None` erst *nach* der Echo-Diagnose (P0-5).
- Risiko: Echo führt zur Selbstunterbrechung. Deshalb gehört P0-5 zuerst.
- Abnahme: R2 und R5 grün.

**P0-3 Kein Nachreden nach dem Readback**
- `propose_decision` gibt `ToolResult(reply_required=False)` zurück.
- `confirm_decision` entfernen; der Controller entscheidet über die Zustimmung.
- Abnahme: R3.

**P0-4 Klassifizierer härten, Erzwingen eingrenzen**
- `okay`/`ok` allein, `ja ja` und Endungen auf `ich|du|es|das` gelten nicht als Zustimmung.
- Erzwingen nur bei ausdrücklichen Abschlussphrasen wie „so machen wir's“ oder „schick ab“, nicht bei nacktem Ja.
- Abnahme: R4 sowie eine Negativliste als Test.

**P0-5 Private numerische Diagnose pro Turn**
- Erfassen: Überlappung (ja/nein), Pause→Clear vs. Pause→Resume, Latenzlisten statt nur letzter Wert, Anzahl erkannter Auflegeabsichten, Grund für den Ausgang.
- Echo-Indikator als reine Zahl: lokale Ähnlichkeit zwischen Transkript und letztem Agententext, ohne Text zu speichern.
- Ohne das liefert der nächste Menschentest wieder nur „19 Transkripte, Ursache unbekannt“.

**P1**
- **Geduld bei Denkpausen:** Endpointing `mode='dynamic'` ist im SDK eingebaut, keine neue Abhängigkeit. Dazu eine Zögerungsschranke in `on_user_turn_completed`: `StopResponse` bei Endungen wie „ähm/also/und/weil/ich“ oder „Moment“. Den lokalen Multilingual-Turn-Detector nur nach Freigabe (neue Abhängigkeit, UNVERIFIED mit Batch-Erkennung). `preemptive_generation` wieder an, sobald P0-4 steht. Fish `latency` testen. Abnahme: R6; menschlich 2-s-Pausen in 4 von 5 Fällen nicht unterbrochen.
- **Prompt neu priorisieren:** Anliegen und Korrekturen zuerst, dann Beenden, dann Prozedur. Keine Zusagen von Handlungen, die die Stimme nicht ausführen kann. „Du kennst nur die Frage“ ersetzen.
- **Stimme:** Blindvergleich weniger deutscher Kandidaten über lokal simuliertes G.711. Die Auswahl trifft der Eigentümer; das kostet TTS-Zeichen und braucht Freigabe. Opus über einen baresip-Neubau ist ein grösserer Eingriff (Aushandlung mit Linphone UNVERIFIED).
- **Streaming-Erkennung prüfen** (bestehendes `recognition_backend=livekit`, A/B mit der Stimme des Eigentümers). Interim-Transkripte erlauben `min_interruption_words≥1`, also weniger Fehlpausen.

---

## (f) Wirtschaftlichkeit und was unbelegbar bleibt

- **Verbrauch:** Der letzte Anruf hatte laut SDK ca. 50 s Erkennung, ca. 17 000 LLM-Tokens und 1773 TTS-Zeichen. Rechnungen und Restguthaben bei LiveKit, Groq und den MAFFEO-Routen sind **UNKNOWN**.
- **Komplexität:** Neun Glieder (gepatchtes libre/SRTP, eigene baresip-Module, Linphone, LiveKit Inference, Fish, Groq, MAFFEO, MCP, Codex) für einen Entscheidungsanruf sind fragil.
- **Trotzdem sinnvoll:** Der Ende-zu-Ende-Transport funktioniert nachweislich, und die Mängel liegen in der Gesprächsschicht von ca. 400 Zeilen. P0 ist klein und zielgenau. Ein Neubau ist jetzt nicht gerechtfertigt.
- **Entscheidungspunkt:** Scheitern Unterbrechung oder Turn-Wechsel nach P0+P1 im Menschentest weiter, ist die Kette aus Batch-Erkennung und VAD der Engpass. Dann wäre zu prüfen: Streaming-Erkennung oder ein kostenpflichtiges Speech-to-Speech-Modell (Kosten, Datenschutz). Garantien gibt es dafür keine.
- **Unbelegbar ohne neue Daten oder Freigabe:**
  - Die genauen Worte im letzten Anruf, und ob Whisper „leg auf“ überhaupt korrekt erkannt hat.
  - Ob es Echo gibt.
  - Die wahrgenommene Latenz am iPhone.
  - Woher der Akzent kommt (Sprache der Referenzaufnahme).
  - Das AEC-Verhalten von Linphone.
  - Restguthaben bei den Providern.
  - Ob die 18 Abbrüche gewollt waren.

**Nicht ausgeführt (UNVERIFIED):** `test-cloud-sip.py`, jeder Telefon- oder Provideraufruf, Menschentest. Der letzte Fix (`0213e16`) wurde **nie** mit einem echten Anruf getestet. Die Zähler oben stammen vom Anruf davor.

**Zurückgelassen:** von mir nichts; mein temporäres Verzeichnis wurde automatisch entfernt. Gefunden habe ich einen alten Rest vom 17.10.: `$TMPDIR/cpb-9wrz_sfy`, 0 Byte, enthält einen verwaisten Socket aus einem früheren harten Abbruch. Nicht von mir angelegt, nicht gelöscht. Das Löschen ist harmlos, wenn du willst.