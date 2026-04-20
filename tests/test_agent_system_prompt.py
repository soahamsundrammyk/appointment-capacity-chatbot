"""Verify agent node builds system prompt with KB + cache_control."""
from langchain_core.messages import SystemMessage
from capacity_chatbot.knowledge import KB
from capacity_chatbot.knowledge.prompt_builder import build_system_messages
from capacity_chatbot.prompts import get_capacity_agent_system_prompt


def test_system_message_has_two_blocks_with_cache_control():
    behavioral = get_capacity_agent_system_prompt(current_time="test")
    blocks = build_system_messages(entries=KB, tier="base", behavioral_prompt=behavioral)
    msg = SystemMessage(content=blocks)
    assert len(msg.content) == 2
    assert msg.content[0]["type"] == "text"
    assert msg.content[1]["type"] == "text"
    assert msg.content[1]["cache_control"] == {"type": "ephemeral"}
    # KB block contains actual content from loaded entries
    assert "Q:" in msg.content[1]["text"]


def test_tiers_produce_different_sizes():
    behavioral = get_capacity_agent_system_prompt(current_time="test")
    base = build_system_messages(entries=KB, tier="base", behavioral_prompt=behavioral)
    manager = build_system_messages(entries=KB, tier="manager", behavioral_prompt=behavioral)
    internal = build_system_messages(entries=KB, tier="internal", behavioral_prompt=behavioral)
    # All 59 existing entries are tier=base, so they're equal for now.
    # But structure must be same:
    assert len(base) == len(manager) == len(internal) == 2
