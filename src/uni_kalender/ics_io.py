"""Den Feed docs/uni.ics aus dem Archiv schreiben (SPEC.md Abschnitt 3)."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone as dt_timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event, Timezone

_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def parse_duration(value: str) -> timedelta:
    match = _DURATION_RE.match(value)
    if not match:
        raise ValueError(f"Unbekanntes Dauer-Format: {value!r}")
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


def _zeit(value: str, tz: ZoneInfo) -> datetime | date:
    if len(value) == 10:
        return date.fromisoformat(value)
    # Das Archiv kennt nur den UTC-Offset, nicht den Zonennamen. Auf die
    # benannte Zone umrechnen, damit TZID=Europe/Berlin im Feed steht.
    return datetime.fromisoformat(value).astimezone(tz)


def build_calendar(entries: list[dict], calname: str, tz_name: str, ttl: str) -> Calendar:
    tz = ZoneInfo(tz_name)
    cal = Calendar()
    cal.add("prodid", "-//alekspaunovic//Uni-Kalender//DE")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("x-wr-calname", calname)
    cal.add("x-wr-timezone", tz_name)
    cal.add("x-published-ttl", ttl)
    cal.add("refresh-interval", parse_duration(ttl), parameters={"VALUE": "DURATION"})
    cal.add_component(Timezone.from_tzid(tz_name))

    now = datetime.now(dt_timezone.utc)
    for entry in sorted(entries, key=lambda e: (e["dtstart"], e["uid"])):
        event = Event()
        event.add("uid", entry["uid"])
        event.add("dtstamp", now)
        event.add("dtstart", _zeit(entry["dtstart"], tz))
        event.add("dtend", _zeit(entry["dtend"], tz))
        event.add("summary", entry["summary"])
        if entry.get("location"):
            event.add("location", entry["location"])
        if entry.get("description"):
            event.add("description", entry["description"])
        # Bewusst keine VALARM-Komponenten (SPEC.md Abschnitt 3).
        cal.add_component(event)
    return cal


def write_feed(path: str | Path, entries: list[dict], calname: str, tz_name: str, ttl: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_calendar(entries, calname, tz_name, ttl).to_ical())
