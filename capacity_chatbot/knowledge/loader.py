"""Load and validate KB entries from per-topic JSON files."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypedDict

ALLOWED_TIERS: set[str] = {"base", "manager", "internal"}
ID_PATTERN = re.compile(r"^[a-z0-9-]+\.[a-z0-9-]+$")


class Entry(TypedDict):
    id: str
    question: str
    answer: str
    tier: str
    topic: str


class LoaderError(ValueError):
    """Raised when KB content fails validation."""


def load_kb(kb_dir: Path) -> list[Entry]:
    """Load every *.json under kb_dir, merge, validate, return entries."""
    entries: list[Entry] = []
    id_sources: dict[str, Path] = {}
    for path in sorted(kb_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise LoaderError(f"{path.name}: invalid JSON: {exc}") from exc
        if not isinstance(raw, list):
            raise LoaderError(f"{path.name} must contain a JSON array")
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                entry_id = item["id"]
                if entry_id in id_sources:
                    raise LoaderError(
                        f"duplicate id {entry_id!r} in {path.name} "
                        f"(first seen in {id_sources[entry_id].name})"
                    )
                id_sources[entry_id] = path
            entries.append(item)  # type: ignore[arg-type]
    _validate(entries)
    return entries


def _validate(entries: list[Entry]) -> None:
    required = {"id", "question", "answer", "tier", "topic"}
    for e in entries:
        if not isinstance(e, dict):
            raise LoaderError(f"entry is not a dict: {e!r}")
        missing = required - set(e)
        if missing:
            raise LoaderError(f"entry missing fields {missing}: {e}")
        if e["tier"] not in ALLOWED_TIERS:
            raise LoaderError(f"invalid tier {e['tier']!r} in {e['id']}")
        if not ID_PATTERN.match(e["id"]):
            raise LoaderError(f"invalid id format {e['id']!r}")
        if not e["question"].strip() or not e["answer"].strip():
            raise LoaderError(f"empty question/answer in {e['id']}")
