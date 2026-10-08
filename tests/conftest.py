from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from uni_kalender import quelle
from uni_kalender.config import load_config

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "fixtures" / "campus-events.ics"
BERLIN = ZoneInfo("Europe/Berlin")
# Zeitpunkt des Exports der Fixture (DTSTAMP 20261007T140116).
EXPORT = datetime(2026, 10, 7, 14, 1, tzinfo=BERLIN)


@pytest.fixture(scope="session")
def config():
    return load_config(REPO_ROOT / "config.yaml")


@pytest.fixture(scope="session")
def campus_cal():
    return quelle.parse(FIXTURE.read_bytes())


@pytest.fixture(scope="session")
def campus(campus_cal):
    """VEVENTs der Fixture nach Quell-UID."""
    return {str(v["UID"]): v for v in campus_cal.walk("VEVENT")}
