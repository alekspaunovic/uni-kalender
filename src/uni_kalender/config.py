"""Laden von config.yaml und .env (SPEC.md Abschnitt 10)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Config:
    timezone: str
    feed_ttl: str
    calname: str
    uid_prefix: str
    output_path: str
    archive_path: str
    source_env: str
    typen: list[str] = field(default_factory=list)
    studiengaenge: list[str] = field(default_factory=list)
    modul_overrides: dict[str, str] = field(default_factory=dict)
    schutz_anteil: float = 0.5
    schutz_mindestanzahl: int = 3

    def source_url(self) -> str | None:
        return os.environ.get(self.source_env) or None


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return Config(
        timezone=raw["timezone"],
        feed_ttl=raw["feed_ttl"],
        calname=raw["calname"],
        uid_prefix=raw["uid_prefix"],
        output_path=raw["output_path"],
        archive_path=raw["archive_path"],
        source_env=raw["source_env"],
        typen=list(raw.get("typen") or []),
        studiengaenge=list(raw.get("studiengaenge") or []),
        modul_overrides=dict(raw.get("modul_overrides") or {}),
        schutz_anteil=float(raw.get("schutz_anteil", 0.5)),
        schutz_mindestanzahl=int(raw.get("schutz_mindestanzahl", 3)),
    )


def load_env_file(path: str | Path = ".env") -> None:
    """Liest KEY=VALUE-Zeilen aus einer lokalen .env in die Umgebung. Schon
    gesetzte Variablen gewinnen -- im Workflow kommt der Link aus dem GitHub
    Secret, eine .env gibt es dort nicht. Werte werden nie ausgegeben."""
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)
