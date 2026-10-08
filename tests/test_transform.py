import dataclasses

import pytest

from uni_kalender import transform

# SPEC.md Abschnitt 5: die sechs Module aus der Tabelle.
MODULE = {
    "Wirtschaftsenglisch 3 Gr. 04 F GM+WI+WING 25W  LLO (Live Learning Online)": "Wirtschaftsenglisch 3",
    "Management der Wertschöpfungskette Gr. 2 GM+WI+WING 25W LLO/GSS Gr. 2 GSS (Guided Self-Studies)": "Management der Wertschöpfungskette",
    "Anwendungssysteme & Informationsmanagement WI 25W Solingen LLC (Live Learning on Campus)": "Anwendungssysteme & Informationsmanagement",
    "DS+SoE: Datenqualitätsmanagement WI 25W  GSS (Guided Self-Studies)": "DS+SoE: Datenqualitätsmanagement",
    "Infoveranstaltung Fallstudie 25W  LLO (Live Learning Online)": "Infoveranstaltung Fallstudie",
    "Projektmanagement Gr. 2 GM+WI+WING 25W Solingen WI+WING LLC (Live Learning on Campus)": "Projektmanagement",
}


@pytest.mark.parametrize("summary,modul", MODULE.items())
def test_modulname(config, summary, modul):
    assert transform.ermittle_modul(summary, config) == modul


def test_alle_termine_der_fixture_ergeben_eines_der_sechs_module(config, campus):
    module = {transform.transform(v, config)["module"] for v in campus.values()}
    assert module == set(MODULE.values())


@pytest.mark.parametrize(
    "source_uid,typ,langform",
    [
        ("207875@simovative.com", "LLO", "Live Learning Online"),
        ("207883@simovative.com", "GSS", "Guided Self-Studies"),
        ("209435@simovative.com", "LLC", "Live Learning on Campus"),
        ("207950@simovative.com", "Prüfungstermin", "LV"),
    ],
)
def test_typerkennung(campus, source_uid, typ, langform):
    assert transform.erkenne_typ(str(campus[source_uid]["SUMMARY"])) == (typ, langform)


@pytest.mark.parametrize(
    "source_uid,titel",
    [
        ("207875@simovative.com", "LLO-Wirtschaftsenglisch 3"),
        ("209013@simovative.com", "GSS-Management der Wertschöpfungskette"),
        ("209435@simovative.com", "LLC-Anwendungssysteme & Informationsmanagement"),
        ("207950@simovative.com", "Prüfungstermin-Wirtschaftsenglisch 3"),
        ("209689@simovative.com", "GSS-DS+SoE: Datenqualitätsmanagement"),
        ("209980@simovative.com", "LLO-Infoveranstaltung Fallstudie"),
        ("209766@simovative.com", "LLC-Projektmanagement"),
    ],
)
def test_titel_exakt(config, campus, source_uid, titel):
    assert transform.transform(campus[source_uid], config)["summary"] == titel


def test_typ_mit_llo_gss_im_vorspann_zaehlt_nur_am_ende(config, campus):
    """"... 25W LLO/GSS Gr. 2 GSS (Guided Self-Studies)" ist GSS."""
    entry = transform.transform(campus["209013@simovative.com"], config)
    assert entry["type"] == "GSS"


def test_abgesagt_titel():
    assert transform.titel("LLC", "Projektmanagement", cancelled=True) == "ABGESAGT LLC-Projektmanagement"


def test_unbekannter_typ_wird_uebernommen_und_geloggt(config, caplog):
    with caplog.at_level("WARNING"):
        teile = transform.zerlege("Statistik WI 25W  HYB (Hybrid Learning)", config)
    assert (teile.typ, teile.modul) == ("HYB", "Statistik")
    assert transform.titel(teile.typ, teile.modul) == "HYB-Statistik"
    assert "HYB" in caplog.text


def test_studiengang_nur_am_ende_entfernt(config):
    assert transform.ermittle_modul("WI Grundlagen WI 25W  LLO (Live Learning Online)", config) == "WI Grundlagen"


def test_override_vor_allen_regeln(config):
    config = dataclasses.replace(config, modul_overrides={"Fallstudie 25W": "Fallstudie (Info)"})
    summary = "Infoveranstaltung Fallstudie 25W  LLO (Live Learning Online)"
    assert transform.ermittle_modul(summary, config) == "Fallstudie (Info)"


def test_ohne_semester_token_wird_der_typ_abgeschnitten(config, caplog):
    with caplog.at_level("WARNING"):
        modul = transform.ermittle_modul("Projektmanagement Gr. 2 LLO (Live Learning Online)", config)
    assert modul == "Projektmanagement"
    assert "Semester" in caplog.text


def test_uid_aus_quell_uid(config, campus):
    assert transform.transform(campus["209435@simovative.com"], config)["uid"] == "cbs-209435"


def test_zwei_raeume_bleiben_vollstaendig_erhalten(config, campus):
    entry = transform.transform(campus["209437@simovative.com"], config)
    assert entry["location"] == "SOL P.2.03 Kuala Lumpur [16], SOL P.2.04 Shanghai [18]"


def test_ein_raum_unveraendert(config, campus):
    assert transform.transform(campus["209435@simovative.com"], config)["location"] == "SOL P.2.04 Shanghai [18]"


def test_leeres_location_bleibt_leer(config, campus):
    assert transform.transform(campus["207875@simovative.com"], config)["location"] == ""


def test_notiz_ist_die_original_summary(config, campus):
    entry = transform.transform(campus["207875@simovative.com"], config)
    assert entry["description"] == "Wirtschaftsenglisch 3 Gr. 04 F GM+WI+WING 25W  LLO (Live Learning Online)"


def test_zeiten_unveraendert_mit_zeitzone(config, campus):
    entry = transform.transform(campus["209435@simovative.com"], config)
    assert entry["dtstart"] == "2026-10-08T12:45:00+02:00"
    assert entry["dtend"] == "2026-10-08T17:45:00+02:00"
    # Nach der Zeitumstellung am 25.10.: Winterzeit.
    entry = transform.transform(campus["209437@simovative.com"], config)
    assert entry["dtstart"] == "2026-10-29T08:30:00+01:00"


def test_archiveintrag_hat_die_felder_aus_der_spec(config, campus):
    entry = transform.transform(campus["209435@simovative.com"], config)
    assert list(entry) == [
        "uid", "source_uid", "summary", "module", "type", "dtstart", "dtend",
        "location", "description", "cancelled",
    ]
