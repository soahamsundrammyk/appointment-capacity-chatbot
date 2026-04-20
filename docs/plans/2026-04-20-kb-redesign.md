# KB Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Replace the keyword-scoring `get_knowledge_answer` tool with long-context injection of a tier-filtered knowledge base, stored as per-topic JSON files.

**Architecture:** KB content moves from a Python list in `knowledge/knowledge_store.py` to per-topic JSON files under `knowledge/kb/`. A loader validates entries at startup. A prompt builder filters by user tier (`base` / `manager` / `internal`) and renders the filtered KB as a system prompt block with Anthropic prompt caching. The agent node calls this builder every request; the `get_knowledge_answer` tool and all scoring logic are deleted.

**Tech Stack:** Python 3.11+, pytest, Pydantic v2, LangGraph, LangChain (`langchain-anthropic`), FastAPI.

**Reference design:** `docs/plans/2026-04-20-kb-redesign-design.md`

---

## Task 0: Set up implementation branch

**Files:**
- None (branch management only)

**Step 1: Verify clean working tree and create branch**

Run:
```bash
git status --short
git checkout -b feat/MYK-kb-redesign
```

Expected: working tree clean on new branch `feat/MYK-kb-redesign`.

If there are uncommitted changes, stash them or commit first — don't force-switch.

---

## Task 1: Scaffold knowledge module directory

**Files:**
- Create: `capacity_chatbot/knowledge/kb/.gitkeep` (empty placeholder — migration will fill this)
- Create: `capacity_chatbot/knowledge/loader.py` (empty for now, will fail import)
- Create: `capacity_chatbot/knowledge/prompt_builder.py` (empty for now)
- Create: `tests/test_knowledge_loader.py`
- Create: `tests/test_prompt_builder.py`

**Step 1: Create the empty files**

```bash
mkdir -p capacity_chatbot/knowledge/kb
touch capacity_chatbot/knowledge/kb/.gitkeep
touch capacity_chatbot/knowledge/loader.py
touch capacity_chatbot/knowledge/prompt_builder.py
touch tests/test_knowledge_loader.py
touch tests/test_prompt_builder.py
```

**Step 2: Commit scaffolding**

```bash
git add capacity_chatbot/knowledge/kb/.gitkeep \
        capacity_chatbot/knowledge/loader.py \
        capacity_chatbot/knowledge/prompt_builder.py \
        tests/test_knowledge_loader.py \
        tests/test_prompt_builder.py
git commit -m "chore: scaffold knowledge module directory"
```

---

## Task 2: Build the loader — schema validation (TDD)

**Files:**
- Modify: `capacity_chatbot/knowledge/loader.py`
- Modify: `tests/test_knowledge_loader.py`

**Step 1: Write the failing test for happy-path load**

In `tests/test_knowledge_loader.py`:

```python
"""Tests for the knowledge base loader."""
import json
from pathlib import Path

import pytest

from capacity_chatbot.knowledge.loader import Entry, load_kb, LoaderError


def _write_kb(tmp_path: Path, files: dict[str, list[dict]]) -> Path:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    for name, entries in files.items():
        (kb_dir / name).write_text(json.dumps(entries))
    return kb_dir


def test_load_single_file(tmp_path):
    kb_dir = _write_kb(tmp_path, {
        "capacity.json": [{
            "id": "capacity.what-is-capacity",
            "question": "What is capacity?",
            "answer": "Capacity is the max appointments per period.",
            "tier": "base",
            "topic": "capacity",
        }],
    })
    entries = load_kb(kb_dir)
    assert len(entries) == 1
    assert entries[0]["id"] == "capacity.what-is-capacity"
    assert entries[0]["tier"] == "base"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_knowledge_loader.py::test_load_single_file -v`
Expected: FAIL with `ImportError: cannot import name 'Entry' from 'capacity_chatbot.knowledge.loader'`.

**Step 3: Implement minimal loader to pass the test**

In `capacity_chatbot/knowledge/loader.py`:

```python
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
    for path in sorted(kb_dir.glob("*.json")):
        raw = json.loads(path.read_text())
        if not isinstance(raw, list):
            raise LoaderError(f"{path.name} must contain a JSON array")
        for item in raw:
            entries.append(item)  # type: ignore[arg-type]
    _validate(entries)
    return entries


def _validate(entries: list[Entry]) -> None:
    seen_ids: set[str] = set()
    required = {"id", "question", "answer", "tier", "topic"}
    for e in entries:
        missing = required - set(e)
        if missing:
            raise LoaderError(f"entry missing fields {missing}: {e}")
        if e["tier"] not in ALLOWED_TIERS:
            raise LoaderError(f"invalid tier {e['tier']!r} in {e['id']}")
        if not ID_PATTERN.match(e["id"]):
            raise LoaderError(f"invalid id format {e['id']!r}")
        if not e["question"].strip() or not e["answer"].strip():
            raise LoaderError(f"empty question/answer in {e['id']}")
        if e["id"] in seen_ids:
            raise LoaderError(f"duplicate id {e['id']!r}")
        seen_ids.add(e["id"])
```

**Step 4: Run the test — confirm it passes**

Run: `pytest tests/test_knowledge_loader.py::test_load_single_file -v`
Expected: PASS.

**Step 5: Add validation edge-case tests**

Append to `tests/test_knowledge_loader.py`:

```python
def test_load_rejects_duplicate_id(tmp_path):
    kb_dir = _write_kb(tmp_path, {
        "a.json": [{"id": "x.y", "question": "Q", "answer": "A", "tier": "base", "topic": "x"}],
        "b.json": [{"id": "x.y", "question": "Q2", "answer": "A2", "tier": "base", "topic": "x"}],
    })
    with pytest.raises(LoaderError, match="duplicate"):
        load_kb(kb_dir)


def test_load_rejects_invalid_tier(tmp_path):
    kb_dir = _write_kb(tmp_path, {
        "a.json": [{"id": "x.y", "question": "Q", "answer": "A", "tier": "admin", "topic": "x"}],
    })
    with pytest.raises(LoaderError, match="invalid tier"):
        load_kb(kb_dir)


def test_load_rejects_bad_id_format(tmp_path):
    kb_dir = _write_kb(tmp_path, {
        "a.json": [{"id": "NoDot", "question": "Q", "answer": "A", "tier": "base", "topic": "x"}],
    })
    with pytest.raises(LoaderError, match="invalid id format"):
        load_kb(kb_dir)


def test_load_rejects_missing_field(tmp_path):
    kb_dir = _write_kb(tmp_path, {
        "a.json": [{"id": "x.y", "question": "Q", "tier": "base", "topic": "x"}],
    })
    with pytest.raises(LoaderError, match="missing fields"):
        load_kb(kb_dir)


def test_load_rejects_non_array(tmp_path):
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "a.json").write_text('{"not": "a list"}')
    with pytest.raises(LoaderError, match="JSON array"):
        load_kb(kb_dir)


def test_load_empty_dir_returns_empty(tmp_path):
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    assert load_kb(kb_dir) == []
```

**Step 6: Run all loader tests**

Run: `pytest tests/test_knowledge_loader.py -v`
Expected: all 6 tests PASS.

**Step 7: Commit**

```bash
git add capacity_chatbot/knowledge/loader.py tests/test_knowledge_loader.py
git commit -m "feat: add KB loader with schema validation"
```

---

## Task 3: Build the prompt builder — tier filtering (TDD)

**Files:**
- Modify: `capacity_chatbot/knowledge/prompt_builder.py`
- Modify: `tests/test_prompt_builder.py`

**Step 1: Write failing test for tier filtering**

In `tests/test_prompt_builder.py`:

```python
"""Tests for prompt builder — tier filtering and rendering."""
import pytest

from capacity_chatbot.knowledge.prompt_builder import (
    TIER_VISIBILITY,
    filter_by_tier,
    render_kb,
    build_system_messages,
)


ENTRIES = [
    {"id": "a.x", "question": "Q1", "answer": "A1", "tier": "base", "topic": "a"},
    {"id": "b.x", "question": "Q2", "answer": "A2", "tier": "manager", "topic": "b"},
    {"id": "c.x", "question": "Q3", "answer": "A3", "tier": "internal", "topic": "c"},
]


def test_base_tier_sees_only_base():
    result = filter_by_tier(ENTRIES, "base")
    assert [e["id"] for e in result] == ["a.x"]


def test_manager_sees_base_and_manager():
    result = filter_by_tier(ENTRIES, "manager")
    assert sorted(e["id"] for e in result) == ["a.x", "b.x"]


def test_internal_sees_all():
    result = filter_by_tier(ENTRIES, "internal")
    assert sorted(e["id"] for e in result) == ["a.x", "b.x", "c.x"]


def test_unknown_tier_raises():
    with pytest.raises(ValueError, match="Unknown tier"):
        filter_by_tier(ENTRIES, "admin")
```

**Step 2: Run to verify failures**

Run: `pytest tests/test_prompt_builder.py -v`
Expected: FAIL with ImportError.

**Step 3: Implement prompt_builder**

In `capacity_chatbot/knowledge/prompt_builder.py`:

```python
"""Build tier-filtered KB system messages with prompt caching hints."""
from __future__ import annotations

from capacity_chatbot.knowledge.loader import Entry

TIER_VISIBILITY: dict[str, set[str]] = {
    "base":     {"base"},
    "manager":  {"base", "manager"},
    "internal": {"base", "manager", "internal"},
}


def filter_by_tier(entries: list[Entry], tier: str) -> list[Entry]:
    if tier not in TIER_VISIBILITY:
        raise ValueError(f"Unknown tier: {tier!r}")
    visible = TIER_VISIBILITY[tier]
    return [e for e in entries if e["tier"] in visible]


def render_kb(entries: list[Entry]) -> str:
    """Render entries as markdown, sorted by id for deterministic caching."""
    sorted_entries = sorted(entries, key=lambda e: e["id"])
    lines = ["# Knowledge Base", ""]
    for e in sorted_entries:
        lines.append(f"## {e['id']}")
        lines.append(f"**Q:** {e['question']}")
        lines.append(f"**A:** {e['answer']}")
        lines.append("")
    return "\n".join(lines)


def build_system_messages(
    entries: list[Entry],
    tier: str,
    behavioral_prompt: str,
) -> list[dict]:
    """Return Anthropic system-message blocks with cache_control on the KB block."""
    filtered = filter_by_tier(entries, tier)
    kb_text = render_kb(filtered)
    return [
        {"type": "text", "text": behavioral_prompt},
        {
            "type": "text",
            "text": kb_text,
            "cache_control": {"type": "ephemeral"},
        },
    ]
```

**Step 4: Run tests — confirm pass**

Run: `pytest tests/test_prompt_builder.py -v`
Expected: 4 tests PASS.

**Step 5: Add rendering + build_system_messages tests**

Append to `tests/test_prompt_builder.py`:

```python
def test_render_is_sorted_by_id():
    unsorted = [
        {"id": "z.a", "question": "Qz", "answer": "Az", "tier": "base", "topic": "z"},
        {"id": "a.b", "question": "Qa", "answer": "Aa", "tier": "base", "topic": "a"},
    ]
    text = render_kb(unsorted)
    assert text.index("a.b") < text.index("z.a")


def test_render_includes_all_fields():
    text = render_kb([ENTRIES[0]])
    assert "a.x" in text
    assert "Q1" in text
    assert "A1" in text


def test_build_system_messages_structure():
    blocks = build_system_messages(ENTRIES, "base", "BEHAVIOR")
    assert len(blocks) == 2
    assert blocks[0] == {"type": "text", "text": "BEHAVIOR"}
    assert blocks[1]["type"] == "text"
    assert blocks[1]["cache_control"] == {"type": "ephemeral"}
    assert "a.x" in blocks[1]["text"]
    # manager/internal entries should NOT be in base-tier output
    assert "b.x" not in blocks[1]["text"]
    assert "c.x" not in blocks[1]["text"]
```

**Step 6: Run all prompt builder tests**

Run: `pytest tests/test_prompt_builder.py -v`
Expected: all 7 tests PASS.

**Step 7: Commit**

```bash
git add capacity_chatbot/knowledge/prompt_builder.py tests/test_prompt_builder.py
git commit -m "feat: add prompt builder with tier filtering and cache_control"
```

---

## Task 4: Write migration script (TDD)

**Files:**
- Create: `scripts/__init__.py` (empty if not present)
- Create: `scripts/migrate_kb_to_json.py`
- Create: `tests/test_migrate_kb.py`

**Step 1: Inspect the existing Python KB**

Read `capacity_chatbot/knowledge/knowledge_store.py` to confirm the `COMMON_QUESTIONS` list shape. Each entry has `question`, `answer`, `category`, `keywords`.

**Step 2: Write failing test for id-generation logic**

In `tests/test_migrate_kb.py`:

```python
"""Tests for the one-time KB migration script."""
from scripts.migrate_kb_to_json import (
    infer_topic,
    make_id,
    migrate_entries,
)


def test_make_id_basic():
    assert make_id("capacity", "What is capacity?") == "capacity.what-is-capacity"


def test_make_id_strips_punctuation():
    assert make_id("holiday", "How do I block Easter Sunday?!") == "holiday.how-do-i-block-easter-sunday"


def test_make_id_truncates_long_slug():
    long_q = "How do I " + "very " * 30 + "long question?"
    result = make_id("concept", long_q)
    # topic + dot + up-to-50-char slug
    slug = result.split(".", 1)[1]
    assert len(slug) <= 50


def test_infer_topic_from_question_transport():
    assert infer_topic("how-to", "How do I increase loaner capacity?") == "transport"


def test_infer_topic_from_question_schedule():
    assert infer_topic("how-to", "How do I update an advisor schedule?") == "schedule"


def test_infer_topic_respects_explicit_category():
    assert infer_topic("troubleshooting", "Why is capacity 0?") == "troubleshooting"


def test_migrate_entries_assigns_tier_base():
    old = [{"question": "Q", "answer": "A", "category": "concept", "keywords": ["k"]}]
    migrated = migrate_entries(old)
    assert migrated[0]["tier"] == "base"
    assert "keywords" not in migrated[0]


def test_migrate_entries_groups_by_topic():
    old = [
        {"question": "What is capacity?", "answer": "...", "category": "concept", "keywords": []},
        {"question": "How do I block a holiday?", "answer": "...", "category": "how-to", "keywords": []},
    ]
    migrated = migrate_entries(old)
    topics = {e["topic"] for e in migrated}
    assert "concept" in topics
    assert "holiday" in topics


def test_migrate_handles_duplicate_slugs():
    old = [
        {"question": "Test", "answer": "A", "category": "concept", "keywords": []},
        {"question": "Test", "answer": "B", "category": "concept", "keywords": []},
    ]
    migrated = migrate_entries(old)
    ids = {e["id"] for e in migrated}
    assert len(ids) == 2  # both got unique IDs
```

**Step 3: Run tests — verify failures**

Run: `pytest tests/test_migrate_kb.py -v`
Expected: FAIL with ImportError.

**Step 4: Implement migration script**

Create `scripts/__init__.py`:
```python
```
(empty file)

Create `scripts/migrate_kb_to_json.py`:

```python
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
```

**Step 5: Run tests — confirm pass**

Run: `pytest tests/test_migrate_kb.py -v`
Expected: all 9 tests PASS.

**Step 6: Commit**

```bash
git add scripts/__init__.py scripts/migrate_kb_to_json.py tests/test_migrate_kb.py
git commit -m "feat: add KB migration script (Python dict -> per-topic JSON)"
```

---

## Task 5: Run migration and validate output

**Files:**
- Create: `capacity_chatbot/knowledge/kb/*.json` (generated by script)
- Delete: `capacity_chatbot/knowledge/kb/.gitkeep`

**Step 1: Run migration**

```bash
python -m scripts.migrate_kb_to_json \
  --source capacity_chatbot/knowledge/knowledge_store.py \
  --out capacity_chatbot/knowledge/kb
```

Expected output: `Found 59 entries in ...` followed by a list of topic JSON files.

**Step 2: Verify the loader accepts the output**

Run: `python -c "from pathlib import Path; from capacity_chatbot.knowledge.loader import load_kb; print(len(load_kb(Path('capacity_chatbot/knowledge/kb'))))"`
Expected output: `59`.

If validation fails, inspect the failing entry, fix the migration script mapping, and rerun.

**Step 3: Inspect diff — manual sanity check**

```bash
ls capacity_chatbot/knowledge/kb/
cat capacity_chatbot/knowledge/kb/capacity.json | python -m json.tool | head -30
```

Confirm topics look sensible (no entries mis-categorized into `concept` that should be `schedule`, etc.). Spot-check 3-5 entries end-to-end. If mapping is wrong, adjust `TOPIC_KEYWORDS` in the script and rerun.

**Step 4: Remove placeholder**

```bash
rm capacity_chatbot/knowledge/kb/.gitkeep
```

**Step 5: Commit the generated KB**

```bash
git add capacity_chatbot/knowledge/kb/
git rm capacity_chatbot/knowledge/kb/.gitkeep 2>/dev/null || true
git commit -m "feat: migrate 59 existing KB entries to per-topic JSON"
```

---

## Task 6: Add module-level loaded KB

**Files:**
- Modify: `capacity_chatbot/knowledge/__init__.py`
- Create: `tests/test_knowledge_init.py`

**Step 1: Check existing `__init__.py`**

Run: `cat capacity_chatbot/knowledge/__init__.py`

**Step 2: Write failing test — KB loads at import time**

In `tests/test_knowledge_init.py`:

```python
def test_kb_is_loaded_at_import():
    from capacity_chatbot.knowledge import KB
    assert isinstance(KB, list)
    assert len(KB) > 0
    assert all("id" in e for e in KB)
```

**Step 3: Run to verify failure**

Run: `pytest tests/test_knowledge_init.py -v`
Expected: FAIL with `ImportError: cannot import name 'KB'`.

**Step 4: Update `capacity_chatbot/knowledge/__init__.py`**

Preserve existing exports; add the `KB` constant. Append:

```python
from pathlib import Path

from capacity_chatbot.knowledge.loader import load_kb

_KB_DIR = Path(__file__).parent / "kb"
KB = load_kb(_KB_DIR)
```

**Step 5: Run test — confirm pass**

Run: `pytest tests/test_knowledge_init.py -v`
Expected: PASS.

**Step 6: Commit**

```bash
git add capacity_chatbot/knowledge/__init__.py tests/test_knowledge_init.py
git commit -m "feat: load KB at module init as capacity_chatbot.knowledge.KB"
```

---

## Task 7: Add `user_tier` to API request model

**Files:**
- Modify: `capacity_chatbot/model/requests.py` (or wherever the run request Pydantic model lives — verify first)
- Modify: `capacity_chatbot/api/routes.py` (to pipe the field through)

**Step 1: Find the request model**

Run: `grep -rn "class.*Request\|messages.*list\|dealer_uuid" capacity_chatbot/model capacity_chatbot/api 2>/dev/null | head -20`

Identify the Pydantic model used for the run endpoint. It's likely in `capacity_chatbot/model/requests.py` or `capacity_chatbot/api/routes.py`. Read that file fully before editing.

**Step 2: Add `user_tier` to the model**

In the request model file, import `Literal` from `typing` and add:

```python
from typing import Literal

class <ExistingRequestModel>(BaseModel):
    # ... existing fields ...
    user_tier: Literal["base", "manager", "internal"] = "base"
```

**Step 3: Pipe `user_tier` through to the graph state**

Wherever the handler converts the request to `InputState`, pass `user_tier=request.user_tier`. Identify the handler with:

```bash
grep -rn "InputState\|invoke\|stream" capacity_chatbot/api/routes.py
```

Add `user_tier` to the state dict being passed in.

**Step 4: Manual smoke-test the API still boots**

Run: `python -c "from capacity_chatbot.api.routes import app; print('ok')"`
Expected: `ok`. If it imports cleanly, the Pydantic model is valid.

**Step 5: Commit**

```bash
git add capacity_chatbot/model/requests.py capacity_chatbot/api/routes.py
git commit -m "feat: accept user_tier in chatbot run request"
```

---

## Task 8: Add `user_tier` to LangGraph state

**Files:**
- Modify: `capacity_chatbot/state.py`

**Step 1: Read the current state**

Run: `cat capacity_chatbot/state.py`

**Step 2: Add `user_tier` to `InputState`**

Add to the TypedDict (keep existing fields; just add one):

```python
from typing import Literal

class InputState(TypedDict):
    # ... existing fields ...
    user_tier: Literal["base", "manager", "internal"]
```

Ensure `CapacityChatbotState` inherits this correctly — no change needed if it already extends InputState.

**Step 3: Verify no type errors**

Run: `python -c "from capacity_chatbot.state import InputState, CapacityChatbotState; print('ok')"`
Expected: `ok`.

**Step 4: Commit**

```bash
git add capacity_chatbot/state.py
git commit -m "feat: add user_tier to graph InputState"
```

---

## Task 9: Wire the agent node to use `build_system_messages`

**Files:**
- Modify: `capacity_chatbot/nodes/capacity_agent.py`

**Step 1: Read the current agent node**

Run: `cat capacity_chatbot/nodes/capacity_agent.py`

Identify:
- Where the LLM is invoked
- Where the system prompt is constructed (likely from `prompts.py`)

**Step 2: Import and call `build_system_messages`**

At the top of `capacity_agent.py`:

```python
from capacity_chatbot.knowledge import KB
from capacity_chatbot.knowledge.prompt_builder import build_system_messages
from capacity_chatbot.prompts import BEHAVIORAL_PROMPT  # or whatever the existing prompt is named
```

If the current system prompt variable has a different name (e.g., `SYSTEM_PROMPT`), rename it to `BEHAVIORAL_PROMPT` in `prompts.py` for clarity, OR import under whatever name it has and alias locally.

Inside the node function, **before the LLM invocation**, replace the existing `SystemMessage(content=SYSTEM_PROMPT)` construction with:

```python
system_blocks = build_system_messages(
    entries=KB,
    tier=state.get("user_tier", "base"),
    behavioral_prompt=BEHAVIORAL_PROMPT,
)
```

Then when invoking the LLM, pass `system_blocks` as the content of the system message. LangChain's `ChatAnthropic` accepts `SystemMessage(content=list_of_blocks)` where each block is a dict with `type`/`text`/`cache_control`.

Concretely, change:
```python
# Before
response = await llm.ainvoke([SystemMessage(content=SYSTEM_PROMPT)] + messages, config=config)
```
to:
```python
# After
response = await llm.ainvoke([SystemMessage(content=system_blocks)] + messages, config=config)
```

**Step 3: Smoke-test the imports**

Run: `python -c "from capacity_chatbot.nodes.capacity_agent import *; print('ok')"`
Expected: `ok`.

**Step 4: Commit**

```bash
git add capacity_chatbot/nodes/capacity_agent.py capacity_chatbot/prompts.py
git commit -m "feat: wire agent to inject tier-filtered KB into system prompt"
```

---

## Task 10: Delete the old `get_knowledge_answer` tool

**Files:**
- Delete: `capacity_chatbot/tools/knowledge.py`
- Modify: `capacity_chatbot/tools/__init__.py` (remove `KNOWLEDGE_TOOLS` export and usage)
- Modify: `capacity_chatbot/prompts.py` (remove references to `get_knowledge_answer`)

**Step 1: Remove the tool export**

Edit `capacity_chatbot/tools/__init__.py`:
- Remove the `from capacity_chatbot.tools.knowledge import ...` import
- Remove `KNOWLEDGE_TOOLS` from any `__all__` list
- Remove `*KNOWLEDGE_TOOLS` from `CAPACITY_TOOLS` list

**Step 2: Delete the tool file**

```bash
git rm capacity_chatbot/tools/knowledge.py
```

**Step 3: Update prompts.py — remove tool references**

Edit `capacity_chatbot/prompts.py`:
- Delete any lines that tell the agent to call `get_knowledge_answer`
- Add one line like: `"The knowledge base below contains authoritative answers for how-to, conceptual, and troubleshooting questions. Cite entries by id when useful."`

**Step 4: Verify nothing else imports from the deleted module**

Run: `grep -rn "get_knowledge_answer\|from capacity_chatbot.tools.knowledge\|KNOWLEDGE_TOOLS" capacity_chatbot tests`
Expected: no results.

If any references remain, fix them.

**Step 5: Smoke-test**

Run: `python -c "from capacity_chatbot.tools import CAPACITY_TOOLS; print(len(CAPACITY_TOOLS))"`
Expected: a number — whatever the remaining tool count is. Should be one less than before.

**Step 6: Commit**

```bash
git add capacity_chatbot/tools/__init__.py capacity_chatbot/prompts.py
git commit -m "refactor: remove get_knowledge_answer tool (replaced by system prompt injection)"
```

---

## Task 11: Delete dead code in `knowledge_store.py`

**Files:**
- Delete: `capacity_chatbot/knowledge/knowledge_store.py`

**Step 1: Verify no remaining imports**

Run: `grep -rn "from capacity_chatbot.knowledge.knowledge_store\|knowledge_store\." capacity_chatbot tests scripts`

The only hit should be in `scripts/migrate_kb_to_json.py` — that script reads the file as source text, not as a module, so deleting it after migration is fine.

**Step 2: Delete the file**

```bash
git rm capacity_chatbot/knowledge/knowledge_store.py
```

**Step 3: Smoke-test**

Run: `python -c "import capacity_chatbot.knowledge; print(len(capacity_chatbot.knowledge.KB))"`
Expected: `59`.

**Step 4: Commit**

```bash
git commit -m "refactor: delete legacy knowledge_store.py (content moved to kb/*.json)"
```

---

## Task 12: End-to-end integration test

**Files:**
- Create: `tests/test_kb_integration.py`

**Step 1: Write a test that exercises the full path**

```python
"""End-to-end: loaded KB + prompt builder produce valid system messages."""
from capacity_chatbot.knowledge import KB
from capacity_chatbot.knowledge.prompt_builder import build_system_messages


def test_base_tier_build_returns_two_blocks():
    blocks = build_system_messages(KB, "base", "TEST-BEHAVIORAL-PROMPT")
    assert len(blocks) == 2
    assert blocks[0]["text"] == "TEST-BEHAVIORAL-PROMPT"
    assert blocks[1]["type"] == "text"
    assert blocks[1]["cache_control"] == {"type": "ephemeral"}


def test_all_tiers_produce_output():
    for tier in ("base", "manager", "internal"):
        blocks = build_system_messages(KB, tier, "B")
        # KB block is non-empty
        assert len(blocks[1]["text"]) > 100


def test_higher_tier_sees_more_entries():
    base_blocks = build_system_messages(KB, "base", "B")
    manager_blocks = build_system_messages(KB, "manager", "B")
    internal_blocks = build_system_messages(KB, "internal", "B")
    assert len(base_blocks[1]["text"]) <= len(manager_blocks[1]["text"])
    assert len(manager_blocks[1]["text"]) <= len(internal_blocks[1]["text"])


def test_rendered_kb_is_deterministic():
    # Same input → same bytes (critical for prompt caching)
    a = build_system_messages(KB, "base", "B")
    b = build_system_messages(KB, "base", "B")
    assert a == b
```

**Step 2: Run the test suite**

Run: `pytest tests/ -v`
Expected: ALL tests pass, including the existing `test_appointment_formatter.py`, `test_date_parser.py`, `test_appointment_filters.py`.

**Step 3: Commit**

```bash
git add tests/test_kb_integration.py
git commit -m "test: add end-to-end integration tests for KB injection"
```

---

## Task 13: Manual smoke test against a running agent

**Files:**
- None (manual verification)

**Step 1: Start the service locally**

Run: `langgraph dev` (or however the project normally runs locally — check README).

Wait for the server to report it is listening.

**Step 2: Send a base-tier request**

In another shell:

```bash
curl -X POST http://localhost:3334/capacity-chatbot/threads/test-thread-1/runs/wait \
  -H 'Content-Type: application/json' \
  -d '{
    "assistant_id": "capacity_agent",
    "input": {
      "messages": [{"role": "user", "content": "How do I block appointments on a holiday?"}],
      "dealer_uuid": "test-dealer-uuid",
      "department_uuid": "test-department-uuid",
      "user_tier": "base"
    },
    "if_not_exists": "create"
  }'
```

Expected: response contains steps from the `holiday` KB topic. The answer should reference the settings menu path (Settings → Appointments → ...). If the model says something generic and non-specific, the KB didn't make it into the prompt — debug by logging `build_system_messages` output.

**Step 3: Send a manager-tier request**

Same curl, change `"user_tier": "manager"`. After content is added in Phase 2, this should surface manager-only entries. For Phase 1 all content is `base`, so the response should be equivalent.

**Step 4: Verify cache hit on second call**

Run the same curl twice in quick succession. The second should be noticeably faster if the Anthropic cache is hit (look at response time, or `usage.cache_read_input_tokens` in the response metadata if exposed).

If caching doesn't trigger, confirm:
- `cache_control` is being passed to Anthropic (check LangChain `ChatAnthropic` version supports it; upgrade `langchain-anthropic` if needed)
- System prompt bytes are identical between calls (deterministic rendering)

**Step 5: No commit needed — this is manual QA**

---

## Task 14: Open PR

**Files:**
- None

**Step 1: Push the branch**

```bash
git push -u origin feat/MYK-kb-redesign
```

**Step 2: Open the PR**

```bash
gh pr create --title "feat: redesign KB with tier-filtered long-context injection" --body "$(cat <<'EOF'
## Summary
- Replace keyword-scoring `get_knowledge_answer` tool with direct injection of tier-filtered KB into the system prompt
- Move 59 existing entries from Python dict in `knowledge_store.py` to per-topic JSON files under `knowledge/kb/`
- Add `user_tier` (base/manager/internal) to the API request and graph state; higher tiers see more entries
- Delete scoring algorithm, synonym expansion, phrase-match logic, and the knowledge tool
- Anthropic prompt caching (`cache_control: ephemeral`) keeps per-request cost negligible

See design doc: `docs/plans/2026-04-20-kb-redesign-design.md`

## Test plan
- [ ] `pytest tests/` — all green
- [ ] Manual curl with `user_tier=base` returns KB-grounded answer to a holiday/capacity question
- [ ] Manual curl with `user_tier=manager` and `user_tier=internal` succeed (Phase 1: same content as base)
- [ ] Second identical curl hits the Anthropic prompt cache (check response metadata / latency)
- [ ] Loader validation fails gracefully on malformed JSON (run `python -c "..."` with a bad file)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Step 3: Report PR URL**

---

## Post-merge next steps (NOT part of this plan)

The Phase 2 content-expansion work (authority/dashboard/communication/ui entries) is intentionally out of scope for this plan. Those are content PRs that only touch JSON files — they have no code changes and don't need a TDD plan. Write them directly, one topic per PR, using `scripts/lookup_dsos.py` (to be built later) to source canonical DSO/authority descriptions.

Phase 3 (frontend `computeUserTier()` helper) lives in the `appointment-ui-client` repo — separate plan there.
