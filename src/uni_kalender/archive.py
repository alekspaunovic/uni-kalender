"""Archiv laden, mergen, speichern (SPEC.md Abschnitt 9)."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from .transform import ABGESAGT


def _beginn(entry: dict) -> datetime | date:
    value = entry["dtstart"]
    if len(value) == 10:
        return date.fromisoformat(value)
    return datetime.fromisoformat(value)


def hat_begonnen(entry: dict, now: datetime) -> bool:
    beginn = _beginn(entry)
    if isinstance(beginn, datetime):
        return beginn <= now
    return beginn <= now.date()


def streichungen(existing: list[dict], seen_uids: set[str], now: datetime, protect: set[str] = frozenset()) -> list[dict]:
    """Archiveinträge, die dieser Lauf streichen würde: nicht mehr in der
    Quelle, noch nicht abgesagt und noch nicht begonnen.

    Was erst nach seinem Beginn aus der Quelle verschwindet, ist nicht
    gestrichen, sondern aus ihrem Zeitfenster gefallen -- die Hochschule
    nimmt vergangene Veranstaltungen nach einer Weile aus dem Export. Es
    bleibt unverändert stehen.
    """
    return [
        entry
        for entry in existing
        if entry["uid"] not in seen_uids
        and entry["uid"] not in protect
        and not entry["cancelled"]
        and not hat_begonnen(entry, now)
    ]


def pruefe_schutz(
    existing: list[dict],
    seen_uids: set[str],
    now: datetime,
    anteil: float,
    mindestanzahl: int,
    protect: set[str] = frozenset(),
) -> str | None:
    """Gibt einen Abbruchgrund zurück, wenn der Lauf auf einen Schlag zu viele
    künftige Termine streichen würde -- typisch für eine gestörte Antwort der
    Quelle. Sonst None.

    Verglichen wird mit den künftigen Terminen, nicht mit der Gesamtzahl: die
    schrumpft von selbst, weil vergangene Termine aus der Quelle fallen, und
    würde den Lauf zum Semesterende dauerhaft blockieren.
    """
    kuenftige = [e for e in existing if not e["cancelled"] and not hat_begonnen(e, now)]
    gestrichen = streichungen(existing, seen_uids, now, protect)
    if len(gestrichen) >= mindestanzahl and len(gestrichen) > anteil * len(kuenftige):
        return (
            f"{len(gestrichen)} von {len(kuenftige)} künftigen Terminen fehlen "
            f"in der Quelle (Schwelle {anteil:.0%})"
        )
    return None


def merge(
    existing: list[dict],
    new_entries: list[dict],
    now: datetime,
    protect: set[str] = frozenset(),
) -> list[dict]:
    """Bekannte UIDs werden aktualisiert -- auch Zeit und Ort, das ist eine
    Verschiebung, die UID bleibt stabil. Neue UIDs werden ergänzt. Fehlt ein
    künftiger Termin in der Quelle, ist er gestrichen und bekommt das
    ABGESAGT-Präfix, bleibt aber im Feed. Taucht er wieder auf, gilt wieder
    die Quelle und das Präfix ist weg.

    `protect` nimmt UIDs aus, über die dieser Lauf nichts weiß, weil ihr
    Quell-Termin nicht gelesen werden konnte.
    """
    now_iso = now.isoformat()
    by_uid = {entry["uid"]: dict(entry) for entry in existing}
    seen_uids: set[str] = set()

    for neu in new_entries:
        seen_uids.add(neu["uid"])
        entry = by_uid.get(neu["uid"])
        if entry is None:
            entry = {**neu, "first_seen": now_iso}
            by_uid[neu["uid"]] = entry
        else:
            entry.update(neu)
        entry["last_seen"] = now_iso

    for entry in streichungen(list(by_uid.values()), seen_uids, now, protect):
        entry["cancelled"] = True
        if not entry["summary"].startswith(ABGESAGT):
            entry["summary"] = f"{ABGESAGT}{entry['summary']}"

    return sorted(by_uid.values(), key=lambda e: (e["dtstart"], e["uid"]))


def load(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: str | Path, entries: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
