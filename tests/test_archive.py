from datetime import datetime, timedelta

from uni_kalender import archive
from conftest import BERLIN

JETZT = datetime(2026, 10, 7, 14, 0, tzinfo=BERLIN)


def _termin(nr, start, summary="LLC-Projektmanagement", location="SOL P.2.01 Delhi [22]"):
    return {
        "uid": f"cbs-{nr}",
        "source_uid": f"{nr}@simovative.com",
        "summary": summary,
        "module": summary.split("-", 1)[1],
        "type": summary.split("-", 1)[0],
        "dtstart": start.isoformat(),
        "dtend": (start + timedelta(minutes=90)).isoformat(),
        "location": location,
        "description": "Projektmanagement Gr. 2 GM+WI+WING 25W Solingen WI+WING LLC (Live Learning on Campus)",
        "cancelled": False,
    }


def _kuenftig(nr, tage=7):
    return _termin(nr, JETZT + timedelta(days=tage))


def _vergangen(nr, tage=7):
    return _termin(nr, JETZT - timedelta(days=tage))


def test_neuer_termin_bekommt_first_und_last_seen():
    ergebnis = archive.merge([], [_kuenftig(1)], JETZT)
    assert ergebnis[0]["first_seen"] == ergebnis[0]["last_seen"] == JETZT.isoformat()
    assert list(ergebnis[0])[-2:] == ["first_seen", "last_seen"]


def test_verschiebung_aktualisiert_ohne_abgesagt():
    archiv = archive.merge([], [_kuenftig(1)], JETZT)
    verschoben = _termin(1, JETZT + timedelta(days=9), location="SOL P.2.04 Shanghai [18]")
    spaeter = JETZT + timedelta(hours=6)

    ergebnis = archive.merge(archiv, [verschoben], spaeter)
    assert len(ergebnis) == 1
    assert ergebnis[0]["uid"] == "cbs-1"
    assert ergebnis[0]["dtstart"] == verschoben["dtstart"]
    assert ergebnis[0]["location"] == "SOL P.2.04 Shanghai [18]"
    assert ergebnis[0]["summary"] == "LLC-Projektmanagement"
    assert ergebnis[0]["cancelled"] is False
    assert ergebnis[0]["first_seen"] == JETZT.isoformat()
    assert ergebnis[0]["last_seen"] == spaeter.isoformat()


def test_streichung_kuenftiger_termin_bekommt_abgesagt_und_bleibt():
    archiv = archive.merge([], [_kuenftig(1), _kuenftig(2)], JETZT)
    ergebnis = archive.merge(archiv, [_kuenftig(2)], JETZT + timedelta(hours=6))
    gestrichen = next(e for e in ergebnis if e["uid"] == "cbs-1")
    assert len(ergebnis) == 2
    assert gestrichen["cancelled"] is True
    assert gestrichen["summary"] == "ABGESAGT LLC-Projektmanagement"


def test_vergangener_termin_faellt_nur_aus_dem_zeitfenster():
    """SPEC.md Abschnitt 9: Die Hochschule nimmt vergangene Veranstaltungen
    nach einer Weile aus dem Export. Das ist keine Streichung."""
    archiv = archive.merge([], [_vergangen(1), _kuenftig(2)], JETZT - timedelta(days=10))
    ergebnis = archive.merge(archiv, [_kuenftig(2)], JETZT)
    vergangen = next(e for e in ergebnis if e["uid"] == "cbs-1")
    assert vergangen["cancelled"] is False
    assert vergangen["summary"] == "LLC-Projektmanagement"


def test_laufender_termin_gilt_als_begonnen():
    laufend = _termin(1, JETZT - timedelta(minutes=30))
    archiv = archive.merge([], [laufend], JETZT - timedelta(days=1))
    assert archive.merge(archiv, [], JETZT)[0]["cancelled"] is False


def test_wiederauftauchen_entfernt_das_praefix():
    archiv = archive.merge([], [_kuenftig(1), _kuenftig(2)], JETZT)
    archiv = archive.merge(archiv, [_kuenftig(2)], JETZT + timedelta(hours=6))
    ergebnis = archive.merge(archiv, [_kuenftig(1), _kuenftig(2)], JETZT + timedelta(hours=12))
    wieder = next(e for e in ergebnis if e["uid"] == "cbs-1")
    assert wieder["cancelled"] is False
    assert wieder["summary"] == "LLC-Projektmanagement"


def test_gestrichener_termin_bleibt_nach_seinem_datum_abgesagt():
    archiv = archive.merge([], [_kuenftig(1, tage=1), _kuenftig(2)], JETZT)
    archiv = archive.merge(archiv, [_kuenftig(2)], JETZT + timedelta(hours=6))
    ergebnis = archive.merge(archiv, [_kuenftig(2)], JETZT + timedelta(days=3))
    assert next(e for e in ergebnis if e["uid"] == "cbs-1")["summary"] == "ABGESAGT LLC-Projektmanagement"


def test_absage_der_quelle_per_status():
    abgesagt = _kuenftig(1)
    abgesagt.update(cancelled=True, summary="ABGESAGT LLC-Projektmanagement")
    ergebnis = archive.merge([], [abgesagt], JETZT)
    assert ergebnis[0]["summary"] == "ABGESAGT LLC-Projektmanagement"


def test_geschuetzte_uid_wird_nicht_gestrichen():
    archiv = archive.merge([], [_kuenftig(1)], JETZT)
    ergebnis = archive.merge(archiv, [], JETZT + timedelta(hours=6), protect={"cbs-1"})
    assert ergebnis[0]["cancelled"] is False


# --- Schutz gegen fehlerhafte Abrufe ----------------------------------------

def _archiv(kuenftige=10, vergangene=10):
    eintraege = [_kuenftig(i, tage=i + 1) for i in range(kuenftige)]
    eintraege += [_vergangen(100 + i, tage=i + 1) for i in range(vergangene)]
    return archive.merge([], eintraege, JETZT - timedelta(days=30))


def test_leerer_feed_bricht_ab():
    grund = archive.pruefe_schutz(_archiv(), set(), JETZT, 0.5, 3)
    assert grund is not None
    assert "10 von 10" in grund


def test_mehr_als_die_haelfte_der_kuenftigen_bricht_ab():
    archiv = _archiv()
    noch_da = {e["uid"] for e in archiv if e["uid"] in {f"cbs-{i}" for i in range(4)}}
    assert archive.pruefe_schutz(archiv, noch_da, JETZT, 0.5, 3) is not None


def test_genau_die_haelfte_ist_noch_erlaubt():
    archiv = _archiv()
    noch_da = {f"cbs-{i}" for i in range(5)}
    assert archive.pruefe_schutz(archiv, noch_da, JETZT, 0.5, 3) is None


def test_vergangene_termine_zaehlen_fuer_den_schutz_nicht():
    """Zum Semesterende fallen viele vergangene Termine heraus, ohne dass
    künftige fehlen -- das darf den Lauf nicht blockieren."""
    archiv = _archiv(kuenftige=4, vergangene=40)
    noch_da = {f"cbs-{i}" for i in range(4)}
    assert archive.pruefe_schutz(archiv, noch_da, JETZT, 0.5, 3) is None


def test_einzelne_letzte_streichung_blockiert_nicht():
    archiv = _archiv(kuenftige=2, vergangene=40)
    assert archive.pruefe_schutz(archiv, set(), JETZT, 0.5, 3) is None


def test_einzelne_streichungen_laufen_durch():
    archiv = _archiv(kuenftige=40, vergangene=0)
    noch_da = {f"cbs-{i}" for i in range(38)}
    assert archive.pruefe_schutz(archiv, noch_da, JETZT, 0.5, 3) is None


def test_save_und_load(tmp_path):
    archiv = archive.merge([], [_kuenftig(1)], JETZT)
    pfad = tmp_path / "data" / "archive.json"
    archive.save(pfad, archiv)
    assert archive.load(pfad) == archiv
