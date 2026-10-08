"""Abruf und Parsen des Quell-Feeds (SPEC.md Abschnitt 2 und 9).

Der Abo-Link ist geheim (CLAUDE.md). Ausnahmen von `requests` tragen ihn in
ihrer Meldung ("... for url: https://..."), deshalb verlässt keine davon
dieses Modul: jeder Fehler wird zu einem `QuellFehler`, dessen Meldung nur
Fehlerart und HTTP-Status enthält.
"""

from __future__ import annotations

import requests
from icalendar import Calendar


class QuellFehler(Exception):
    """Abruf gescheitert oder kein gültiges VCALENDAR. Die Meldung enthält nie
    den Abo-Link."""


def fetch(url: str, timeout: float = 30.0) -> bytes:
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException as fehler:
        raise QuellFehler(f"Abruf fehlgeschlagen ({type(fehler).__name__})") from None
    if not response.ok:
        raise QuellFehler(f"Abruf fehlgeschlagen (HTTP {response.status_code})")
    return response.content


def parse(raw: bytes) -> Calendar:
    """Parst den Export. Die Quelle ist nicht standardkonform -- DTSTAMP mit
    TZID, unmaskierte Kommas in LOCATION, nach jeder DESCRIPTION eine Zeile
    "\\n" ohne Eigenschaftsnamen. icalendar übergeht die kaputte Zeile und
    vermerkt sie nur in `errors`; alles andere liest es korrekt."""
    if not raw or not raw.strip():
        raise QuellFehler("Antwort ist leer")
    try:
        cal = Calendar.from_ical(raw)
    except (ValueError, IndexError, KeyError) as fehler:
        raise QuellFehler(f"Kein gültiges VCALENDAR ({type(fehler).__name__})") from None
    if getattr(cal, "name", None) != "VCALENDAR":
        raise QuellFehler("Kein gültiges VCALENDAR")
    return cal
