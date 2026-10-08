import dataclasses
import json
import logging
import os
from datetime import timedelta

import requests
from icalendar import Calendar

from uni_kalender import main
from uni_kalender.config import load_env_file
from conftest import EXPORT, FIXTURE


def _config(config, tmp_path):
    return dataclasses.replace(
        config,
        output_path=str(tmp_path / "docs" / "uni.ics"),
        archive_path=str(tmp_path / "data" / "archive.json"),
    )


def _feed(config):
    with open(config.output_path, "rb") as f:
        return Calendar.from_ical(f.read())


def _ohne(tmp_path, source_uids):
    """Die Fixture ohne die genannten Termine."""
    raw = FIXTURE.read_bytes()
    teile = raw.split(b"BEGIN:VEVENT")
    behalten = [teile[0]] + [t for t in teile[1:] if not any(uid.encode() in t for uid in source_uids)]
    pfad = tmp_path / "quelle.ics"
    pfad.write_bytes(b"BEGIN:VEVENT".join(behalten))
    return pfad


def test_lauf_mit_fixture_schreibt_feed_und_archiv(config, tmp_path):
    config = _config(config, tmp_path)
    assert main.run(config, EXPORT, FIXTURE) == 0

    archiv = json.loads((tmp_path / "data" / "archive.json").read_text(encoding="utf-8"))
    assert len(archiv) == 58
    eintrag = next(e for e in archiv if e["uid"] == "cbs-209435")
    assert eintrag["summary"] == "LLC-Anwendungssysteme & Informationsmanagement"
    assert eintrag["module"] == "Anwendungssysteme & Informationsmanagement"
    assert eintrag["type"] == "LLC"

    feed = _feed(config)
    assert str(feed["X-WR-CALNAME"]) == "Uni"
    assert str(feed["X-WR-TIMEZONE"]) == "Europe/Berlin"
    assert str(feed["X-PUBLISHED-TTL"]) == "PT6H"
    assert "REFRESH-INTERVAL" in feed
    assert len(feed.walk("VTIMEZONE")) == 1
    assert feed.walk("VALARM") == []
    assert len(feed.walk("VEVENT")) == 58


def test_feed_zwei_raeume_leerer_ort_notiz_und_zeitzone(config, tmp_path):
    config = _config(config, tmp_path)
    main.run(config, EXPORT, FIXTURE)
    events = {str(e["UID"]): e for e in _feed(config).walk("VEVENT")}

    assert str(events["cbs-209437"]["LOCATION"]) == "SOL P.2.03 Kuala Lumpur [16], SOL P.2.04 Shanghai [18]"
    assert "LOCATION" not in events["cbs-207875"]
    assert str(events["cbs-207875"]["DESCRIPTION"]) == (
        "Wirtschaftsenglisch 3 Gr. 04 F GM+WI+WING 25W  LLO (Live Learning Online)"
    )
    assert events["cbs-209435"]["DTSTART"].params["TZID"] == "Europe/Berlin"
    assert events["cbs-209435"]["DTSTART"].dt.isoformat() == "2026-10-08T12:45:00+02:00"

    raw = open(config.output_path, "rb").read()
    assert b"DTSTART;TZID=Europe/Berlin:20261008T124500" in raw


def test_streichung_landet_im_feed(config, tmp_path):
    config = _config(config, tmp_path)
    main.run(config, EXPORT, FIXTURE)
    # Ein künftiger Termin (08.10.) fehlt, ein vergangener (09.09.) auch.
    quelle_neu = _ohne(tmp_path, ["209435@simovative.com", "207875@simovative.com"])
    assert main.run(config, EXPORT + timedelta(hours=6), quelle_neu) == 0

    events = {str(e["UID"]): e for e in _feed(config).walk("VEVENT")}
    assert len(events) == 58
    assert str(events["cbs-209435"]["SUMMARY"]) == "ABGESAGT LLC-Anwendungssysteme & Informationsmanagement"
    assert str(events["cbs-207875"]["SUMMARY"]) == "LLO-Wirtschaftsenglisch 3"

    # Taucht er wieder auf, ist das Präfix weg.
    main.run(config, EXPORT + timedelta(hours=12), FIXTURE)
    events = {str(e["UID"]): e for e in _feed(config).walk("VEVENT")}
    assert str(events["cbs-209435"]["SUMMARY"]) == "LLC-Anwendungssysteme & Informationsmanagement"


def _archiv_und_feed(config):
    return (
        open(config.archive_path, encoding="utf-8").read(),
        len(_feed(config).walk("VEVENT")),
    )


def test_leerer_feed_bricht_ab_archiv_bleibt(config, tmp_path, caplog):
    config = _config(config, tmp_path)
    main.run(config, EXPORT, FIXTURE)
    archiv_vorher, _ = _archiv_und_feed(config)

    leer = tmp_path / "leer.ics"
    leer.write_bytes(b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Events//EN\r\nEND:VCALENDAR\r\n")
    with caplog.at_level(logging.WARNING):
        assert main.run(config, EXPORT + timedelta(hours=6), leer) == 0

    archiv_nachher, anzahl = _archiv_und_feed(config)
    assert archiv_nachher == archiv_vorher
    assert anzahl == 58
    assert "abgebrochen" in caplog.text


def test_mehr_als_die_haelfte_weg_bricht_ab(config, tmp_path):
    config = _config(config, tmp_path)
    main.run(config, EXPORT, FIXTURE)
    archiv_vorher, _ = _archiv_und_feed(config)

    archiv = json.loads(archiv_vorher)
    kuenftige = [e["source_uid"] for e in archiv if e["dtstart"] > EXPORT.isoformat()]
    quelle_neu = _ohne(tmp_path, kuenftige[: len(kuenftige) // 2 + 1])
    assert main.run(config, EXPORT + timedelta(hours=6), quelle_neu) == 0

    archiv_nachher, _ = _archiv_und_feed(config)
    assert archiv_nachher == archiv_vorher


def test_kaputte_quelle_exit_1_archiv_bleibt_feed_neu_geschrieben(config, tmp_path):
    config = _config(config, tmp_path)
    main.run(config, EXPORT, FIXTURE)
    archiv_vorher, _ = _archiv_und_feed(config)
    (tmp_path / "docs" / "uni.ics").unlink()

    html = tmp_path / "login.html"
    html.write_bytes(b"<html><body>Bitte anmelden</body></html>")
    assert main.run(config, EXPORT + timedelta(hours=6), html) == 1

    archiv_nachher, anzahl = _archiv_und_feed(config)
    assert archiv_nachher == archiv_vorher
    assert anzahl == 58


def test_fehlender_link_exit_1(config, tmp_path, monkeypatch):
    monkeypatch.delenv(config.source_env, raising=False)
    assert main.run(_config(config, tmp_path), EXPORT) == 1


def test_abo_link_taucht_nie_im_log_auf(config, tmp_path, monkeypatch, caplog):
    geheim = "https://campus.example/ical/geheimes-token-123"
    monkeypatch.setenv(config.source_env, geheim)

    def kaputt(url, timeout):
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}")

    monkeypatch.setattr(requests, "get", kaputt)
    with caplog.at_level(logging.DEBUG):
        assert main.run(_config(config, tmp_path), EXPORT) == 1
    assert "geheimes-token" not in caplog.text
    assert "ConnectionError" in caplog.text


def test_module_werden_geloggt(config, tmp_path, caplog):
    with caplog.at_level(logging.INFO):
        main.run(_config(config, tmp_path), EXPORT, FIXTURE)
    assert "DS+SoE: Datenqualitätsmanagement" in caplog.text
    assert "Prüfungstermin-Wirtschaftsenglisch 3 (1)" in caplog.text


def test_env_datei(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text('# Kommentar\nexport UNI_TEST_URL="https://x.example/a"\n', encoding="utf-8")
    monkeypatch.setenv("UNI_TEST_URL", "vorher")
    monkeypatch.delenv("UNI_TEST_URL")
    load_env_file(tmp_path / ".env")
    assert os.environ["UNI_TEST_URL"] == "https://x.example/a"


def test_env_datei_ueberschreibt_gesetzte_variable_nicht(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("UNI_TEST_URL=aus-der-datei\n", encoding="utf-8")
    monkeypatch.setenv("UNI_TEST_URL", "aus-dem-secret")
    load_env_file(tmp_path / ".env")
    assert os.environ["UNI_TEST_URL"] == "aus-dem-secret"
