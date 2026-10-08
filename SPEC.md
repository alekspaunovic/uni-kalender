# Uni-Kalender CBS

Spezifikation für ein Skript, das den Vorlesungs-Export der CBS in ein
eigenes ICS-Format umschreibt, dauerhaft archiviert und über GitHub Pages
veröffentlicht.

## 1. Zweck

Die Hochschule stellt einen ICS-Export bereit (Simovative). Zwei Probleme:

- Vergangene Veranstaltungen verschwinden aus dem Feed und damit aus dem
  Kalender. Es lässt sich hinterher nicht mehr nachvollziehen, was wann war.
- Die Titel sind unlesbar lang und enthalten Gruppe, Studiengang und Semester,
  während der entscheidende Unterschied (Online, Selbststudium oder Präsenz)
  am Ende versteckt steht. Der Raum taucht im Titel gar nicht auf.

Das Skript liest den Quell-Feed, schreibt die Termine in ein festes
Wunschformat um, führt ein dauerhaftes Archiv und veröffentlicht einen
einzelnen ICS-Feed zum Abonnieren.

Eigenes Repository, getrennt vom Handball-Projekt: `uni-kalender`.

## 2. Quelle

Ein einzelner ICS-Abo-Link der Hochschule, Anbieter Simovative.

Der Link ist personalisiert und gehört in ein GitHub Secret namens
`UNI_ICS_URL`, lokal in die `.env`. Er darf an keiner Stelle ins Repository.

### Eigenschaften des Quellformats

```
X-WR-CALNAME:Your-Campus-Events
PRODID:-//Events//EN
UID:209435@simovative.com
```

- UIDs sind stabil und numerisch, Form `<zahl>@simovative.com`
- VTIMEZONE für Europe/Berlin ist korrekt eingebettet
- `DTSTAMP;TZID=Europe/Berlin:...` ist nicht standardkonform, DTSTAMP müsste
  UTC sein. Der Parser muss damit umgehen können
- DESCRIPTION ist identisch zur SUMMARY und wird verworfen
- LOCATION ist nur bei Präsenzterminen gefüllt, sonst leer. Kommas zwischen
  zwei Räumen sind nicht maskiert (`\,` wäre korrekt)
- Zeilen sind nach ICS-Regeln gefaltet, teils mitten im Wort
- Nach jeder DESCRIPTION folgt ein einzelnes LF und eine Zeile `\n ` ohne
  Eigenschaftsnamen. Der Parser (icalendar) übergeht sie und vermerkt sie nur
  als Fehler, alle Termine kommen trotzdem an

## 3. Ausgabe

Ein einziger Feed: `docs/uni.ics`

```
X-WR-CALNAME:Uni
X-WR-TIMEZONE:Europe/Berlin
X-PUBLISHED-TTL:PT6H
REFRESH-INTERVAL;VALUE=DURATION:PT6H
```

Keine VALARM-Komponenten, keine Erinnerungen.

## 4. Veranstaltungstypen

Der Typ steht am Ende der SUMMARY, in der Form `<Kürzel> (<Langform>)`.

| Kürzel | Langform | Bedeutung |
| --- | --- | --- |
| LLO | Live Learning Online | Online-Vorlesung |
| GSS | Guided Self-Studies | betreutes Selbststudium |
| LLC | Live Learning on Campus | Präsenz, mit Raum |
| Prüfungstermin | LV | Klausur |

Die Erkennung erfolgt über den Schlussteil der SUMMARY, nicht über eine feste
Liste, damit neue Typen nicht verlorengehen. Ein unbekanntes Kürzel wird
übernommen und geloggt. Kürzel ist das letzte Wort vor der Klammer:
`... 25W LLO/GSS Gr. 2 GSS (Guided Self-Studies)` ist `GSS`, die Klausur steht
in der Quelle als `... 25W  Prüfungstermin (LV)`.

## 5. Titel

Format: `<Kürzel>-<Modulname>`

```
LLO-Wirtschaftsenglisch 3
GSS-Projektmanagement
LLC-Anwendungssysteme & Informationsmanagement
Prüfungstermin-Wirtschaftsenglisch 3
```

Der Modulname wird vollständig ausgeschrieben übernommen, nicht gekürzt.

Bei Streichung wird `ABGESAGT ` vorangestellt:
`ABGESAGT LLC-Projektmanagement`

### Modulnamen ermitteln

Die SUMMARY hat die Form:

```
<Modulname> [Gr. <n> [<Buchstabe>]] [<Studiengang>] <Semester> [Zusätze] <Kürzel> (<Langform>)
```

Beispiele aus den echten Daten:

| SUMMARY | Modulname |
| --- | --- |
| `Wirtschaftsenglisch 3 Gr. 04 F GM+WI+WING 25W  LLO (Live Learning Online)` | Wirtschaftsenglisch 3 |
| `Management der Wertschöpfungskette Gr. 2 GM+WI+WING 25W LLO/GSS Gr. 2 GSS (Guided Self-Studies)` | Management der Wertschöpfungskette |
| `Anwendungssysteme & Informationsmanagement WI 25W Solingen LLC (Live Learning on Campus)` | Anwendungssysteme & Informationsmanagement |
| `DS+SoE: Datenqualitätsmanagement WI 25W  GSS (Guided Self-Studies)` | DS+SoE: Datenqualitätsmanagement |
| `Infoveranstaltung Fallstudie 25W  LLO (Live Learning Online)` | Infoveranstaltung Fallstudie |
| `Projektmanagement Gr. 2 GM+WI+WING 25W Solingen WI+WING LLC (Live Learning on Campus)` | Projektmanagement |

Vorgehen:

1. Das Semester-Token suchen, Muster `\b\d{2}[WS]\b`, also `25W`, `26S`. Alles
   ab dort wird verworfen.
2. Im verbleibenden Vorspann nach ` Gr. ` gefolgt von einer Ziffer suchen. Bei
   Treffer dort abschneiden.
3. Ist kein ` Gr. ` vorhanden, am Ende des Vorspanns einen Studiengangs-Block
   entfernen. Das sind Tokens aus einer konfigurierbaren Liste, auch mit Plus
   verbunden wie `GM+WI+WING`. Entfernt wird nur am Ende, nie am Anfang und
   nie das einzige Wort, sonst fällt das Präfix `DS+SoE:` dem Verfahren zum
   Opfer. In der Liste stehen nur Codes, die in der Quelle vorkommen, bisher
   GM, WI und WING. Ein vorsorglicher Eintrag wie `BWL` würde ein Modul
   `Einführung in die BWL` ohne Gruppe um sein letztes Wort kürzen.
4. Mehrfache Leerzeichen zusammenfassen, Rand trimmen.

Fehlt das Semester-Token, wird stattdessen der Typ am Ende abgeschnitten und
der Rest wie ein Vorspann behandelt. Das Skript loggt eine Warnung.

Greift das Verfahren bei einem Modul daneben, hilft eine Override-Tabelle in
`config.yaml`, die vor allen Regeln geprüft wird. Schlüssel ist ein Teilstring
der SUMMARY, Wert der gewünschte Modulname.

Das Skript loggt bei jedem Lauf die erkannten Modulnamen, damit Fehlgriffe
auffallen.

## 6. Zeiten

Start und Ende werden unverändert übernommen, inklusive
`TZID=Europe/Berlin`. Die Quelle liefert plausible Dauern zwischen 90 Minuten
und fünf Stunden, es wird nichts gerechnet.

## 7. Ort

Die Quelle liefert bei Präsenzterminen Werte wie:

```
SOL P.2.04 Shanghai [18]
SOL P.2.03 Kuala Lumpur [16], SOL P.2.04 Shanghai [18]
```

Diese werden unverändert ins LOCATION-Feld übernommen, inklusive der Zahl in
eckigen Klammern und inklusive beider Räume, wenn zwei genannt sind.

Keine Campus-Adresse, keine Koordinaten, keine Navigation.

Ist LOCATION leer, bleibt das Feld leer.

## 8. Notiz

Die vollständige Original-SUMMARY, damit Gruppe, Studiengang und Semester bei
Bedarf nachlesbar bleiben:

```
Wirtschaftsenglisch 3 Gr. 04 F GM+WI+WING 25W  LLO (Live Learning Online)
```

Die DESCRIPTION der Quelle wird verworfen, sie ist ohnehin identisch zur
SUMMARY.

## 9. Archiv und Streichungen

Termine sollen dauerhaft erhalten bleiben, auch wenn die Quelle sie nicht mehr
ausliefert. Dafür führt das Skript `data/archive.json`, das bei jedem Lauf
ergänzt und ins Repository zurückcommittet wird.

Der Feed wird immer vollständig aus dem Archiv erzeugt, nie direkt aus der
Quelle. Die Quelle aktualisiert nur das Archiv.

### Verschiebung

Eine bekannte UID mit geänderter Zeit oder geändertem Ort ist eine
Verschiebung. Der Archiveintrag wird aktualisiert, die UID bleibt stabil,
damit der Kalender den Termin verschiebt statt einen zweiten anzulegen. Kein
ABGESAGT-Präfix.

Da Simovative stabile UIDs vergibt, ist das zuverlässig erkennbar.

### Streichung

Eine UID, die im Archiv steht und nicht mehr in der Quelle vorkommt, bevor
ihr Termin begonnen hat, ist eine Streichung. Der Termin bekommt das
ABGESAGT-Präfix, bleibt aber im Feed stehen, auch nachdem sein Datum vorbei
ist.

Verschwindet ein Termin erst nach seinem Beginn, ist er nicht gestrichen,
sondern aus dem Zeitfenster der Quelle gefallen (Abschnitt 1: vergangene
Veranstaltungen verschwinden aus dem Export). Er bleibt unverändert stehen.
Ohne diese Ausnahme würde jede Vorlesung kurz nach dem Termin als abgesagt
erscheinen -- derselbe Fehler trat im Handball-Kalender auf.

Taucht die UID später wieder auf, wird das Präfix entfernt.

Meldet die Quelle eine Absage ausdrücklich (`STATUS:CANCELLED`), gilt sie
ebenso. Bisher streicht Simovative nur durch Weglassen.

Ein einzelner Quell-Termin, der sich nicht lesen lässt, wird übersprungen und
geloggt. Sein Archiveintrag bleibt unverändert und gilt nicht als gestrichen.

### Schutz gegen fehlerhafte Abrufe

Ohne Absicherung würde eine einzelne gestörte Antwort das halbe Semester auf
abgesagt setzen. Deshalb bricht der Lauf ab und lässt das Archiv unverändert,
wenn eine dieser Bedingungen zutrifft:

- Der Abruf schlägt fehl oder liefert kein gültiges VCALENDAR (auch eine
  leere Antwort oder eine HTML-Seite)
- Der Lauf würde auf einen Schlag mehr als die Hälfte der bekannten
  **künftigen** Termine streichen, und zwar mindestens drei. Ein Feed mit
  null Terminen fällt darunter, sobald künftige Termine bekannt sind

Verglichen wird bewusst nicht mit der Gesamtzahl des letzten Laufs: die
schrumpft von selbst, weil vergangene Termine aus der Quelle fallen, und geht
zum Semesterende gegen null. Der Lauf würde sich dann selbst blockieren. Die
Mindestanzahl sorgt dafür, dass zum Semesterende die Streichung der letzten
ein, zwei Termine nicht als Störung gilt.

Im Abbruchfall wird der bestehende Feed unverändert aus dem Archiv neu
geschrieben. Ein gescheiterter Abruf beendet den Lauf mit Exit-Code 1, der
Workflow wird rot und GitHub schickt eine Mail -- so fällt ein abgelaufener
Abo-Link auf. Der Schutz vor zu vielen Streichungen loggt nur eine Warnung.
Anteil und Mindestanzahl sind in `config.yaml` einstellbar (`schutz_anteil`,
`schutz_mindestanzahl`).

### UIDs

Feste Form `cbs-<zahl>`, abgeleitet aus der Quell-UID. Aus
`209435@simovative.com` wird `cbs-209435`. Sie ändern sich nie.

### Archiv-Eintrag

```json
{
  "uid": "cbs-209435",
  "source_uid": "209435@simovative.com",
  "summary": "LLC-Anwendungssysteme & Informationsmanagement",
  "module": "Anwendungssysteme & Informationsmanagement",
  "type": "LLC",
  "dtstart": "2026-10-08T12:45:00+02:00",
  "dtend": "2026-10-08T17:45:00+02:00",
  "location": "SOL P.2.04 Shanghai [18]",
  "description": "Anwendungssysteme & Informationsmanagement WI 25W Solingen LLC (Live Learning on Campus)",
  "cancelled": false,
  "first_seen": "2026-10-07T14:00:00Z",
  "last_seen": "2026-10-07T14:00:00Z"
}
```

## 10. Technik

- Python 3.12, Abhängigkeiten `icalendar`, `requests`, `pyyaml`
- Konfiguration in `config.yaml`: Studiengangs-Codes, Modul-Overrides,
  Plausibilitätsschwelle
- Quell-URL aus dem GitHub Secret `UNI_ICS_URL`, lokal aus `.env` (das
  Skript liest sie selbst ein, eine gesetzte Umgebungsvariable gewinnt)
- Die Quell-URL erscheint nie im Log. Fehlermeldungen von `requests` enthalten
  sie, deshalb werden sie nur mit Fehlerart und HTTP-Status geloggt -- das
  Repository und damit die Logs der Actions sind öffentlich
- `.gitignore` enthält `.env`, bevor irgendetwas hochgeladen wird
- GitHub Actions (`.github/workflows/feed.yml`), Cron alle 6 Stunden plus
  `workflow_dispatch`
- Ausgabe nach `docs/`, Veröffentlichung über GitHub Pages
- Der Workflow committet `docs/uni.ics` und `data/archive.json` zurück und
  braucht dafür Schreibrechte
- `docs/.nojekyll` anlegen
- Zeitzone durchgehend Europe/Berlin, VTIMEZONE korrekt einbetten
- Lokaler Lauf ohne Secret: `python -m uni_kalender.main --local` liest
  `fixtures/campus-events.ics`

## 11. Tests

Die hochgeladene Beispieldatei dient als Fixture unter
`fixtures/campus-events.ics` (Export vom 07.10.2026, 58 Termine, unverändert
inklusive aller Formatfehler). Abzudecken:

- Typ-Erkennung für LLO, GSS, LLC und Prüfungstermin
- Modulname für alle sechs Module aus der Tabelle in Abschnitt 5, besonders
  `DS+SoE: Datenqualitätsmanagement` mit Plus-Präfix und
  `Infoveranstaltung Fallstudie` ohne Studiengang
- Titel entspricht exakt `<Kürzel>-<Modulname>`
- Raum mit zwei Einträgen bleibt vollständig und unverändert erhalten
- Leeres LOCATION führt zu leerem Ortsfeld
- Notiz enthält die vollständige Original-SUMMARY
- Verschiebung: gleiche UID mit neuem DTSTART aktualisiert den Eintrag ohne
  ABGESAGT-Präfix
- Streichung: verschwundene künftige UID bekommt ABGESAGT, Eintrag bleibt
  im Feed
- Verschwundener vergangener Termin bleibt unverändert
- Wiederauftauchen entfernt das Präfix wieder
- Leerer Feed bricht den Lauf ab, Archiv bleibt unverändert
- Fehlt mehr als die Hälfte der künftigen Termine, bricht der Lauf ebenfalls
  ab. Fallen nur vergangene Termine heraus, läuft er durch
- Gescheiterter Abruf: Exit-Code 1, Archiv unverändert, der Abo-Link steht
  in keiner Log-Zeile
- Nicht standardkonformes `DTSTAMP;TZID=...` wird korrekt verarbeitet

## 12. Offene Punkte

- Liste der Studiengangs-Codes ergänzen, sobald neue in der Quelle auftauchen
  (das Log zeigt bei jedem Lauf die erkannten Modulnamen)
- Verhalten beim Semesterwechsel beobachten, wenn erstmals `26S` auftaucht
- Wie lange vergangene Termine in der Quelle bleiben: Der Export vom
  07.10.2026 reicht vier Wochen zurück (bis 09.09.2026)
