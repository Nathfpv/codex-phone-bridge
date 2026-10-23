
<!-- codex-phone-bridge:start -->
## Telefonanrufe und Entscheidungen

Wenn der Nutzer einen Anruf verlangt («Ruf mich an», «ich möchte reden»), prüfe
`phone_status` und starte bei `can_call=true` sofort `codex-phone.phone_call` ohne
Argumente. Kein Grund, Thema oder Entscheidungsbedarf ist nötig; das Anliegen darf
erst im Gespräch kommen. Bei Fehler keinen automatischen Wiederholungsanruf starten.

Wenn eine notwendige Produkt- oder Designentscheidung die laufende Aufgabe blockiert,
verwende das lokale MCP-Werkzeug `codex-phone.phone_decision` mit einer konkreten Frage
und dem nötigen Kontext. Bei verfügbarem Werkzeug hat der Telefonkanal Vorrang vor
Text-Rückfragen; Routineentscheidungen weiterhin selbstständig lösen. Prüfe vorher
`phone_status`: Bei fehlender Verfügbarkeit oder `can_call=false` die Frage als offen
melden und unabhängige Arbeit fortsetzen. Nur mit `confirmed=true` die zurückgegebene
Entscheidung in derselben Aufgabe umsetzen. Bei Fehler/Abbruch keine Antwort annehmen
und keinen automatischen Wiederholungsanruf starten. Datei-, Shell-, Netzwerk-, Konto-
und Sandbox-Freigaben bleiben in den regulären authentifizierten Freigabedialogen.
<!-- codex-phone-bridge:end -->
