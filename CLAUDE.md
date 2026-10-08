# Projektregeln

## Geheimer Abo-Link

Der ICS-Abo-Link der Hochschule ist personalisiert und geheim. Er steht
ausschließlich in `.env` und im GitHub Secret `UNI_ICS_URL`. Er darf niemals
in einer anderen Datei auftauchen – auch nicht als Beispiel, Kommentar,
Testdaten oder in Log-Ausgaben. In Dokumentation und Code wird er nur als
Platzhalter wie `aus GitHub Secret UNI_ICS_URL` referenziert.

Das gilt auch für Fehlermeldungen: Ausnahmen von `requests` enthalten die URL.
Sie werden deshalb nie unverändert geloggt (siehe `quelle.py`). Das Repository
ist öffentlich, die Logs der GitHub Actions auch.

## Herkunft

Aufbau und Archiv-Logik folgen `alekspaunovic/handball-kalender`, die Regeln
für Streichungen und den Schutz vor fehlerhaften Abrufen stehen in SPEC.md
Abschnitt 9.
