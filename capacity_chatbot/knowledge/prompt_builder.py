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
