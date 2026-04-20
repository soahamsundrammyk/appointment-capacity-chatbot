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
