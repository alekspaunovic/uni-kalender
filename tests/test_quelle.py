import pytest
import requests

from uni_kalender import quelle
from conftest import FIXTURE


def test_fixture_mit_dtstamp_tzid_und_kaputter_zeile_wird_gelesen(campus):
    """DTSTAMP;TZID=..., unmaskierte Kommas in LOCATION und die Zeile "\\n"
    nach jeder DESCRIPTION -- trotzdem kommen alle 58 Termine an."""
    assert len(campus) == 58
    assert "DTSTAMP" in campus["209435@simovative.com"]


def test_fixture_ist_unveraendert_der_originalexport():
    raw = FIXTURE.read_bytes()
    assert b"DTSTAMP;TZID=Europe/Berlin:" in raw
    assert b"\n\\n \r\n" in raw


@pytest.mark.parametrize("raw", [b"", b"   ", b"<html><body>Login</body></html>", b"BEGIN:VEVENT\r\nEND:VEVENT\r\n"])
def test_kein_gueltiges_vcalendar(raw):
    with pytest.raises(quelle.QuellFehler):
        quelle.parse(raw)


class _Antwort:
    def __init__(self, status):
        self.status_code = status
        self.ok = status < 400
        self.content = b""


GEHEIM = "https://campus.example/ical/geheimes-token-123"


def test_http_fehler_nennt_den_link_nicht(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, timeout: _Antwort(403))
    with pytest.raises(quelle.QuellFehler) as info:
        quelle.fetch(GEHEIM)
    assert "403" in str(info.value)
    assert "geheimes-token" not in str(info.value)


def test_verbindungsfehler_nennt_den_link_nicht(monkeypatch):
    def kaputt(url, timeout):
        raise requests.ConnectionError(f"Max retries exceeded with url: {url}")

    monkeypatch.setattr(requests, "get", kaputt)
    with pytest.raises(quelle.QuellFehler) as info:
        quelle.fetch(GEHEIM)
    assert "geheimes-token" not in str(info.value)
    assert info.value.__cause__ is None
    assert info.value.__suppress_context__ is True
