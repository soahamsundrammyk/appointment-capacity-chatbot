"""Simple node that calls the get_rules tool directly."""

import logging
import os
import asyncio

from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.tools import get_rules_tool_impl

logger = logging.getLogger(__name__)


def call_rules_tool(state: CapacityChatbotState) -> CapacityChatbotState:
    """Call the get_rules tool to fetch rules for the department.
    
    This is a simple node that directly calls the tool without LLM tool calling.
    Use this for testing or when you know you need to fetch rules.
    """
    # Get department_uuid
    department_uuid = state.department_uuid
    if not department_uuid:
        # Try to get from env as fallback
        department_uuid = os.getenv("DEFAULT_DEPARTMENT_UUID")
        if department_uuid:
            state.department_uuid = department_uuid
            logger.info(f"Using default department_uuid from env: {department_uuid}")
        else:
            state.errors.append("Department UUID is required for fetching rules")
            return state
    
    try:
        # Call the tool
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Call with default parameters
        result = loop.run_until_complete(
            get_rules_tool_impl(
                department_uuid=department_uuid,
                dealer_uuid_list=[],
                result_size=100,
                start_position=0,
                rule_status_list=["ACTIVE"],
                rule_type_list=["CAPACITY"]
            )
        )
        
        # Store result in state
        state.rules_data = result
        state.reasoning.append(
            f"Successfully fetched {result.get('totalCount', 0)} rules"
        )
        logger.info(f"Fetched {result.get('totalCount', 0)} rules")
        
        # Format rules for response
        rule_list = result.get("ruleList", [])
        if rule_list:
            rules_summary = f"Found {len(rule_list)} active capacity rules:\n\n"
            for i, rule in enumerate(rule_list, 1):
                rules_summary += f"{i}. {rule.get('ruleName', 'Unnamed')}\n"
                rules_summary += f"   If: {rule.get('ifVerbiage', 'N/A')}\n"
                rules_summary += f"   Then: {rule.get('thenVerbiage', 'N/A')}\n\n"
            state.response_message = rules_summary
        else:
            state.response_message = "No active capacity rules found for this department."
        
    except Exception as e:
        logger.error(f"Error calling get_rules tool: {e}")
        state.errors.append(f"Error fetching rules: {str(e)}")
        state.response_message = f"I encountered an error while fetching rules: {str(e)}"
    
    return state

