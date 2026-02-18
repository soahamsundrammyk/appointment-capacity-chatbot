"""Entity tools for listing and validating entities from cached data."""

import logging
from typing import Any, Callable

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from capacity_chatbot.tools.validation import (
    _extract_advisor_name,
    _extract_transport_name,
    validate_entities,
)
from capacity_chatbot.utils.state_extractor import extract_state
from capacity_chatbot.utils.uuid_mapper import UUIDMapper

logger = logging.getLogger(__name__)


def _get_cached_data(config: RunnableConfig) -> dict[str, Any] | None:
    """Get cached data from state, with fallback to test data if needed.

    Returns:
        Cached data dict or None if unavailable
    """
    state, error = extract_state(config)
    if error:
        return None

    cached_data = state.cached_data or {}
    if not cached_data:
        from capacity_chatbot.utils.test_data import ensure_cached_data

        ensure_cached_data(state)
        cached_data = state.cached_data or {}

    return cached_data or None


def _format_simple_entity_list(
    entities: list[dict[str, Any]],
    name_extractor: Callable[[dict[str, Any]], str | None],
    entity_type_name: str,
    not_found_msg: str,
) -> str:
    """Format a simple list of entities (transport options or advisors).

    Args:
        entities: List of entity dictionaries from cached data
        name_extractor: Function to extract name from entity dict
        entity_type_name: Human-readable entity type name for output
        not_found_msg: Message to return if no entities found

    Returns:
        Formatted string with entity list
    """
    if not entities:
        return not_found_msg

    names = []
    for entity in entities:
        name = name_extractor(entity)
        if name:
            names.append(name)

    if not names:
        return not_found_msg

    name_list = "\n".join("- %s" % n for n in names)
    return "Available %s (%d):\n%s" % (entity_type_name, len(names), name_list)


@tool
async def get_available_entities(
    entity_type: str,
    config: RunnableConfig = None,
) -> str:
    """Get available transport options, advisors, or teams from cached data.

    Use this tool when user wants to see a list of available entities:
    - "What transport options are available?" → entity_type="transport_options"
    - "List all advisors" → entity_type="advisors"
    - "What teams are there?" → entity_type="teams"
    - "Show me the service advisors" → entity_type="advisors"

    Args:
        entity_type: One of 'transport_options', 'advisors', or 'teams'
        config: RunnableConfig (automatically provided)

    Returns:
        Formatted list of available entities with names
    """
    cached_data = _get_cached_data(config)
    if not cached_data:
        return "No cached data available."

    entity_type_lower = entity_type.lower().strip()

    if entity_type_lower in ["transport_options", "transport", "transportation"]:
        options = cached_data.get("transport_options", [])
        return _format_simple_entity_list(
            options, _extract_transport_name, "transport options", "No transport options found."
        )

    elif entity_type_lower in ["advisors", "advisor", "service_advisors"]:
        advisors = cached_data.get("advisors", [])
        return _format_simple_entity_list(
            advisors, _extract_advisor_name, "advisors", "No advisors found."
        )

    elif entity_type_lower in ["teams", "team"]:
        teams = cached_data.get("teams", [])
        if not teams:
            return "No teams found."

        uuid_mapper = UUIDMapper(cached_data)
        details = []

        for team in teams:
            name = team.get("name", "Unknown")
            advisor_uuids = team.get("dealerAssociateUuids", [])
            advisor_names = [uuid_mapper.get_advisor_name(u) for u in advisor_uuids]
            # Filter out cases where UUID wasn't mapped (get_advisor_name returns UUID if not found)
            advisor_names = [n for n in advisor_names if n and n not in advisor_uuids]

            if advisor_names:
                details.append("- %s: %s" % (name, ", ".join(advisor_names)))
            else:
                details.append("- %s" % name)

        details_list = "\n".join(details)
        return "Available teams (%d):\n%s" % (len(teams), details_list)

    else:
        return (
            "Invalid entity type: '%s'. Use 'transport_options', 'advisors', or 'teams'."
            % entity_type
        )


@tool
async def confirm_entity(
    entity_type: str,
    entity_names: str,
    config: RunnableConfig = None,
) -> str:
    """Validate entity names before making API calls to prevent errors.

    Use this when you're unsure if an entity name is correct:
    - User says "capacity for John" → confirm_entity("advisor", "John")
    - User says "loaner capacity" → confirm_entity("transport", "Loaner")
    - User says "express team" → confirm_entity("team", "express")

    Uses fuzzy matching so "Visal" will match "Vishal".

    Args:
        entity_type: 'advisor', 'team', or 'transport'
        entity_names: Comma-separated list of names to validate
        config: RunnableConfig (automatically provided)

    Returns:
        Validation result with confirmed names and suggestions for typos
    """
    cached_data = _get_cached_data(config)
    if not cached_data:
        return "No cached data available."

    names_list = [name.strip() for name in entity_names.split(",") if name.strip()]
    if not names_list:
        return "Please provide at least one entity name."

    result = validate_entities(entity_type, names_list, cached_data)

    # Message already contains all info (success, errors, suggestions)
    return result["message"]


ENTITY_TOOLS = [
    get_available_entities,
    confirm_entity,
]
