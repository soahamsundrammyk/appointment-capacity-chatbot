"""Capacity agent node using ReAct architecture.

This node uses create_react_agent from langgraph.prebuilt to let the LLM
decide which tools to call based on conversation context. This replaces
the previous 3-LLM-call approach (message_parse + tool_calling_node) with
a single ReAct agent call.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.tools.capacity_tools import CAPACITY_TOOLS
from capacity_chatbot.prompts import get_capacity_agent_system_prompt_minimal
from capacity_chatbot.utils.uuid_mapper import UUIDMapper
from capacity_chatbot.utils.test_data import ensure_cached_data

logger = logging.getLogger(__name__)

RECURSION_LIMIT = 12
ERROR_MESSAGE = "I apologize, but something went wrong. Please contact the dealership directly and the team will help you out."


def _format_cached_data(state: CapacityChatbotState) -> Optional[str]:
    """Format cached data (advisors, teams, transport options) for the agent prompt.
    
    Args:
        state: Current capacity chatbot state
        
    Returns:
        Formatted string with cached data info, or None if no cached data
    """
    if not state.cached_data:
        return None
    
    cached_info_parts = []
    
    # Transport options
    transport_options = state.cached_data.get("transport_options", [])
    if transport_options:
        transport_names = [t.get("customName") or t.get("optionName", "") for t in transport_options]
        cached_info_parts.append("=== TRANSPORT OPTIONS (for customer transportation) ===")
        cached_info_parts.append(f"{', '.join(transport_names)}")
    
    # Advisors
    advisors = state.cached_data.get("advisors", [])
    if advisors:
        advisor_names = [a.get("nickname") or f"{a.get('firstName', '')} {a.get('lastName', '')}".strip() for a in advisors]
        cached_info_parts.append("\n=== ADVISORS (service advisors) ===")
        cached_info_parts.append(f"{', '.join(advisor_names)}")
    
    # Teams
    teams = state.cached_data.get("teams", [])
    if teams:
        cached_info_parts.append("\n=== TEAMS (groups of advisors) ===")
        team_details = []
        uuid_mapper = UUIDMapper(state.cached_data)
        for team in teams:
            team_name = team.get("name", "")
            advisor_uuids = team.get("dealerAssociateUuids", [])
            advisor_names_in_team = [uuid_mapper.get_advisor_name(uuid) for uuid in advisor_uuids if uuid_mapper.get_advisor_name(uuid) != uuid]
            if advisor_names_in_team:
                team_details.append(f"  - {team_name}: {', '.join(advisor_names_in_team)}")
            else:
                team_details.append(f"  - {team_name}: (no advisors)")
        
        if team_details:
            cached_info_parts.append("\n".join(team_details))
    
    return "\n".join(cached_info_parts) if cached_info_parts else None


def _create_agent_config(state: CapacityChatbotState, config: Optional[RunnableConfig]) -> Dict:
    """Create a safe config dict for the agent with state.
    
    Args:
        state: Current capacity chatbot state
        config: Optional runnable config from LangGraph
        
    Returns:
        Dictionary with configurable state and recursion limit
    """
    safe_config = {}
    
    if config:
        for key in ["thread_id", "checkpoint_ns", "checkpoint_id"]:
            if config.get("configurable", {}).get(key):
                safe_config[key] = config["configurable"][key]
    
    # Pass state to tools via config
    safe_config["state"] = state
    
    # Add tags and metadata for LangSmith tracking
    model_name = os.getenv("MODEL", "gpt-4o-mini")
    prompt_version = os.getenv("PROMPT_VERSION", "v1")
    
    tags = [
        "approach:react",
        f"model:{model_name}",
        f"prompt:{prompt_version}",
        "version:v1.0",
    ]
    
    metadata = {
        "state": state,
        "model": model_name,
        "approach": "react",
        "prompt_version": prompt_version,
        "recursion_limit": RECURSION_LIMIT,
        "timestamp": datetime.now().isoformat(),
    }
    
    return {
        "configurable": safe_config,
        "recursion_limit": RECURSION_LIMIT,
        "tags": tags,
        "metadata": metadata,
    }


def _load_model():
    """Load the default chat model.
    
    Returns:
        ChatOpenAI model instance
    """
    model_name = os.getenv("MODEL", "gpt-4o-mini")
    return ChatOpenAI(model=model_name, temperature=0)


async def capacity_agent(
    state: CapacityChatbotState,
    config: Optional[RunnableConfig] = None,
) -> Dict[str, Any]:
    """ReAct capacity agent that uses tools to answer capacity-related queries.
    
    This replaces the previous 3-LLM-call approach:
    - OLD: message_parse (LLM #1) → tool_calling_node (LLM #2) → tool_calling_node (LLM #3)
    - NEW: capacity_agent (ReAct - single LLM call with reasoning loop)
    
    The LLM decides which tools to call based on conversation and state.
    Tools access state via config["configurable"]["state"].
    
    Args:
        state: Current capacity chatbot state
        config: Optional runnable config from LangGraph
        
    Returns:
        State updates including assistant message and any tool results
    """
    logger.info("Capacity agent invoked (ReAct mode)")
    
    # Ensure cached_data is available (load test data if needed for dev/testing)
    ensure_cached_data(state)
    
    # Get department_uuid (required for tools)
    department_uuid = state.department_uuid
    if not department_uuid:
        department_uuid = os.getenv("DEFAULT_DEPARTMENT_UUID")
        if department_uuid:
            state.department_uuid = department_uuid
            logger.info(f"Using default department_uuid from env: {department_uuid}")
        else:
            error_msg = "Department UUID is required for tool calls"
            logger.error(error_msg)
            return {
                "assistant_message": "I need a department UUID to help you. Please provide one.",
                "messages": [AIMessage(content="I need a department UUID to help you. Please provide one.")],
                "errors": [error_msg],
            }
    
    # Get the latest user message
    user_messages = [msg for msg in state.messages if isinstance(msg, HumanMessage)]
    if not user_messages:
        error_msg = "No user message found"
        logger.error(error_msg)
        return {
            "assistant_message": "I didn't receive your message. Please try again.",
            "messages": [AIMessage(content="I didn't receive your message. Please try again.")],
            "errors": [error_msg],
        }
    
    try:
        # Load model
        model = _load_model()
        
        # Get current time (for context)
        current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        
        # Build minimal system prompt
        # Knowledge base and cached data are now accessed via tools:
        # - get_knowledge_answer: For conceptual questions
        # - get_available_entities: For listing transport options/advisors/teams
        system_prompt = get_capacity_agent_system_prompt_minimal(current_time=current_time)
        
        # Create ReAct agent
        agent = create_react_agent(
            model,
            tools=CAPACITY_TOOLS,
            prompt=system_prompt
        )
        
        # Prepare agent input (messages)
        agent_input = {"messages": list(state.messages)}
        
        # Create agent config with state, tags, and metadata for LangSmith
        agent_config = _create_agent_config(state, config)
        
        # Invoke the agent (single LLM call with ReAct loop)
        result = await agent.ainvoke(agent_input, config=agent_config)
        
        # Extract final response
        final_message = result["messages"][-1].content
        
        # Build response
        response: Dict[str, Any] = {
            "assistant_message": final_message,
            "messages": [AIMessage(content=final_message)],
            "response_message": final_message,
        }
        
        # Update state fields that tools may have modified
        # (tools can update state directly via config, but we also return them for persistence)
        if state.rules_data:
            response["rules_data"] = state.rules_data
        if state.capacity_data:
            response["capacity_data"] = state.capacity_data
        if state.first_available_slot_data:
            response["first_available_slot_data"] = state.first_available_slot_data
        
        return response
        
    except Exception as e:
        logger.error(f"Capacity agent error: {e}", exc_info=True)
        error_message = ERROR_MESSAGE
        return {
            "assistant_message": error_message,
            "messages": [AIMessage(content=error_message)],
            "response_message": error_message,
            "errors": [str(e)],
        }
