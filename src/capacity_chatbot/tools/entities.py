"""Entity tools for listing and validating entities from cached data."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.utils.enums import EntityType
from capacity_chatbot.utils.uuid_mapper import UUIDMapper

logger = logging.getLogger(__name__)


# =============================================================================
# Main Tools
# =============================================================================


@tool
async def get_available_entities(
    entity_type: str,
    config: RunnableConfig = None,
) -> str:
    """Get available transport options, advisors, or teams.

    EXAMPLES:
    - "What transport options are available?" → entity_type="transport_options"
    - "List all advisors" → entity_type="advisors"
    - "What teams are there?" → entity_type="teams"

    Args:
        entity_type: 'transport_options', 'advisors', or 'teams'
        config: RunnableConfig (auto-provided)
    """
    state, cached_data, error = _extract_state_with_cache(config)
    if error:
        return error

    normalized = EntityType.from_alias(entity_type)
    if not normalized:
        return f"Invalid entity type: '{entity_type}'. Use 'transport_options', 'advisors', or 'teams'."

    if normalized == EntityType.TRANSPORT_OPTIONS:
        return _format_transport_options(cached_data)
    elif normalized == EntityType.ADVISORS:
        return _format_advisors(cached_data)
    elif normalized == EntityType.TEAMS:
        return _format_teams(cached_data)

    return "Unknown entity type."


@tool
async def confirm_entity(
    entity_type: str,
    entity_names: str,
    config: RunnableConfig = None,
) -> str:
    """Validate entity names before making API calls.

    Uses fuzzy matching so "Visal" matches "Vishal".

    EXAMPLES:
    - User says "capacity for John" → confirm_entity("advisor", "John")
    - User says "loaner capacity" → confirm_entity("transport", "Loaner")

    Args:
        entity_type: 'advisor', 'team', or 'transport'
        entity_names: Comma-separated names to validate
        config: RunnableConfig (auto-provided)
    """
    state, cached_data, error = _extract_state_with_cache(config)
    if error:
        return error

    names_list = [n.strip() for n in entity_names.split(",") if n.strip()]
    if not names_list:
        return "Please provide at least one entity name."

    from capacity_chatbot.tools.validation import validate_entities

    result = validate_entities(entity_type, names_list, cached_data, fuzzy_match=True)

    parts = [result["message"]]

    if result["valid"]:
        parts.append("\nConfirmed:")
        for name, _ in result["valid"]:
            parts.append(f"  - {name}")

    if result.get("suggestions"):
        parts.append("\nSuggestions:")
        for invalid, suggestions in result["suggestions"].items():
            parts.append(f"  - '{invalid}' -> {', '.join(suggestions)}")

    return "\n".join(parts)


# =============================================================================
# State Extraction
# =============================================================================


def _extract_state_with_cache(config: RunnableConfig) -> Tuple[Optional[CapacityChatbotState], Dict[str, Any], Optional[str]]:
    """Extract state and ensure cached data is available."""
    if not config:
        return None, {}, "Error: Config not available"

    state: CapacityChatbotState = config.get("configurable", {}).get("state")
    if not state:
        return None, {}, "Error: State not available"

    cached_data = state.cached_data or {}

    if not cached_data:
        from capacity_chatbot.utils.test_data import ensure_cached_data
        ensure_cached_data(state)
        cached_data = state.cached_data or {}

    if not cached_data:
        return state, {}, "No cached data available."

    return state, cached_data, None


# =============================================================================
# Entity Formatters
# =============================================================================


def _format_transport_options(cached_data: Dict[str, Any]) -> str:
    """Format transport options list."""
    options = cached_data.get("transport_options", [])
    if not options:
        return "No transport options found."

    names = [t.get("customName") or t.get("optionName", "") for t in options
             if t.get("customName") or t.get("optionName")]

    return f"Available transport options ({len(names)}):\n" + "\n".join(f"- {n}" for n in names)


def _format_advisors(cached_data: Dict[str, Any]) -> str:
    """Format advisors list."""
    advisors = cached_data.get("advisors", [])
    if not advisors:
        return "No advisors found."

    names = []
    for a in advisors:
        name = f"{a.get('firstName', '')} {a.get('lastName', '')}".strip()
        if not name:
            name = a.get("associateName", "") or a.get("name", "")
        if name:
            names.append(name)

    return f"Available advisors ({len(names)}):\n" + "\n".join(f"- {n}" for n in names)


def _format_teams(cached_data: Dict[str, Any]) -> str:
    """Format teams list with member details."""
    teams = cached_data.get("teams", [])
    if not teams:
        return "No teams found."

    uuid_mapper = UUIDMapper(cached_data)
    details = []

    for team in teams:
        name = team.get("name", "Unknown")
        advisor_uuids = team.get("dealerAssociateUuids", [])
        advisor_names = [uuid_mapper.get_advisor_name(u) for u in advisor_uuids]
        advisor_names = [n for n in advisor_names if n and n not in advisor_uuids]

        if advisor_names:
            details.append(f"- {name}: {', '.join(advisor_names)}")
        else:
            details.append(f"- {name}")

    return f"Available teams ({len(teams)}):\n" + "\n".join(details)


# =============================================================================
# Exports
# =============================================================================


ENTITY_TOOLS = [
    get_available_entities,
    confirm_entity,
]
