# Claude Code: unabhängiger Fix-Review

Lokale CLI 2.1.308, Modell claude-opus-5-5[1m]. Snapshot des aktuellen Diffs; keine ausgeführten Checks durch den Reviewer.

# Code-Review Phone-Fix (statisch, nichts ausgeführt)

Ich sehe zwei blockierende Bugs. Beide führen zum selben Fehlerbild: Ein „Ja“, das nicht frisch nach dem vollständig gehörten Readback kam, kann als Bestätigung zählen. Beide sind nur aus dem Code abgeleitet, also **nicht verifiziert**.

## 1. `CallController.speech_started`: Onset wird überschrieben → stale „Ja“

**Ursache:** `speech_started()` setzt `self.onset = self.now()` bei jedem VAD-Onset. `user_turn()` liest den Wert erst beim Turn-Ende. Zählt also nicht der Beginn des Turns, sondern der letzte Onset davor.

**Ablauf:**
1. `perform_readback` spielt den Vorschlag ab. Kurz vor dem Ende sagt der Nutzer ein kurzes „Ja“ (unter 0,3 s, löst also keine Unterbrechung aus). `speech_started` setzt `onset = t1`.
2. Der Readback endet. `read_back(version, ended_at=t2)` wird aufgerufen, mit `t2 > t1`. `read_back_at` entspricht dem aktuellen `turn`, das „Ja“ ist noch nicht gezählt.
3. Vor dem finalen Transkript des „Ja“ kommt ein zweiter VAD-Onset ohne STT-Text (Atmen, Geräusch, Leitungsrauschen). Dann gilt `onset = t3 > t2`.
4. Das Endpointing (0,7 s) liefert den Turn „Ja“. `onset > ended_at` ist erfüllt und `turn > read_back_at` ebenfalls. `confirm()` läuft durch, `pending` wird gesetzt.
5. Nach `commit_delay` liefert `tick()` den Status `confirmed`. Kommt kein weiterer Onset, wird `pending` nicht verworfen.

Damit wird ein „Ja“ zur Zustimmung, das während des Readbacks begann.

**Fix:** Nur den ersten Onset seit dem letzten Turn festhalten, also `if self.onset is None: self.onset = self.now()`. `pending` weiter verwerfen und invalidieren wie bisher. Als Test: Onset vor `ended_at`, dann ein zweiter Onset danach, dann `user_turn('Ja')`. Erwartet: keine Bestätigung.

## 2. `state_changed` / `perform_readback`: Agent-Sprache direkt nach dem Readback entwertet nicht

**Ursache:** `agent_spoke()` wird nur bei einem Übergang nach `speaking` aufgerufen und nur, wenn `reading_back` falsch ist. `decision.read_back(...)` läuft erst, nachdem `wait_for_playout()` in den Tool-Task zurückgekehrt ist.

**Ablauf:**
1. Während des Readbacks sagt der Nutzer ein kurzes „Ja“ ohne Barge-in. `user_turn` liefert `RESPOND`, weil `eligible` falsch und `retry_proposal` `None` ist. Das LLM erzeugt eine normale Antwort, die nach dem Readback in der Warteschlange steht.
2. Der Readback-Handle endet. Der Scheduler startet sofort die LLM-Antwort. Dabei gibt es zwei Möglichkeiten:
   - Der Agent-State bleibt durchgehend `speaking`. Dann gibt es kein Event und `agent_spoke` wird nie aufgerufen.
   - Das Event `speaking` kommt, bevor der Tool-Task weiterläuft. Dann ist `reading_back` noch wahr und das Event wird ignoriert.
3. Danach setzt `read_back()` `readback_ended_at` und `read_back_at`. Zuletzt gehört hat der Nutzer aber die LLM-Antwort, nicht den Vorschlag.
4. Ein frisches „Ja“ nach dieser Antwort ist `eligible`, und `confirm()` bestätigt den alten Vorschlag. Die LLM-Antwort kann den Vorschlag inhaltlich verändert oder relativiert haben.

**Einordnung:** Ob der State durchgehend `speaking` bleibt oder das Event vor dem Resume kommt, hängt vom SDK-Scheduling ab. **Wahrscheinlich, zu prüfen.** Welcher der beiden Fälle eintritt, ist für den Fehler egal.

**Fix:** Nach `wait_for_playout()` prüfen, ob eine andere Speech aktiv oder eingereiht ist. Zum Beispiel: Ist `session.current_speech` nicht `None` und nicht der eigene Handle, dann `read_back` nicht setzen. Alternativ jede neu erzeugte Speech außer dem Readback-Handle als `agent_spoke` werten, unabhängig von State-Übergängen. Als Test: ein „Ja“ mitten im Readback, das eine LLM-Antwort auslöst. Danach darf ein „Ja“ nicht bestätigen.

## Geprüft, kein blockierender Bug gefunden

- **Korrektur oder HOLD während des Readbacks:** `heard()` bzw. HOLD rufen `invalidate()` auf und erhöhen `version`. `read_back(version)` liefert dann `False`, `read_back_at` bleibt `None`. `readback_failed` setzt bei abweichender Version kein Retry.
- **Commit-Delay:** `speech_started`, HOLD, Nicht-Bestätigung und `agent_spoke` entwerten `pending`. `tick()` vergleicht die Version.
- **StopResponse:** Die Nachricht wird vor dem `raise` in `chat_ctx` übernommen.
- **`reply_required=False`:** Ist auf allen Pfaden von `perform_readback` gesetzt.
- **Readback ohne 2-Satz-Limit:** `tts_node` umgeht `short_speech`, solange `reading_back` gesetzt ist. Das Flag wird vor `say()` gesetzt und erst nach dem Playout zurückgesetzt.
- **Persist vor ACK:** `persist_outcome` schreibt `ANSWERED`, bevor `outcome_ack` gesendet wird.
- **Kein Verlust von `ANSWERED` bei Abbruch:** `Store.set_question` schützt `ANSWERED` vor `ORPHANED`, `WAITING`, `ENDED_NO_DECISION`, `COMPLETED` und `EXPIRED`. Das deckt die Cancel-Pfade in `call` und `command` ab.
- **Parent beobachtet den SIP-Hangup:** `converse` wartet auf `sip.disconnected`, liest danach noch 1,5 s nach und legt im `finally` auf, bevor der Worker gestoppt wird.
- **OPEN ist nie Consent:** `eligible` erfordert `not conversation`, `finish` lässt `answer` weg, es gibt keine Tools, und `decode` lehnt `confirmed` bei einer Konversation ab.
- **Kein automatischer Replay:** Kein automatischer Retry. `ENDED_NO_DECISION` enthält die Anweisung „Do not automatically call again“. Ein Retry-Readback ist nur ein Vorlesen, keine Zustimmung.

## Nicht blockierend, aber erwähnenswert

- In `converse` wirft `task.result()` bei einer Zeile über dem Limit einen `ValueError` außerhalb des `try`. Nach einem bereits empfangenen Outcome wird so aus einem Cleanup-Fehler eine Exception. `ANSWERED` bleibt trotzdem geschützt.
- Bei einem Peer-Hangup erfährt der Worker nichts davon. Er wird erst über `stdin`-Close und `terminate` beendet, nach etwa 4,5 s. Das funktioniert, ist aber langsam.

## Fazit

Bug 1 und Bug 2 sollten vor einem echten iPhone-Test behoben und mit je einem Offline-Test reproduziert werden. Die 72 grünen Tests decken beide Abläufe offenbar nicht ab.


## Nachprüfung und Umsetzung durch Codex

Die oben unveränderte Autorenfassung prüfte einen Zwischenstand. Beide gemeldeten
Blocker wurden danach behoben: erster Onset bleibt bis zum Turn erhalten;
`attach_controller` entwertet über `speech_created(generate_reply)` unabhängig
vom speaking-State. Rote Onset-Reproduktion → grün; echter SDK-Test für neue
generierte Speech und alten Readback-Callback → grün. Final 75 Tests grün.

Der nachfolgende unabhängige Subagent-Nachreview fand keine weiteren konkret
belegten Consent-/Protokollblocker (13 gezielte Tests selbst ausgeführt).
Composed MCP/SIP/Cloud-Entscheidung mit Fish und Cartesia-de sowie OPEN HOLD→END
mit Cartesia-de bestanden. Kein iPhone-Anruf; keine subjektive Klangabnahme.
Stand gepusht und aktiviert: 3727367. Siehe CALLING-FIX-2026-10-24.md.
