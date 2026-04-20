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
