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
