"""Load the static support directory and the fictional professional list."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def support_data() -> dict:
    path = ROOT / "resources" / "support_resources.json"
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def professionals_data() -> dict:
    path = ROOT / "resources" / "professionals.json"
    return json.loads(path.read_text(encoding="utf-8"))


def resources() -> list[dict]:
    return list(support_data().get("resources") or [])


def unverified() -> bool:
    data = support_data()
    return data.get("verification_status") != "VERIFIED" or not data.get("human_verified")


def localized_name(row: dict, language: str, field: str = "name") -> str:
    value = row.get(field) or {}
    if isinstance(value, str):
        return value
    return value.get(language) or value.get("en") or ""


def crisis_lines(language: str, limit: int = 4, kinds: tuple[str, ...] = ("emergency", "listening")) -> list[str]:
    """Short lines for scripted replies. Numbers come only from the static file."""
    preferred = [row for row in resources() if row.get("kind") in kinds]
    lines = []
    for row in preferred:
        if len(lines) >= limit:
            break
        name = localized_name(row, language)
        hours = localized_name(row, language, "hours")
        phone = row.get("phone") or ""
        if hours:
            lines.append(f"{phone} {name} ({hours})")
        else:
            lines.append(f"{phone} {name}")
    return lines
