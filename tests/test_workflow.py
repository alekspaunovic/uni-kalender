import yaml

from conftest import REPO_ROOT

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "feed.yml"


def test_workflow_alle_sechs_stunden_und_manuell():
    raw = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML liest den Schlüssel "on" als True.
    trigger = raw.get("on", raw.get(True))
    assert trigger["schedule"][0]["cron"].endswith("*/6 * * *")
    assert "workflow_dispatch" in trigger
    assert raw["permissions"]["contents"] == "write"


def test_abo_link_nur_aus_dem_secret():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "UNI_ICS_URL: ${{ secrets.UNI_ICS_URL }}" in text


def test_gitignore_enthaelt_env():
    assert ".env" in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_nojekyll_vorhanden():
    assert (REPO_ROOT / "docs" / ".nojekyll").exists()
