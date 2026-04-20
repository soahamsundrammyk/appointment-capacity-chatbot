"""Migrate the Python COMMON_QUESTIONS KB to per-topic JSON files.

Idempotent: rerunning produces the same output given the same input.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from collections import defaultdict
from pathlib import Path

TOPIC_KEYWORDS: list[tuple[str, str]] = [
    ("holiday", "holiday"),
    ("holiday", "easter"),
    ("holiday", "block off"),
    ("holiday", "block all appointments"),
    ("transport", "transport"),
    ("transport", "loaner"),
    ("transport", "shuttle"),
    ("transport", "pickup and delivery"),
    ("schedule", "advisor schedule"),
    ("schedule", "individual schedule"),
    ("schedule", "dealer schedule"),
    ("schedule", "recurring schedule"),
    ("schedule", "turn off days"),
    ("online-scheduler", "online scheduler"),
    ("online-scheduler", "web scheduler"),
    ("assignment", "assignment rule"),
    ("capacity", "capacity rule"),
    ("capacity", "capacity"),
]

# Categories where we trust the label directly
CATEGORY_PASSTHROUGH = {
    "concept": "concept",
    "troubleshooting": "troubleshooting",
    "limit-info": "concept",
    "rules": "capacity",
}


def infer_topic(category: str, question: str) -> str:
    q = question.lower()
    # For how-to and navigation, infer from question text
    if category in ("how-to", "navigation"):
        for topic, keyword in TOPIC_KEYWORDS:
            if keyword in q:
                return topic
        return "concept"
    return CATEGORY_PASSTHROUGH.get(category, "concept")


def make_id(topic: str, question: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")
    return f"{topic}.{slug[:50].rstrip('-')}"


def migrate_entries(old_entries: list[dict]) -> list[dict]:
    """Migrate old entries to new schema. Collision-safe ID generation."""
    seen_ids: set[str] = set()
    migrated = []
    for e in old_entries:
        topic = infer_topic(e.get("category", ""), e["question"])
        base_id = make_id(topic, e["question"])
        new_id = base_id
        suffix = 2
        while new_id in seen_ids:
            new_id = f"{base_id}-{suffix}"
            suffix += 1
        seen_ids.add(new_id)
        migrated.append({
            "id": new_id,
            "question": e["question"],
            "answer": e["answer"],
            "tier": "base",
            "topic": topic,
        })
    return migrated


def extract_common_questions(source_path: Path) -> list[dict]:
    """Parse the Python module and extract COMMON_QUESTIONS as a list of dicts."""
    tree = ast.parse(source_path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "COMMON_QUESTIONS":
            return ast.literal_eval(node.value)
    raise RuntimeError(f"COMMON_QUESTIONS not found in {source_path}")


def write_by_topic(entries: list[dict], out_dir: Path) -> None:
    """Group entries by topic, write each to <topic>.json (sorted by id)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    by_topic: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_topic[e["topic"]].append(e)
    for topic, group in by_topic.items():
        group.sort(key=lambda x: x["id"])
        (out_dir / f"{topic}.json").write_text(json.dumps(group, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    old = extract_common_questions(args.source)
    print(f"Found {len(old)} entries in {args.source}")
    migrated = migrate_entries(old)
    write_by_topic(migrated, args.out)
    files = sorted(p.name for p in args.out.glob("*.json"))
    print(f"Wrote {len(files)} topic files to {args.out}:")
    for f in files:
        print(f"  {f}")


if __name__ == "__main__":
    main()
