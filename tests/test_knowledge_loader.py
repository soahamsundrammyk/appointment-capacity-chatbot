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


def test_load_rejects_malformed_json(tmp_path):
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "a.json").write_text("{not-valid-json")
    with pytest.raises(LoaderError, match="invalid JSON"):
        load_kb(kb_dir)


def test_load_rejects_non_dict_entry(tmp_path):
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "a.json").write_text(json.dumps([1, 2, 3]))
    with pytest.raises(LoaderError):
        load_kb(kb_dir)
