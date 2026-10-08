"""Quell-Termin in einen Archiveintrag umschreiben (SPEC.md Abschnitte 4-8)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .config import Config

logger = logging.getLogger(__name__)

ABGESAGT = "ABGESAGT "

# "<Kürzel> (<Langform>)" am Ende der SUMMARY, etwa "LLO (Live Learning
# Online)" oder "Prüfungstermin (LV)".
_TYP_RE = re.compile(r"(\S+)\s*\(([^()]*)\)\s*$")
# Semester-Token wie 25W oder 26S.
_SEMESTER_RE = re.compile(r"\b\d{2}[WS]\b")
# " Gr. " gefolgt von einer Ziffer, etwa "Gr. 04 F" oder "Gr. 2".
_GRUPPE_RE = re.compile(r" Gr\. \d")
_SOURCE_UID_RE = re.compile(r"^(\d+)@simovative\.com$")


@dataclass(frozen=True)
class Zerlegung:
    typ: str | None
    langform: str | None
    modul: str


def _whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def erkenne_typ(summary: str) -> tuple[str | None, str | None]:
    match = _TYP_RE.search(summary)
    if not match:
        return None, None
    return match.group(1), _whitespace(match.group(2))


def _ohne_studiengang(vorspann: str, studiengaenge: set[str]) -> str:
    """Entfernt einen Studiengangs-Block am Ende, etwa "WI" oder "GM+WI+WING".
    Nur am Ende und nie das erste Wort -- "DS+SoE:" am Anfang bleibt stehen."""
    woerter = vorspann.split()
    if len(woerter) < 2:
        return vorspann
    letztes = woerter[-1]
    if all(teil in studiengaenge for teil in letztes.split("+")):
        return " ".join(woerter[:-1])
    return vorspann


def ermittle_modul(summary: str, config: Config) -> str:
    """Modulname nach SPEC.md Abschnitt 5."""
    for teilstring, modul in config.modul_overrides.items():
        if teilstring in summary:
            return modul

    semester = _SEMESTER_RE.search(summary)
    if semester:
        vorspann = summary[: semester.start()]
    else:
        # Ohne Semester-Token fehlt der Anker. Dann wenigstens den Typ am Ende
        # abschneiden und den Rest wie einen Vorspann behandeln.
        logger.warning("Kein Semester-Token in %r, Modulname ist unsicher", summary)
        typ_match = _TYP_RE.search(summary)
        vorspann = summary[: typ_match.start()] if typ_match else summary

    gruppe = _GRUPPE_RE.search(vorspann)
    if gruppe:
        vorspann = vorspann[: gruppe.start()]
    else:
        vorspann = _ohne_studiengang(_whitespace(vorspann), set(config.studiengaenge))

    modul = _whitespace(vorspann)
    if not modul:
        logger.warning("Kein Modulname aus %r ermittelbar, nehme die SUMMARY", summary)
        return _whitespace(summary)
    return modul


def zerlege(summary: str, config: Config) -> Zerlegung:
    typ, langform = erkenne_typ(summary)
    if typ is None:
        logger.warning("Kein Veranstaltungstyp am Ende von %r", summary)
    elif typ not in config.typen:
        logger.warning("Unbekannter Veranstaltungstyp %r (%s), wird übernommen", typ, langform)
    return Zerlegung(typ=typ, langform=langform, modul=ermittle_modul(summary, config))


def titel(typ: str | None, modul: str, cancelled: bool = False) -> str:
    """`<Kürzel>-<Modulname>`, bei Streichung mit ABGESAGT-Präfix."""
    text = f"{typ}-{modul}" if typ else modul
    return f"{ABGESAGT}{text}" if cancelled else text


def uid_aus_quelle(source_uid: str, uid_prefix: str) -> str:
    """Aus 209435@simovative.com wird cbs-209435."""
    match = _SOURCE_UID_RE.match(source_uid)
    if match:
        return f"{uid_prefix}-{match.group(1)}"
    logger.warning("Unerwartete Quell-UID %r", source_uid)
    return f"{uid_prefix}-" + re.sub(r"[^A-Za-z0-9]+", "-", source_uid).strip("-")


def _zeit(value: datetime | date, tz_name: str) -> str:
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo(tz_name))
    return value.isoformat()


def transform(vevent, config: Config) -> dict:
    """Ein VEVENT der Quelle als Archiveintrag (ohne first_seen/last_seen)."""
    source_uid = str(vevent["UID"])
    summary = str(vevent.get("SUMMARY", ""))
    teile = zerlege(summary, config)
    # Die Quelle streicht bisher durch Weglassen. Meldet sie eine Absage doch
    # einmal ausdrücklich, gilt sie ebenso.
    cancelled = str(vevent.get("STATUS", "")).upper() == "CANCELLED"

    return {
        "uid": uid_aus_quelle(source_uid, config.uid_prefix),
        "source_uid": source_uid,
        "summary": titel(teile.typ, teile.modul, cancelled),
        "module": teile.modul,
        "type": teile.typ,
        "dtstart": _zeit(vevent["DTSTART"].dt, config.timezone),
        "dtend": _zeit(vevent["DTEND"].dt, config.timezone),
        # Unverändert, auch mit zwei Räumen und der Zahl in Klammern.
        "location": str(vevent.get("LOCATION", "")).strip(),
        # Die Original-SUMMARY als Notiz. Die DESCRIPTION der Quelle ist
        # identisch und wird verworfen.
        "description": summary,
        "cancelled": cancelled,
    }
