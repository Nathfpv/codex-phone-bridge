> Historische Planung. Umsetzung und ausgeführte Nachweise vom 24.10.2026:
> [Calling-Fix](CALLING-FIX-2026-10-24.md). Die ursprüngliche Planung unten
> ist keine aktuelle Aussage, dass die inzwischen umgesetzten Punkte offen sind.

# Calling: konkrete End-to-End-Umsetzungsvorlage

Stand: 23.10.2026, Quellstand `f10bb92`.
Autor dieser Vorlage: **Codex**, auf Basis des vorherigen unabhängigen Claude-Audits,
des aktuellen Quellcodes, der installierten LiveKit Agents 1.8.8 und offizieller
Anbieterdokumentation. **Dies ist kein neuer abgeschlossener Claude-Bericht.**
Die frühere SSO-Blockade trat im falschen privaten Chrome-Profil auf. Nach
Wechsel ins Roche-Profil und Anmeldung durch den Eigentümer lieferte die lokale
Claude Code CLI am 24.10.2026 einen vollständigen unabhängigen Folgebericht:
[Claude-Review](CLAUDE-CALLING-IMPLEMENTATION-REVIEW-2026-10-24.md).
Der Bericht ist eine Snapshot-Prüfung, kein ausgeführter Implementierungsnachweis.

## Verbindliche Korrektur der Umsetzungsvorlage vom 24.10.2026

Die folgenden Korrekturen haben Vorrang vor den ursprünglichen Abschnitten:

1. **Zuerst bestehender Stack.** Controller, Zustimmung, Unterbrechbarkeit und
   Worker/Parent/SIP-Abschluss auf Groq + MAFFEO + bisheriger TTS reparieren.
   AssemblyAI und Cartesia bleiben anschliessende, einzeln gemessene Kandidaten.
2. **Controller besitzt fachliche Zustände.** SDK-Zustände THINKING/SPEAKING
   nicht als zweite Wahrheit spiegeln. Zustimmung, Readback-Version, HOLD und
   Abschluss sind die fachlichen Zustände.
3. **Korrektur entwertet Zustimmung.** Nach einer Korrektur darf ein späteres
   Ja keinen alten Vorschlag bestätigen. Neue Fassung muss erneut vollständig
   vorgelesen werden. Automatisches Wiederholen ist nur für einen noch aktuellen,
   unveränderten Vorschlag zulässig; nie nach inhaltlicher Korrektur.
4. **Sprechbeginn berücksichtigen.** Ein erst nach Readback-Ende finalisiertes
   Transkript beweist keinen erst danach begonnenen Zustimmungs-Turn. Onset und
   tatsächliches lokales Playout-Ende müssen getrennt erfasst werden. Ein kurzes
   gemessenes Commit-Fenster schützt vor unmittelbar fortgesetztem „Ja … aber“;
   es garantiert keine Erkennung beliebig später Einschränkungen.
5. **Abschlussbeweise trennen.** CALL_CLOSED beweist lokalen SIP-Abschluss.
   Sichtbares Auflegen am iPhone braucht einen echten Gerätetest. CONTROL_LOST
   ist kein CALL_CLOSED. Outcome und Abschlussstatus getrennt erhalten.
6. **OPEN-Limits sind reguläre Ausgänge.** Ein freies Gespräch darf am Turn-Limit
   nicht pauschal als technischer Fehler enden. Keine bestätigte Entscheidung
   aus OPEN und keine automatische Wiederwahl.
7. **Reviews bleiben kritisch.** Claudes API-/SDK- und Parallelitätsannahmen sind
   ausdrücklich vor Implementierung ausführbar zu prüfen. Sein Vorschlag, jede
   Wiederholung automatisch zu starten, ist kein Freibrief für alte Vorschläge.
   Die im Bericht vorgeschlagenen Eigentümer-Gates sind Review-Vorschläge;
   bestehende Nutzerautorisierung bleibt massgeblich. Neue Anrufe nur auf Wunsch.

Ausgeführt am 24.10.2026 auf f10bb92:
- Volle Offline-Suite: 59 Tests grün, 5,963 s.
- Reproduktion: Readback X → „Nein, eher Y“ → „Ja“ liefert weiterhin X.
- Reproduktion: alte und neue proposal-Aufrufe plus unversionierter read_back-
  Callback geben den neuen, ungehörten Text frei. Dies belegt die fehlende
  Versionssicherung; tatsächliche parallele SDK-Tool-Ausführung bleibt ungeprüft.
- Reproduktion: `Okay, ich`, `Ja ich`, `Stimmt das` ergeben jeweils True.

**Status:** unabhängig geprüft und konkretisiert; noch nicht implementiert.
Die bestehenden 59 Tests decken diese Reproduktionen nicht ab. Kein neuer
Cloud-, SIP- oder iPhone-Test wurde in diesem Planungsschritt ausgeführt.
Alle Zahlen unten bleiben Abnahmeziele, keine behaupteten Messwerte.

## 1. Ausgangslage und festgelegter Weg

Der aktuelle Stand ergänzt bereits `phone_call({})`, freie Unterhaltung und
`end_conversation`. Das bleibt erhalten. `phone_decision` bleibt ein eigener
Modus. Der neue End-Tool-Aufruf allein löst jedoch nicht die gesperrten Sprechphasen,
das frühzeitige Beenden des Workers oder die unvollständige Zustimmungserkennung.

Bevorzugte erste Implementierung:

| Teil | Entscheidung | Grund / verbleibendes Gate |
|---|---|---|
| Transport | Bestehendes SIP, Linphone und zunächst G.711 behalten | Funktionierender Transport; nicht gleichzeitig Codec und Gesprächssteuerung umbauen. Bandbreite bleibt begrenzt. |
| Gesprächsmodell | MAFFEO `gpt-oss-120b` behalten | Kein neues Modellkonto und kein neuer Modellserver. |
| Erkennung | Vorhandenen LiveKit-Zugang für `assemblyai/universal-streaming-multilingual`, Sprache `de`, als bevorzugtes interaktives Profil nutzen | Streaming und deutsche Unterstützung sind offiziell dokumentiert; echte Erkennungsqualität muss im synthetischen Provider-Test bestehen. Groq bleibt ein ausdrücklich wählbares Rollbackprofil, kein stiller Fallback. |
| Turn-Ende | STT-basiertes Turn-Ende plus Silero für unmittelbare Unterbrechung; zusätzlicher expliziter Wartezustand | Sprachbeginn und semantisches Ende sind verschiedene Ereignisse. Keine zusätzliche grosse lokale Modellinstallation als erster Schritt. |
| Stimme | Deutsch ausgewählte Standardstimme mit `cartesia/sonic-3` über vorhandenes LiveKit als bevorzugten Kandidatenpfad | Kein separater Cartesia-Schlüssel nötig. Keine seriös verifizierte deutsche Voice-ID liegt vor; Stimmkatalog und Hörabnahme sind ein zwingendes Gate. Die bisherige Fish-Beispielstimme wird nicht als deutsche Qualitätslösung weitergegeben. |
| Steuerung | Ein `CallController`, ein SDK-Adapter, ein typisiertes Worker-Protokoll | Zustimmung und Auflegen dürfen nicht über mehrere konkurrierende Stellen entschieden werden. |

Anbietersupport ist belegt, Kontoentitlement, Restguthaben, konkrete Voice-ID und
persönliche Klangqualität nicht. Kein Upgrade, Kauf, neues Konto oder behauptetes
unbegrenztes Gratisangebot ist Teil dieses Wegs.

Primärquellen:
- [AssemblyAI über LiveKit](https://docs.livekit.io/agents/models/stt/assemblyai/)
- [Cartesia über LiveKit](https://docs.livekit.io/agents/models/tts/cartesia/)
- [Fish-Standardstimmen und Einschränkungen](https://docs.livekit.io/agents/models/tts/fishaudio/)

## 2. Verantwortlichkeiten und Zustände

Neues reines Python-Modul `src/codex_phone/call_control.py`. Keine Netzwerk-,
SDK-, Datei- oder SQL-Zugriffe darin. Uhr und Ereignisse werden übergeben.
Ein Controller wird nur vom Worker-Eventloop verändert.

```python
Mode = OPEN | DECISION
Phase = LISTENING | THINKING | SPEAKING | HOLDING | READING_BACK | AWAITING_CONFIRM | CLOSING | CLOSED
OutcomeKind = CONFIRMED | ENDED_BY_REQUEST | PEER_CLOSED | TIMED_OUT | CANCELLED | FAILED

Proposal(version, text, readback_complete=False, interrupted=False)
Action = CONTINUE | STOP_OUTPUT | HOLD | READ_BACK | COMMIT | CLOSE
Outcome(kind, call_id, decision=None, proposal_version=None,
        close_observed=False, error_code=None)
```

Externe Schnittstelle, exemplarische neue API, keine bestehende SDK-API:

```python
controller.on_user_message(message_id, complete_text) -> list[Action]
controller.on_output_finished(proposal_version, success, interrupted) -> list[Action]
controller.on_peer_closed() -> list[Action]
controller.on_timeout() -> list[Action]
controller.outcome
```

Nur vollständig zusammengesetzte Nutzeräusserungen werden zur Zustimmung verwendet.
`user_input_transcribed` bleibt Diagnose, `conversation_item_added` darf keine zweite
Zustimmung mehr auslösen. Ein `message_id` wird genau einmal verarbeitet.
Interim-Erkennung darf Audio stoppen, aber nie eine Entscheidung bestätigen.

Priorität vor einem Commit: Beenden/Abbrechen, Korrektur oder Weiterreden, erst dann
vollständige Zustimmung. Nach einem dauerhaften Commit kann der Ausgang nicht mehr
stillschweigend geändert werden. Bestätigte Daten werden bei nachfolgendem
Transportfehler erhalten; der Schliessstatus bleibt separat sichtbar.

### Gewünschte konkrete Semantik

- `OPEN`: freies Gespräch ohne vorgeschriebene Frage und ohne Bestätigungsritual.
  Begrüssung beispielsweise „Hallo, ich höre.“ Danach zuhören.
- `DECISION`: ein konkreter Vorschlag wird kurz vorgelesen. Erst eine neue,
  vollständige Zustimmung danach ermöglicht `CONFIRMED`.
- „Leg auf“, „Beende das Gespräch“: beide Modi beenden, ohne weitere Entscheidung.
- „Sag nicht ‹leg auf›“, „Was bedeutet ‹leg auf›?“ und konditionale Aussagen sind
  keine unmittelbaren Auflegebefehle. Ganze Äusserungen erkennen; keine blosse
  Substring-Suche. Negativtests sind obligatorisch.
- **Vorgeschlagener, noch nicht separat vom Eigentümer bestätigter Default:**
  „Ja, passt, leg auf“ bestätigt und beendet nur in `AWAITING_CONFIRM` nach einem
  vollständig gehörten aktuellen Vorschlag. In anderen Phasen beendet es ohne
  Entscheidung. Ein reines „Leg auf“ bestätigt niemals etwas.
- `Okay, ich`, `Ja ich`, eine Frage oder ein korrigierender Zusatz bestätigen nie.
- `propose_decision` bleibt als Modellwerkzeug, aber der Controller prüft Phase
  und Version. Das pauschale Erzwingen bei nacktem Ja/Okay entfällt.
- `confirm_decision` als konkurrierender Modellweg entfällt. Nur der Controller
  entscheidet über einen abgeschlossenen Nutzer-Turn.
- Ein einheitliches End-Werkzeug steht beiden Modi zur Verfügung. Zusätzlich kann
  der Controller eindeutige Auflegeabsichten direkt behandeln.

## 3. Immer zuhören, trotzdem Zustimmung schützen

`src/codex_phone/voice_session.py` enthält eine gemeinsame Session-Fabrik für
Produktion und Tests. Modelle und Audio-Adapter werden injiziert. Keine zweite,
handgeschriebene Testkonfiguration mit viel kleineren Zeitschwellen.

Verfügbare SDK-APIs wurden lokal geprüft:

```python
from livekit.agents import StopResponse, ToolResult, TurnHandlingOptions
await session.interrupt(force=True)
session.shutdown(drain=True)  # ist synchron; schliesst NICHT selbst SIP
await session.aclose()
```

Erster Konfigurationskandidat, nur nach Tests aktivieren:
- `turn_detection='stt'` für das gewählte Streaming-Profil.
- VAD-Unterbrechung zunächst etwa 0,3 s, nicht die bisherigen 0,7 s.
- False-interruption recovery mit echtem `SipOutput.pause/resume` beibehalten.
- `discard_audio_if_uninterruptible=False`; kein verstecktes Verwerfen von Sprache.
- Jede eigene `say`-Ausgabe unterbrechbar, einschliesslich Begrüssung und Readback.
- Preemptive generation zunächst aus, damit der neue Steuerpfad ohne spekulative
  Werkzeugausführung verifiziert wird. Erst separat messen, ob Wiedereinschalten
  das Latenzziel nötig macht und qualifizierte Äusserungen weiterhin sicher sind.
- Provider-Endpunktoptionen nicht aus fremden SDK-Versionen kopieren. Zuerst den
  minimal dokumentierten Modell-/Sprachvertrag synthetisch prüfen.

AEC-Warmup und Echo sind ein eigenes Gate: Die SDK-Warmup-Phase ersetzt ebenfalls
STT-Eingang durch Stille. Deshalb darf der Zielzustand nicht unverändert darauf
beruhen. Mit gesendeter Stimme als Referenz werden Echo-only und Double-talk
getrennt geprüft. Warmup erst entfernen, wenn die Echo-/Double-talk-Prüfung
besteht. Falls die reale Linphone-Strecke dies nicht besteht, ist die Anforderung
„immer zuhören“ noch nicht erfüllt; nicht durch erneutes Stummschalten kaschieren.

### Versionierter Readback

1. Vorschlag erhält eine neue monoton steigende Version.
2. Nur die zugehörige Ausgabe darf diese Version als vollständig gehört markieren.
3. Sprachbeginn stoppt beziehungsweise pausiert die Ausgabe. Eine echte
   Unterbrechung entwertet die Readback-Berechtigung dieser Version.
4. Eine Korrektur erzeugt eine neue Version; der Callback der alten Ausgabe kann
   diese niemals freigeben.
5. „Ja“ nach abgebrochenem Readback bestätigt nichts. Der Controller kennt den
   Grund und bietet einen kurzen erneuten Readback an, statt erneut nur Ja zu
   verlangen. Ein Auflegewunsch bleibt jederzeit möglich.
6. Der bestehende Schutz über `failed_playbacks`, hörbare Samples und tatsächliche
   Handle-Fehler bleibt zusätzlich erhalten. Ein erfolgreiches Handle allein reicht nicht.

`propose_decision` liefert nach der eigenen Ausgabe
`ToolResult(output=..., reply_required=False)`. So entsteht nach „Soll ich das so
festhalten?“ keine weitere Modellrede. Gleiches gilt für ein End-Werkzeug.
`on_user_turn_completed` kann mit `StopResponse` eine unnötige Modellantwort
unterdrücken; das ist nicht mit dem Stoppen bereits laufender Audioausgabe zu verwechseln.

## 4. Denkpausen, kurze Antworten und tatsächliches Anliegen

Ein ausdrückliches „Moment“, „Ich überlege“ oder „Warte“ setzt `HOLDING`. Dort
startet kein neuer Modellmonolog. Neue Nutzersprache hebt den Zustand auf; das
bestehende maximale Anruflimit bleibt eine Sicherheitsgrenze.

Unvollständige Enden wie „Okay, ich …“ oder „… weil“ dürfen keinen Commit auslösen.
Eine eng begrenzte Zögerungserkennung im Turn-Hook unterdrückt eine sofortige
Antwort und erhält den bisherigen Inhalt. Sie muss mit dem nächsten Turn
zusammengeführt werden; Text darf nicht verloren gehen. Bei Unsicherheit eine
kurze Klärung statt eines neuen Aufsatzes. Streaming-Endsignale sind hilfreich,
aber nicht als bereits bewiesene Denkpausenerkennung ausgeben.

Gesprochene Antwort: standardmässig ein bis zwei kurze Sätze und höchstens eine
Frage. Ein echtes Längenlimit im Ausgabeadapter verhindert wieder lange Reden;
kein blindes Abschneiden mitten im Wort und keine Kürzung des gespeicherten
Entscheidungstexts ohne neuen Readback. Begrüssung wird nicht aus der ganzen
2000-Zeichen-Aufgabe vorgelesen. Voller Kontext bleibt für das Modell verfügbar.

Prompt-Reihenfolge: Nutzeranliegen und Korrekturen, Beenden/Warten, dann optionale
Entscheidungsprozedur. Keine Zusagen über Codeausführung oder Auflegen, bevor der
zugehörige Controllerpfad vorhanden ist. Freies Gespräch benötigt keinen heimlich
erfundenen Projektkontext; fehlendes Wissen wird offen benannt.

## 5. Abschluss bis zur tatsächlichen SIP-Trennung

`cloud_voice.py` kennt SDK und Audio. `cloud_audio.py` kennt den Kindprozess und
liest dessen Protokoll. `bridge.py` besitzt `Sip` und die persistente Zuordnung.
Der Worker allein kann mit `session.shutdown()` keinen SIP-BYE senden.

Versioniertes newline-JSON-Protokoll, beispielsweise:

```json
{"v":2,"type":"ready","call_id":"..."}
{"v":2,"type":"outcome","call_id":"...","kind":"confirmed","decision":"...","proposal_version":2}
{"v":2,"type":"ready_to_close","call_id":"...","farewell_played":true}
```

Parent-Antwort auf dem bisher zu früh geschlossenen stdin:
`{"v":2,"type":"outcome_ack","call_id":"..."}`.
Eine gültige Protokollversion muss bereits vor `ready` und damit vor dem Wählen
vereinbart sein. Ein alter Parent darf nicht erst nach dem Klingeln scheitern.

Ablauf:
1. End-Absicht oder gültige Zustimmung setzt `CLOSING`; neue Modellreden werden
   unterdrückt. Laufende Audioausgabe mit `interrupt(force=True)` stoppen.
2. Worker sendet genau einen typisierten Ausgang, keine missverständliche
   `answer='Gespräch beendet'`-Ersatzentscheidung.
3. Parent validiert Call-ID, Modus, Version und Grenzen. `CONFIRMED` wird einmalig
   gespeichert. Danach bestätigt er den Empfang. Noch kein Prozesskill.
4. Ein vorgewärmter sehr kurzer Abschied darf mit engem Zeitbudget abgespielt
   werden; bei ausdrücklichem sofortigem Auflegen kann er entfallen. Keine neue
   LLM-Antwort dafür erzeugen.
5. Worker meldet `ready_to_close` und schliesst die SDK-Sitzung geordnet.
6. Parent/Bridge führt `await sip.hangup()` aus und wartet begrenzt auf
   `CALL_CLOSED`. Erst dieses Ereignis beziehungsweise ein schon beobachteter
   Peer-Abschluss belegt die physische Trennung. Ein gesendeter Befehl allein nicht.
7. Worker geordnet abwarten; SIGTERM nur nach Ablauf der Grace-Periode, SIGKILL als
   letzter begrenzter Fehlerpfad. Worker behandelt SIGTERM, damit Cleanup laufen kann.
8. MCP liefert Ergebnis und Schliessstatus an exakt den ursprünglichen Aufruf.
   Bereits bestätigte Daten bleiben trotz Abschieds-/Cleanupfehler gültig.

Bei konkurrierendem Peer-BYE und Worker-Receipt wird zuerst ein bereits empfangenes,
gültiges bestätigtes Ergebnis erhalten. Eine kurze begrenzte Drain-Phase kann ein
bereits ankommendes Receipt verarbeiten. Ohne gültige Bestätigung bleibt der
Ausgang `PEER_CLOSED`; Auflegen wird nicht nachträglich als Ja interpretiert.
Ein fehlendes `CALL_CLOSED` wird als ungeprüfter Abschluss gemeldet, nicht als
sicher erfolgreiche Trennung. Weder Timeout noch Fehler starten einen neuen Anruf.

## 6. Deutsche Stimme: ausführbares Auswahl-Gate

1. Im vorhandenen LiveKit-Projekt den angebotenen Standardstimmen-Katalog des
   gewählten Cartesia-Modells öffnen. Nur belegbar deutsche Standardstimmen
   auswählen; Herkunft, ID, Modellkompatibilität und Datum festhalten.
2. Falls der vorhandene Zugang keinen solchen Katalog bereitstellt: vor diesem
   Schritt stoppen und die notwendige legitime Katalogzugänglichkeit klären.
   Keine ID erfinden und kein zusätzliches Konto stillschweigend anlegen.
3. Maximal drei Kandidaten mit denselben kurzen deutschen Testsätzen erzeugen,
   nachdem tatsächliche Kontogrenzen und erlaubter Verbrauch geprüft wurden.
   Testtexte bleiben synthetisch, keine Stimme des Eigentümers klonen.
4. Jeden Clip original sowie nach G.711-Roundtrip hören. Namen, Umlaute, Zahlen,
   Fragen und eine ruhige längere Antwort einschliessen.
5. Eigentümer beurteilt einmal gebündelt Akzent, Verständlichkeit und Ton.
   Ohne diese Abnahme bleibt „gutes Deutsch“ UNVERIFIED. Kein weiterer Testanruf
   ist für diese vorbereitende Stimmwahl nötig.
6. Wenn die akzeptierte Stimme erst nach G.711 unbrauchbar wird, Codecwechsel als
   separates Arbeitspaket prüfen. Keine Änderung an globalen Homebrew-Bibliotheken
   oder am gepatchten SIP-Transport ohne eigene Regression und Rückfallweg.

## 7. Arbeitsreihenfolge und Tests

| Paket | Dateien / Änderung | Falsifizierbare Abnahme |
|---|---|---|
| 1 | `call_control.py`, neue Controller-Tests | Reine End-Absicht braucht keinen Vorschlag; Fragmente und Zitate bestätigen/beenden nicht; Korrektur entwertet alte Version. |
| 2 | `voice_session.py`, `decision_agent.py`, `cloud_voice.py` | Produktionsidentische Optionen; Greeting/Readback unterbrechbar; keine STT-Stille; kein zweiter LLM-Aufruf nach Readback. |
| 3 | `cloud_voice.py`, `cloud_audio.py`, `bridge.py`, `mcp_server.py` | Versionierter Endpfad, persistiertes Receipt, realer lokaler SIP-BYE, eindeutige Outcomes, keine neue Wahl bei Fehler. |
| 4 | `voice_models.py`, eng begrenzte Profiloptionen | Streaming-Modellvertrag erfüllt; Modell, Voice und Sprache atomar validiert; keine stille Providerersetzung. |
| 5 | Fehlerlogger und Worker-Bootstrap | Begrenzte echte stderr-Diagnose, Start-/Fehlerursache und Status; keine Secrets, Transkripte oder rohen Providerantworten. |
| 6 | Testskripte und Liefernachweis | Offline vor Cloud, Cloud vor persönlicher Telefonabnahme, keine simulierten Prüfungen als iPhone-PASS. |

Zuerst bestehendes Fehlverhalten als roten Test reproduzieren, dann denselben Test
grün machen. Neue Factory sowohl im Worker als auch in Tests verwenden.

Pflichtfälle:
- „Leg auf“ während Begrüssung, normaler Antwort, Readback und Wartezustand.
- Echo-only, echtes Double-talk und kurzer Lärm als verschiedene Audioszenarien.
- Unterbrochener oder transportfehlerhafter Readback, danach Ja: keine Zustimmung.
- „Okay, ich“ mit Denkpause: kein Commit, kein verlorener nachfolgender Satz.
- Negation, Zitat, Frage, Korrektur und neuer Vorschlag mit spätem altem Callback.
- „Ja, passt, leg auf“ mit und ohne vollständig vorgelesenen aktuellen Vorschlag.
- Peer-BYE gleichzeitig Receipt, Timeout, kaputte JSON-Zeile, falsche Call-ID,
  veraltetes Protokoll, Rate-Limit, abgebrochener MCP-Client und Daemonrestart.
- Rückgabe an denselben Aufruf, genau eine Wahl, keine Vermischung zweier Clients.

Messziele nach Implementation, keine heutigen Eigenschaften:
- Lokaler Output stoppt innerhalb von 100 ms nach validiertem Stop-Ereignis;
  Sprachbeginn bis letztes hörbares lokales RTP-Zeichen separat messen, Ziel ≤500 ms.
- Lokales `CALL_CLOSED` innerhalb 1 s nach `ready_to_close`; kein Erfolgs-PASS ohne
  dieses Signal. Gesamtdauer ab gesprochenem Wunsch separat messen, Ziel ≤2 s.
- Antwortbeginn ab tatsächlichem Ende der Nutzersprache: Ziel Median ≤2 s,
  p95 ≤3 s unter dokumentierten Testbedingungen. Keine VAD-/Endpoint-Summen bilden.
- Eine 2-s-Denkpause nach angekündigtem „Moment“ löst keinen neuen Monolog aus.
- Kein Zustimmungstest darf durch ein Satzfragment grün werden.

Für p95 ausreichend viele synthetische Turns ausführen und Stichprobengrösse
angeben. Lokales RTP ist nicht die wahrgenommene iPhone-Latenz. Echte akustische
Abnahme erst nach bestandenen automatischen Reproduktionen und auf neue ausdrückliche
Anrufanweisung. In diesem Planungsauftrag wird niemand angerufen.

## 8. Datenschutz, Logs, Aktivierung und Rollback

Diagnose pro Turn: monotone Zeiten, Ereignistypen, Phase/Version, tatsächliche
Pause→Resume- und Pause→Abbruch-Übergänge, Fehlerklasse und Statuscode. Keine
Gesprächsinhalte speichern. Clear-Aufrufe ohne ausstehendes Audio getrennt zählen.
Zähler sind keine bewiesenen abgeschnittenen Antworten.

Worker-stderr über einen begrenzten Reader in eine private rotierende Logdatei
führen, beispielsweise 128 KiB plus zwei Backups. Nur sichere strukturierte Felder
übernehmen; unbekannte rohe Providertexte nicht unverändert protokollieren.
Rate-Limit und Längengrenzen müssen auch bei Logfluten gelten. Kein `/dev/null`
als Versteck für Startfehler, kein unbeschränkter direkter Dateideskriptor.

Vor Aktivierung: Source-Commit und lokale Backup-Referenz, unveränderte Ledger und
Antworten, erfolgreiche automatisierte Tests, tatsächlich erlaubtes Providerbudget,
validiertes Modell-/Stimmprofil. Nur gezielte private Profilfelder ändern; keine
vollständige Runtime-Konfiguration oder Datenbank ersetzen.

Parent-Code ist im langfristigen Bridge-Daemon geladen: bei IDLE geordnet stoppen
und mit neuem Code starten. Kein aktives Gespräch abbrechen. Neue Worker melden
Protokoll-/Buildversion; vor einer Wahl Kompatibilität prüfen. Native MCP-Clients
gezielt reconnecten, falls sie die neuen Tools nicht kennen; keine fremden
Agentensitzungen töten. `phone_call` bleibt argumentlos und auf das konfigurierte
persönliche Ziel beschränkt.

Rollback: vorige Source-/Profilversion zusammen wiederherstellen, Daemon nur bei
IDLE neu laden, Daten nicht zurückrollen. Ein technisch funktionierendes altes
Profil darf nicht als weiterhin persönlich akzeptierte Sprachqualität ausgegeben werden.

## 9. Go / No-Go und ehrlicher Abschluss

**Technisch baubar: ja. Bereits umgesetzt oder zuverlässig im Alltag bewiesen: nein.**
Der vorhandene Transport und die SDK-APIs tragen diesen Weg; eine Neuimplementierung
aller Dienste ist dafür nicht begründet. Die entscheidende Änderung ist die gemeinsame
Gesprächssteuerung, nicht eine weitere Ja-Wortliste.

No-Go: unsichere fragmentierte Zustimmung, unhörbare Nutzerrede, fehlender echter
Endpfad, Echo-Selbstunterbrechung, unbekannte Protokollkompatibilität oder nicht
freigegebene Provider-/Stimmnutzung. In solchen Fällen nicht als fertig aktivieren.

Aktuell tatsächlich ausgeführt durch Codex: **59 Offline-Tests bestanden** auf dem
aktuellen Stand, öffentliche Anbieter-Dokumentation gelesen und die genannten
SDK-Exporte/Signaturen lokal geprüft. Die hier geplanten neuen Verhaltensfälle,
Streaming-Qualität, native deutsche Stimme, tatsächliche neue Anrufbeendigung und
persönliche iPhone-Erfahrung sind damit noch nicht bewiesen.

Der frühere unabhängige Claude-Audit bleibt eine Grundlage. Eine neue unabhängige
Prüfung dieser konkreten Vorlage durch Claude ist wegen der beobachteten SSO-Blockade
**offen**, nicht PASS. Nach legitimer Wiederherstellung des bestehenden Zugangs ist
gezielt dieser Plan zu prüfen, nicht die gesamte Vorgeschichte neu zu starten.
