"""Entity tools for listing and validating entities from cached data."""

import logging
from typing import Optional

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.utils.uuid_mapper import UUIDMapper

logger = logging.getLogger(__name__)


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
    if not config:
        return "Error: Config not available"
    
    state: CapacityChatbotState = config.get("configurable", {}).get("state")
    if not state:
        return "Error: State not available"
    
    cached_data = state.cached_data or {}
    
    if not cached_data:
        from capacity_chatbot.utils.test_data import ensure_cached_data
        ensure_cached_data(state)
        cached_data = state.cached_data or {}
    
    if not cached_data:
        return "No cached data available."
    
    entity_type_lower = entity_type.lower().strip()
    
    if entity_type_lower in ["transport_options", "transport", "transportation"]:
        options = cached_data.get("transport_options", [])
        if not options:
            return "No transport options found."
        
        names = [t.get("customName") or t.get("optionName", "") for t in options if t.get("customName") or t.get("optionName")]
        return f"Available transport options ({len(names)}):\n" + "\n".join(f"- {n}" for n in names)
    
    elif entity_type_lower in ["advisors", "advisor", "service_advisors"]:
        advisors = cached_data.get("advisors", [])
        if not advisors:
            return "No advisors found."
        
        names = []
        for a in advisors:
            name = a.get("nickname") or f"{a.get('firstName', '')} {a.get('lastName', '')}".strip()
            if name:
                names.append(name)
        
        return f"Available advisors ({len(names)}):\n" + "\n".join(f"- {n}" for n in names)
    
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
            advisor_names = [n for n in advisor_names if n and n not in advisor_uuids]
            
            if advisor_names:
                details.append(f"- {name}: {', '.join(advisor_names)}")
            else:
                details.append(f"- {name}")
        
        return f"Available teams ({len(teams)}):\n" + "\n".join(details)
    
    else:
        return f"Invalid entity type: '{entity_type}'. Use 'transport_options', 'advisors', or 'teams'."


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
    if not config:
        return "Error: Config not available"
    
    state: CapacityChatbotState = config.get("configurable", {}).get("state")
    if not state:
        return "Error: State not available"
    
    cached_data = state.cached_data or {}
    
    if not cached_data:
        from capacity_chatbot.utils.test_data import ensure_cached_data
        ensure_cached_data(state)
        cached_data = state.cached_data or {}
    
    if not cached_data:
        return "No cached data available."
    
    names_list = [name.strip() for name in entity_names.split(",") if name.strip()]
    if not names_list:
        return "Please provide at least one entity name."
    
    from capacity_chatbot.tools.validation import validate_entities
    
    result = validate_entities(entity_type, names_list, cached_data, fuzzy_match=True)
    
    parts = [result["message"]]
    
    if result["valid"]:
        parts.append("\nConfirmed:")
        for name, uuid in result["valid"]:
            parts.append(f"  - {name}")
    
    if result.get("suggestions"):
        parts.append("\nSuggestions:")
        for invalid, suggestions in result["suggestions"].items():
            parts.append(f"  - '{invalid}' -> {', '.join(suggestions)}")
    
    return "\n".join(parts)


ENTITY_TOOLS = [
    get_available_entities,
    confirm_entity,
]
