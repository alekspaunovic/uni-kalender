"""Ablauf eines Laufs: Quelle lesen -> umschreiben -> Schutz prüfen ->
Archiv mergen -> Feed schreiben (SPEC.md Abschnitte 9 und 10)."""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

from . import archive, ics_io, quelle, transform
from .config import Config, load_config, load_env_file

logger = logging.getLogger(__name__)


def _lade_quelle(config: Config, lokale_datei: Path | None) -> bytes:
    if lokale_datei is not None:
        try:
            return lokale_datei.read_bytes()
        except OSError as fehler:
            raise quelle.QuellFehler(f"Lokale Datei nicht lesbar ({type(fehler).__name__})") from None
    url = config.source_url()
    if not url:
        raise quelle.QuellFehler(f"Kein Abo-Link gesetzt (Umgebungsvariable {config.source_env})")
    return quelle.fetch(url)


def _logge_module(entries: list[dict]) -> None:
    """SPEC.md Abschnitt 5: die erkannten Modulnamen bei jedem Lauf zeigen,
    damit Fehlgriffe der Regeln auffallen."""
    zaehler = Counter(transform.titel(e["type"], e["module"]) for e in entries)
    logger.info("Erkannte Module (%d Termine):", len(entries))
    for name, anzahl in sorted(zaehler.items()):
        logger.info("  %s (%d)", name, anzahl)


def _logge_aenderungen(existing: list[dict], merged: list[dict]) -> None:
    vorher = {e["uid"]: e for e in existing}
    for entry in merged:
        alt = vorher.get(entry["uid"])
        if alt is None:
            continue
        if entry["cancelled"] and not alt["cancelled"]:
            logger.info("Gestrichen: %s am %s", entry["summary"], entry["dtstart"])
        elif alt["cancelled"] and not entry["cancelled"]:
            logger.info("Wieder da: %s am %s", entry["summary"], entry["dtstart"])
        elif (alt["dtstart"], alt["dtend"], alt["location"]) != (entry["dtstart"], entry["dtend"], entry["location"]):
            logger.info("Verschoben: %s, jetzt %s", entry["summary"], entry["dtstart"])
    neu = len([e for e in merged if e["uid"] not in vorher])
    if neu:
        logger.info("Neu im Archiv: %d Termine", neu)


def run(config: Config, now: datetime, lokale_datei: Path | None = None) -> int:
    """Gibt den Exit-Code zurück: 1, wenn die Quelle nicht lesbar war (der
    Workflow wird rot und GitHub schickt eine Mail), sonst 0 -- auch beim
    Abbruch durch den Schutz, der ist nur eine Warnung."""
    existing = archive.load(config.archive_path)

    def feed_schreiben(entries: list[dict]) -> None:
        ics_io.write_feed(config.output_path, entries, config.calname, config.timezone, config.feed_ttl)

    try:
        cal = quelle.parse(_lade_quelle(config, lokale_datei))
    except quelle.QuellFehler as fehler:
        logger.error("%s. Archiv bleibt unverändert, Feed wird aus dem Archiv neu geschrieben.", fehler)
        feed_schreiben(existing)
        return 1

    neue: list[dict] = []
    # UIDs, deren Quell-Termin nicht lesbar war: über sie weiß dieser Lauf
    # nichts, also dürfen sie auch nicht als gestrichen gelten.
    protect: set[str] = set()
    for vevent in cal.walk("VEVENT"):
        try:
            neue.append(transform.transform(vevent, config))
        except Exception:
            source_uid = str(vevent.get("UID", ""))
            logger.exception("Termin %r nicht lesbar, Archiveintrag bleibt unverändert", source_uid)
            if source_uid:
                protect.add(transform.uid_aus_quelle(source_uid, config.uid_prefix))

    _logge_module(neue)

    seen_uids = {entry["uid"] for entry in neue}
    grund = archive.pruefe_schutz(
        existing, seen_uids, now, config.schutz_anteil, config.schutz_mindestanzahl, protect
    )
    if grund:
        logger.warning("Lauf abgebrochen: %s. Archiv bleibt unverändert.", grund)
        feed_schreiben(existing)
        return 0

    merged = archive.merge(existing, neue, now, protect)
    _logge_aenderungen(existing, merged)
    archive.save(config.archive_path, merged)
    feed_schreiben(merged)
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Uni-Kalender-Feed erzeugen")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument(
        "--local",
        metavar="ICS_DATEI",
        nargs="?",
        const="fixtures/campus-events.ics",
        default=None,
        help="liest eine lokale ICS-Datei statt des Abo-Links (kein Secret nötig)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_env_file(".env")
    config = load_config(args.config)
    lokale_datei = Path(args.local) if args.local else None
    sys.exit(run(config, datetime.now(dt_timezone.utc), lokale_datei))


if __name__ == "__main__":
    main()
