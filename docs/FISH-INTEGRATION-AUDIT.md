# Fish-Integration: Recherche vor der Implementierung

Historischer Recherche-Snapshot vor der Cloud-Implementierung. Aktueller Betrieb und Tests: CLOUD-VOICE.md und CLOUD-ACCEPTANCE.md.

Stand: 15. Oktober 2026. Ergebnis: Kandidat für einen begrenzten Praxistest; noch keine Fish-Integration und kein Live-Nachweis. Budgetrahmen: insgesamt 5 CHF für den Versuch, keine automatische Aufladung. Lokale Spracherkennung ist ausgeschlossen.

## Was der vorhandene Code tatsächlich macht

- `audio.py`: macOS say erzeugt zuerst eine vollständige WAV-Datei. Erst danach wird PCM in den SIP-Strom eingespeist. Es gibt kein Streaming vom Sprachmodell zur Stimme.
- `listen()` beginnt erst nach `speak()` und leert zuvor den Empfangspuffer. Sprechen während der Ausgabe wird nicht als Gesprächsbeitrag verarbeitet. Eine feste RMS-Schwelle und 1,3 Sekunden Pause entscheiden über das Ende einer Äußerung.
- Erst anschließend läuft whisper-cli über eine komplette Aufnahme. Diese lokale Erkennung entspricht nicht mehr dem gewünschten Produkt.
- `bridge.py`: eine Frage, eine Antwort, starre Bestätigungsphrase; höchstens zwei Antwortversuche. Es existiert kein freies mehrstufiges Gespräch und kein Unterbrechen der Ausgabe.
- `codex.py`: Der Entwicklungs-Turn wartet in `phone_decision`. Dessen ursprüngliche RPC-Antwort setzt ihn fort. Das ist keine vorhandene Chat-Completions-Schnittstelle für beliebig viele Gesprächsrunden. Eine Gesprächsschicht muss ausdrücklich eingeführt werden.
- `sip.py`: Nur G.711 geladen. Der Sprachcodec arbeitet mit 8 kHz; die interne PCM-Verarbeitung mit 16 kHz stellt die verlorene Bandbreite nicht wieder her. Die hochwertige Fish-Webvorschau beweist deshalb nicht dieselbe Klangqualität im Telefonat. Einen gemeinsam unterstützten Breitbandcodec müssen wir gesondert aushandeln und testen.
- Bestehende Zuordnung von Frage, Thread, Turn und RPC sowie die getrennte Sicherheitsfreigabe bleiben erforderlich. Ein Gesprächsabbruch darf keine Entscheidung erfinden.

## Neue offizielle Fish-Befunde

Fish Agents ist als öffentliche Beta dokumentiert. Die Plattform übernimmt Spracherkennung, Sprechwechsel und Sprachausgabe. Das widerspricht der zu engen bisherigen Aussage, Fish liefere nur einzelne Sprachbausteine. Es ist ein dokumentierter Kandidat, kein bereits getesteter Ersatz.
Quelle: https://docs.fish.audio/agents/overview

Der dokumentierte Medienweg ist LiveKit/WebRTC mit Audiotracks. Kontrollnachrichten unterstützen unter anderem Unterbrechen, Auflegen und Ergebnisse von Client-Tools. Für unseren SIP-Anruf wäre ein echter bidirektionaler PCM-zu-WebRTC-Adapter nötig. Ein Browser-Widget wäre nur ein vorgelagerter Test, kein Ersatz für den geforderten iPhone-Anruf.
Quelle: https://docs.fish.audio/agents/deploy/protocol

Custom LLM verlangt einen öffentlich erreichbaren HTTPS-Endpunkt mit gestreamtem Chat-Completions-Vertrag. Dokumentiert sind eine Wiederholung und eine Antwortgrenze von zehn Sekunden. Unsere lokale Codex-App-Server-Verbindung erfüllt diesen Vertrag nicht unmittelbar. Öffentliche Erreichbarkeit und neue Zugangsdaten dürfen nicht beiläufig eingerichtet werden.
Quelle: https://docs.fish.audio/agents/build/custom-llm

Die einzelne ASR-Schnittstelle nimmt Audiodateien entgegen; der dokumentierte TTS-WebSocket allein beweist keine bidirektionale Streaming-ASR-Schnittstelle. Aus Werbetexten darf keine solche Schnittstelle erfunden werden.
Quellen: https://docs.fish.audio/api-reference/endpoint/openapi-v1/speech-to-text und https://docs.fish.audio/api-reference/endpoint/websocket/tts-live

Die veröffentlichten Einzelpreise nennen ASR mit 0,36 USD pro verarbeiteter Audiostunde und s2.1-pro-free mit 0 USD für TTS. Damit ist der Gesamtpreis einer Agents-Sitzung einschließlich Modell/Transport noch NICHT bestimmt. Diese Einzelpreise dürfen nicht als Agent-Tarif verwendet werden. Der unten ergänzte Agent-Tarif und der lesende Kontocheck lösen einen Teil dieser offenen Fragen auf. Keine Zusage zu Gesprächsminuten für 5 CHF.
Quelle: https://docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits

## Zwei unterschiedliche Integrationswege

A. Fish Agents führt das Gespräch mit einem eigenen Gesprächsmodell und einem knappen, ausdrücklich freigegebenen Aufgabenkontext. Ein enges Client-Tool kann die bestätigte Produktentscheidung an den ursprünglichen wartenden Codex-Turn zurückgeben. Das könnte Eigenbau und öffentliche Webhooks vermeiden; Kosten und Kontofunktionen müssen zuerst geprüft werden. Der Gesprächsagent ist ausdrücklich nicht identisch mit dem wartenden Entwicklungs-Agenten. Tools dürfen keine Shell-, Datei-, Netzwerk- oder Sandbox-Freigaben aus Sprache übernehmen.

B. Codex erzeugt auch die Gesprächsantworten. Dafür braucht es einen getesteten Dialog-Adapter, ausreichenden Kontext und niedrige Antwortlatenz. Ein separater Gesprächs-Thread wäre transparent als solcher zu kennzeichnen; er wäre keine heimliche Fortsetzung des wartenden Entwicklungs-Turns. Der finale Entscheidungsweg muss weiter zum originalen RPC führen. Direktes Starten eines zweiten Turns im bereits blockierten Entwicklungs-Turn ist keine ausgearbeitete Lösung.

Zunächst A auf Zugang, Preis und Gesprächsqualität prüfen. B nur weiterverfolgen, wenn Codex selbst als Gesprächsmodell zwingend ist und gemessene Latenz passt. Keine Variante als schon implementiert darstellen.

## Verbindliche Testreihenfolge

1. Konto nur lesend prüfen: Agents verfügbar? Welche Vorschau-Stimme/Modell? Vollständiger Agent-Tarif, Kreditbedingungen und Aufnahme-/Transkriptaufbewahrung? Nicht aufladen, solange der Gesamtpreis unklar ist.
2. Kurzer privater Fish-Gesprächstest ohne private Projektdateien: Deutsch verstehen, drei aufeinanderfolgende Rückfragen, Korrektur und Unterbrechen. Zielwerte zum Bewerten, keine zugesagten Messwerte: Antwortbeginn p95 unter zwei Sekunden, Ausgabe nach Unterbrechen unter 500 ms stoppen. Tatsächliche Kosten erfassen; Kontext und Sprachqualität beurteilt der Nutzer.
3. Erst bei bestandenem Gesprächstest denselben Medienweg über den echten Mac-SIP-Anruf anbinden. Prüfen: beide Richtungen, ausgehandelter Codec, Resampling, Echo, Puffer und Abbruch. Test mit gesperrtem iPhone und zusätzlich mobilen Daten. Keine Mac-Lautsprecher-Schleife.
4. Einen echten offenen Codex-Entscheid mit begrenztem Kontext im Gespräch klären, korrigieren, natürlich bestätigen und exakt dem ursprünglichen Thread/Turn/RPC zuführen. Danach die tatsächliche Dateiänderung prüfen. Keine starre Bestätigungsphrase als alleinige Benutzerführung.
5. Fehlerprüfungen: nicht angenommen/abgelehnt, Verbindungsabbruch vor Bestätigung, verspätete/doppelte Antwort, zwei parallele Aufgaben, API-/Budgetfehler, Neustart. Kein automatischer Ersatz durch lokale STT und keine Endlosschleife.

Budget muss vor jeder abrechenbaren Operation reserviert werden, inklusive begrenzter Wiederholungen und Sicherheitsreserve. Gesprächsdauer allein ist kein verlässlicher Kostenbegrenzer, solange das Tarifmodell unbekannt ist. Keine automatische Aufladung. CHF/USD und Gebühren berücksichtigen. Kontoweite Ausgaben anderer Anwendungen können eine lokale Zählung überholen; lokale Schätzung nicht als garantierte Anbieter-Abrechnungssperre ausgeben.

## Tatsächlich ausgeführte Prüfungen

Code und Dokumentation gelesen, sauberer Git-Stand vor diesem Bericht, 15 bestehende Tests ausgeführt: PASS. Diese Tests betreffen die bisherige Bridge, nicht Fish. Offizielle Fish-Seiten und Index live abgerufen. Keine neue Installation, keine Fish-Zugangsdaten gelesen, keine Audio-/Projektdateien an Fish übertragen, kein kostenpflichtiger API-Aufruf, kein Anruf und keine neue öffentliche Schnittstelle im Rahmen dieser Analyse.

Offene Gates nach der unten ergänzten Recherche: konkrete Vorschau-Stimme, Live-Gesprächsqualität, echter SIP/WebRTC-Medienadapter, sicherer Dialog-/Entscheidungsvertrag, Aufbewahrungsbedingungen und vollständiger neuer E2E-Nachweis.


## Vertiefter Vergleich und aktualisiertes Urteil

Die weitere Recherche ändert das Urteil zugunsten eines frühen Fish-Agents-Tests: Der vollständige Basistarif ist inzwischen offiziell gefunden. Fish Agents ist für die vom Nutzer bevorzugte Stimme der erste Testkandidat; eine technische oder qualitative Überlegenheit gegenüber Gemini Live ist ohne Vergleichsgespräch nicht bewiesen. Kein kostenpflichtiger Test wurde ausgeführt.

### Kosten und tatsächlicher Kontocheck

Die offizielle [Agent-Preisseite](https://docs.fish.audio/agents/pricing) nennt 0,06 USD pro Gesprächsminute einschließlich STT, TTS, Basis-LLMs und Tools; sekundengenaue Zählung. Die Übernahme der Basis-LLM-Kosten ist ausdrücklich eine zeitlich nicht garantierte Promotion. Andere Modelle kosten zusätzlich nach Tokens. WebRTC benötigt keine gemietete Telefonnummer. Builder-Vorschaugespräche sind laut Dokumentation kostenlos. Abrechnung erfolgt beim Sitzungsende: Eine lokale Budgetkontrolle darf keine sofortige serverseitige Ausgabensperre voraussetzen.

Reine Basiskosten: 5 Minuten = 0,30 USD; 10 = 0,60 USD; 30 = 1,80 USD. Das sind Rechenbeispiele, keine ausgeführten Gespräche und keine CHF-Umrechnung. 5 / 0,06 ergibt rechnerisch rund 83 Minuten ohne Zusatzkosten. Die Dokumentation selbst beschreibt das Testguthaben jedoch als ungefähr 60 Minuten: Diese Abweichung verhindert eine verbindliche Minutenzusage.

Lesend im angemeldeten Browser bestätigt: Agent-Bereich verfügbar, 5,00 USD Testguthaben vollständig vorhanden, reguläres Guthaben 0,00 USD, automatisches Aufladen aus, noch keine Agent-Gebühren. Keine Aufladung und kein Agent angelegt. Diese persönlichen Kontodetails nicht als allgemeine Verfügbarkeit oder dauerhaftes Angebot behandeln.

### Was Fish tatsächlich ersetzt

[Voice & Language](https://docs.fish.audio/agents/build/voice-language) dokumentiert standardmäßig Deepgram Nova-3 für Erkennung, alternativ ElevenLabs Scribe. Fish übernimmt die Stimme. Die Architektur bleibt somit Cloud-STT → Gesprächsmodell → TTS. Deutsch ist gelistet; Schweizerdeutsch ist damit nicht nachgewiesen. Dokumentierte TTS-Auswahl für Agents: s2.1-pro oder drama-3; das kostenlose Einzel-TTS-Modell darf nicht als Agent-Einstellung vorausgesetzt werden.

Dies erfüllt den Ausschluss lokaler Erkennung. Es erfüllt noch nicht den Anspruch, direkt mit dem ursprünglichen Codex-Modell zu sprechen. Für den ersten Versuch ist ein eigener, auf die offene Frage begrenzter Gesprächsagent die kleinere Integration. Er erhält weder vollständige Projektdateien noch allgemeine Shell-Werkzeuge und liefert nur einen bestätigten Entscheid zurück.

### SIP und CallKit

Fish bietet [SIP-Trunks](https://docs.fish.audio/agents/telephony/byo-sip), setzt dabei aber eine eigene E.164-Nummer beim Carrier und Trunk-Konfiguration voraus. Das ist kein belegter Login mit zwei persönlichen Linphone-SIP-Konten. Keine erfundene Nummer importieren und keine kostenpflichtige Nummer kaufen.

Für unseren bestehenden kostenlosen SIP-Weg bleibt der bevorzugte Entwurf: iPhone/CallKit ↔ Linphone-SIP ↔ Baresip auf dem Mac ↔ bidirektionaler PCM/LiveKit-Adapter ↔ Fish Agents. Fishs WebRTC-Protokoll ist dokumentiert, dieser Adapter ist noch nicht gebaut. CallKit-Zustellung bleibt ein eigener realer Test und wird durch keinen Cloud-Sprachanbieter automatisch verbessert.

### Vergleich mit anderen aktuellen Angeboten

| Lösung | Aktuell dokumentierte Kosten | Eignung für dieses Projekt |
| --- | --- | --- |
| Fish Agents | 0,06 USD/min mit abgedecktem Basismodell; weitere LLMs extra | Favorit für Test mit gewünschter Fish-Stimme; LiveKit-Adapter und Beta-Risiko |
| Gemini Live | Audio 3 USD/M Eingangstokens, 12 USD/M Ausgangstokens; Text separat, begrenztes Free Tier | Stärkster Gegenkandidat für natives Audio-zu-Audio und einfachere PCM/WebSocket-Anbindung; andere Stimmen |
| Deepgram Voice Agent | Standard 0,075 USD/min; BYO-TTS 0,065 USD/min plus fremde TTS-Kosten | Gebündelte Alternative; direkter Fish-TTS-Support in gelesener Modellliste nicht belegt |
| Cartesia Agents | 0,06 USD/min; Free-Plan nennt 1 USD Agent-Guthaben/Monat | Kosten vergleichbar, eigene Stimme; zeitweise LLM-Promotion nicht als dauerhaft gratis rechnen |
| ElevenAgents | Free-Plan nennt 15 Minuten/Monat; LLM-/Telefoniekosten separat beachten | Testbare Alternative, aber Fish-Stimme und vorhandene SIP-Strecke nicht nachgewiesen |

Quellen: [Gemini Preise](https://ai.google.dev/gemini-api/docs/pricing), [Live-Fähigkeiten](https://ai.google.dev/gemini-api/docs/live-api/capabilities), [Deepgram Preise](https://deepgram.com/pricing), [TTS-Modelle](https://developers.deepgram.com/docs/voice-agent-tts-models), [Cartesia Preise](https://www.cartesia.ai/pricing), [ElevenAgents Preise](https://elevenlabs.io/pricing/agents).

Die Einschätzung zum Integrationsaufwand ist eine technische Ableitung aus den dokumentierten Transporten und unserem vorhandenen PCM-Treiber, keine gemessene Implementierungszeit. Gemini spricht direkt Audio-zu-Audio und kann Unterbrechungen signalisieren. Fish erlaubt eine passend gewählte Lieblingsstimme, ist aber keine belegte native Speech-to-Speech-Architektur. Beide benötigen Aufgaben-Kontext, sichere Zuordnung und dieselbe finale Rückgabe an den wartenden Codex-Turn. Free-Tier-Quoten sind kontoabhängig; keine Garantie, damit dauerhaft zu arbeiten.

### Datenschutz und offene Nachweise

[Fish Conversation History](https://docs.fish.audio/agents/monitor/conversation-history): Produktionssitzungen speichern Transkript und Metadaten immer; Audioaufzeichnung ist standardmäßig aktiviert und kann abgeschaltet werden. Ausschalten der Aufnahme beseitigt nicht das gespeicherte Transkript. Konkrete Speicherfrist, Löschbarkeit, Verarbeitungsregion und Trainingsnutzung sind hier nicht verifiziert. Die verlinkte öffentliche Privacy-Seite lieferte beim Abruf keine brauchbare ausführliche Richtlinie; deshalb keine Zusage dazu. Keine privaten Codex-Projektinformationen übertragen, bevor diese Datenentscheidung geklärt ist.

Google nennt für das reguläre Gemini-Free-Tier Nutzung der Inhalte zur Produktverbesserung, für Paid nicht. Das ist ein materieller Unterschied für private Aufgaben; Free nicht pauschal empfehlen.

### Konkrete Empfehlung

Zuerst kostenloser Fish-Builder-Gesprächstest mit der gewünschten Stimme, neutralem Kontext und deaktivierter Audioaufnahme. Drei Rückfragen, Schweizerdeutsch, Korrektur und Unterbrechen prüfen. Bei unzureichendem Ergebnis vor Integration abbrechen und Gemini Live vergleichen. Bei bestandenem Test die bestehende SIP-Strecke mit Fish-WebRTC verbinden; keinen zusätzlichen PSTN-Dienst einführen. Anschließend echter Codex-Entscheid mit Fortsetzung des ursprünglichen Threads und vollständiger Fehlerprüfung.

Das fünf-Dollar-Testguthaben macht eine sofortige Zahlung unnötig. Derzeit sind weder Fish-Antwortlatenz noch Schweizerdeutsch-Verständnis, Barge-in über SIP, Breitbandcodec oder vollständiger neuer E2E-Ablauf gemessen. Ergebnis bleibt PARTIAL; Recherche ist kein Integrationstest.
