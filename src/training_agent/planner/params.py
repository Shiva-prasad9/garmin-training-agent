"""Rule thresholds: code defaults, overridden by config/rules.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
RULES_PATH = ROOT / "config" / "rules.yaml"


def load_section(name: str, defaults: dict, path: str | Path = RULES_PATH) -> dict:
    """Return `defaults` updated with the `name` section of rules.yaml (if present)."""
    cfg = {}
    p = Path(path)
    if p.exists():
        cfg = yaml.safe_load(p.read_text()) or {}
    return {**defaults, **(cfg.get(name) or {})}


def load_athlete(path: str | Path = ROOT / "config" / "athlete.yaml") -> dict:
    """The athlete profile (max heart rate, weekly template, ...); empty dict if the file is missing."""
    p = Path(path)
    return (yaml.safe_load(p.read_text()) or {}) if p.exists() else {}
