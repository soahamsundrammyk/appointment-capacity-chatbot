"""Knowledge base tools for ReAct agent.

These tools provide access to the knowledge base and cached entity data
without embedding them in the system prompt.
"""

import logging
from typing import Optional

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.knowledge_base import get_relevant_knowledge, COMMON_QUESTIONS
from capacity_chatbot.utils.uuid_mapper import UUIDMapper

logger = logging.getLogger(__name__)


@tool
async def get_knowledge_answer(
    query: str,
    config: RunnableConfig = None,
) -> str:
    """Search the knowledge base for answers to conceptual questions.
    
    Use this tool FIRST when the user asks conceptual questions like:
    - "What is capacity?"
    - "How do capacity rules work?"
    - "What is a transport option?"
    - "How do I increase transport option capacity?"
    - "How do I increase dealer schedule capacity?"
    
    This tool does NOT make API calls - it retrieves answers from the knowledge base.
    For current data (e.g., "what's the capacity for tomorrow?"), use other tools.
    
    Args:
        query: The user's question or query text
        config: RunnableConfig (automatically provided by ReAct agent)
    
    Returns:
        Relevant knowledge base content matching the query
    """
    if not query:
        return "Please provide a question to search the knowledge base."
    
    logger.info(f"get_knowledge_answer called with query: {query}")
    
    # Use the existing get_relevant_knowledge function for keyword matching
    relevant_knowledge = get_relevant_knowledge(query, max_items=3)
    
    if relevant_knowledge:
        return relevant_knowledge
    
    # Fallback: provide a list of topics the knowledge base covers
    return """I couldn't find a specific answer in the knowledge base for your question.

The knowledge base covers these topics:
- What is capacity?
- How do capacity rules work?
- What is a transport option?
- What is a team?
- How to increase transport option capacity
- How to increase capacity rule limits
- How to increase dealer schedule capacity
- How to increase individual advisor capacity
- How to increase operation/opcode capacity

Try rephrasing your question with these keywords."""


@tool
async def get_available_entities(
    entity_type: str,
    config: RunnableConfig = None,
) -> str:
    """Get available transport options, advisors, or teams from cached data.
    
    Use this tool when the user asks:
    - "What transport options are available?"
    - "List all advisors"
    - "What teams are there?"
    - "Show me the available transport options"
    
    This tool retrieves data from cache - no API calls needed.
    
    Args:
        entity_type: One of 'transport_options', 'advisors', or 'teams'
        config: RunnableConfig containing state (automatically provided by ReAct agent)
    
    Returns:
        Formatted list of available entities
    """
    if not config:
        return "Error: Config not available"
    
    state: CapacityChatbotState = config.get("configurable", {}).get("state")
    
    if not state:
        return "Error: State not available"
    
    cached_data = state.cached_data or {}
    
    # Ensure cached_data is available
    if not cached_data:
        from capacity_chatbot.utils.test_data import ensure_cached_data
        ensure_cached_data(state)
        cached_data = state.cached_data or {}
    
    if not cached_data:
        return "No cached data available. Please ensure the department is properly configured."
    
    entity_type_lower = entity_type.lower().strip()
    
    # Handle transport options
    if entity_type_lower in ["transport_options", "transport", "transportation"]:
        transport_options = cached_data.get("transport_options", [])
        if not transport_options:
            return "No transport options found in cached data."
        
        names = []
        for t in transport_options:
            name = t.get("customName") or t.get("optionName", "")
            if name:
                names.append(name)
        
        if names:
            return f"Available transport options ({len(names)}):\n" + "\n".join(f"- {name}" for name in names)
        return "No transport options found."
    
    # Handle advisors
    elif entity_type_lower in ["advisors", "advisor", "service_advisors"]:
        advisors = cached_data.get("advisors", [])
        if not advisors:
            return "No advisors found in cached data."
        
        names = []
        for a in advisors:
            name = a.get("nickname") or f"{a.get('firstName', '')} {a.get('lastName', '')}".strip()
            if name:
                names.append(name)
        
        if names:
            return f"Available advisors ({len(names)}):\n" + "\n".join(f"- {name}" for name in names)
        return "No advisors found."
    
    # Handle teams
    elif entity_type_lower in ["teams", "team"]:
        teams = cached_data.get("teams", [])
        if not teams:
            return "No teams found in cached data."
        
        uuid_mapper = UUIDMapper(cached_data)
        team_details = []
        
        for team in teams:
            team_name = team.get("name", "Unknown Team")
            advisor_uuids = team.get("dealerAssociateUuids", [])
            
            advisor_names = []
            for uuid in advisor_uuids:
                name = uuid_mapper.get_advisor_name(uuid)
                if name and name != uuid:  # Don't show UUID if name not found
                    advisor_names.append(name)
            
            if advisor_names:
                team_details.append(f"- {team_name}: {', '.join(advisor_names)}")
            else:
                team_details.append(f"- {team_name}: (no advisors assigned)")
        
        if team_details:
            return f"Available teams ({len(teams)}):\n" + "\n".join(team_details)
        return "No teams found."
    
    else:
        return f"""Invalid entity type: '{entity_type}'

Valid entity types:
- 'transport_options' - List available transport options (Loaner, Shuttle, etc.)
- 'advisors' - List available service advisors
- 'teams' - List available teams with their advisors"""


# List of knowledge base tools
KNOWLEDGE_BASE_TOOLS = [
    get_knowledge_answer,
    get_available_entities,
]
