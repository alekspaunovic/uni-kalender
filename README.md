# uni-kalender

Schreibt den Vorlesungs-Export der CBS in einen lesbaren Kalender um, hebt
jeden Termin dauerhaft auf und veröffentlicht ihn als ICS-Feed über GitHub
Pages. Details in [SPEC.md](SPEC.md).

**Abo-Link:** `https://alekspaunovic.github.io/uni-kalender/uni.ics`

Titel im Kalender: `LLO-Wirtschaftsenglisch 3`, `LLC-Projektmanagement`,
`Prüfungstermin-Wirtschaftsenglisch 3`. Raum steht im Ort, die vollständige
Original-Bezeichnung in der Notiz.

## Einrichtung

1. Secret anlegen: Settings → Secrets and variables → Actions → New
   repository secret, Name `UNI_ICS_URL`, Wert = Abo-Link der Hochschule.
2. GitHub Pages einschalten: Settings → Pages → Source „Deploy from a
   branch“, Branch `main`, Ordner `/docs`.
3. Workflow einmal von Hand starten: Actions → „Feed aktualisieren“ → Run
   workflow. Danach läuft er alle sechs Stunden von selbst.

## Lokal

```sh
pip install -e ".[dev]"
pytest
python -m uni_kalender.main --local   # liest fixtures/campus-events.ics
```

Für einen Lauf gegen die echte Quelle den Abo-Link als `UNI_ICS_URL=...` in
eine `.env` schreiben (steht in `.gitignore`).
