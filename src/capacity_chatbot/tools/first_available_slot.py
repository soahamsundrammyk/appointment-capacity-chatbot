"""First available slot tool for capacity chatbot.

This module contains everything related to the get_first_available_slot tool.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.config import KAppointmentAPIConfig
from capacity_chatbot.tools.validation import (
    validate_advisor_names,
    validate_transport_option_names,
    validate_team_names
)
from capacity_chatbot.utils.uuid_mapper import UUIDMapper

logger = logging.getLogger(__name__)


# =============================================================================
# Tool Wrapper
# =============================================================================

@tool
async def get_first_available_slot_tool(
    advisor_names: Optional[List[str]] = None,
    team_names: Optional[List[str]] = None,
    transport_option_names: Optional[List[str]] = None,
    dates: Optional[List[str]] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    opcodes: Optional[List[str]] = None,
    config: RunnableConfig = None,
) -> str:
    """Find the first available appointment slot based on selected criteria.
    
    Use this tool when user asks about appointment availability:
    
    EXAMPLES:
    - "When is the first available appointment?" → call with no filters
    - "When can I book with Vishal?" → advisor_names=["Vishal"]
    - "First available loaner appointment?" → transport_option_names=["Loaner"]
    - "Next slot for Express Shop?" → team_names=["Express Shop"]
    - "First available for oil change with loaner?" → Use search_opcode first, then call with opcodes + transport_option_names
    
    COMBINING FILTERS:
    - Can combine advisor + transport: advisor_names=["Vishal"], transport_option_names=["Loaner"]
    - Can combine team + transport: team_names=["Main Shop"], transport_option_names=["Drop Off"]
    
    DATE SUPPORT:
    - Supports natural language: 'tomorrow', 'Thursday', 'this week', 'next week'
    - Defaults to next 7 days if not specified
    
    Args:
        advisor_names: List of advisor names (optional - all advisors if not specified)
        team_names: List of team names (optional)
        transport_option_names: List of transport option names (optional)
        dates: List of dates or natural language ('tomorrow', 'this week')
        start_time: Start time in HH:mm:ss format (optional, defaults to business hours)
        end_time: End time in HH:mm:ss format (optional, defaults to business hours)
        opcodes: List of opcode UUIDs from search_opcode (optional)
        config: RunnableConfig (automatically provided by ReAct agent)
    
    Returns:
        First available slot with date, time, and advisor name
    """
    if not config:
        return "Error: Config not available"
    
    state: CapacityChatbotState = config.get("configurable", {}).get("state")
    if not state:
        return "Error: State not available"
    
    # UUIDs must come from UI client via state - no env var fallbacks
    department_uuid = state.department_uuid
    if not department_uuid:
        return "Error: Department UUID is required. Please ensure the UI client provides this value."
    
    mkid = state.mkid
    cached_data = state.cached_data or {}
    
    try:
        result = await _get_first_available_slot_impl(
            department_uuid=department_uuid,
            advisor_names=advisor_names,
            team_names=team_names,
            transport_option_names=transport_option_names,
            dates=dates,
            start_time=start_time,
            end_time=end_time,
            opcodes=opcodes,
            mkid=mkid,
            cached_data=cached_data,
        )
        
        if isinstance(result, dict) and "formatted_summary" in result:
            return result["formatted_summary"]
        return str(result)
    except Exception as e:
        logger.error(f"Error in get_first_available_slot_tool: {e}", exc_info=True)
        return f"Error finding first available slot: {str(e)}"


# =============================================================================
# Implementation
# =============================================================================

async def _get_first_available_slot_impl(
    department_uuid: str,
    advisor_names: Optional[List[str]] = None,
    team_names: Optional[List[str]] = None,
    transport_option_names: Optional[List[str]] = None,
    dates: Optional[List[str]] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    opcodes: Optional[List[str]] = None,
    mkid: Optional[str] = None,
    cached_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Find the first available appointment slot."""
    uuid_mapper = UUIDMapper(cached_data) if cached_data else None
    
    # Validate entities
    advisor_uuids = []
    transport_uuids = []
    team_uuids = []
    validation_errors = []
    
    if advisor_names and cached_data:
        result = validate_advisor_names(advisor_names, cached_data, fuzzy_match=True)
        advisor_uuids = [uuid for name, uuid in result["valid"]]
        if result["invalid"]:
            validation_errors.append(result["message"])
    
    if transport_option_names and cached_data:
        result = validate_transport_option_names(transport_option_names, cached_data, fuzzy_match=True)
        transport_uuids = [uuid for name, uuid in result["valid"]]
        if result["invalid"]:
            validation_errors.append(result["message"])
    
    if team_names and cached_data:
        result = validate_team_names(team_names, cached_data, fuzzy_match=True)
        team_uuids = [uuid for name, uuid in result["valid"]]
        if result["invalid"]:
            validation_errors.append(result["message"])
    
    if validation_errors:
        return {"formatted_summary": "Entity validation failed:\n" + "\n".join(validation_errors), "raw_data": None, "has_data": False}
    
    # Fallback to all advisors if none specified
    if not advisor_uuids and cached_data:
        advisors = cached_data.get("advisors", [])
        advisor_uuids = [a.get("uuid") for a in advisors if a.get("uuid")]
        if not advisor_uuids:
            return {"formatted_summary": "Error: At least one advisor is required.", "raw_data": None, "has_data": False}
    
    # Build request
    selected_attributes = {"dealerAssociateUuidList": advisor_uuids}
    if team_uuids:
        selected_attributes["teamUuidList"] = team_uuids
    if transport_uuids:
        selected_attributes["transportOptionUuidList"] = transport_uuids
    
    request_payload = {"selectedAvailabilityAttributes": selected_attributes}
    if dates:
        request_payload["dates"] = dates
    if start_time:
        request_payload["startTime"] = start_time
    if end_time:
        request_payload["endTime"] = end_time
    if opcodes:
        request_payload["selectedOperationUuidSet"] = opcodes
    
    basic_auth_username = os.getenv("KAPPOINTMENT_API_USERNAME", "1")
    basic_auth_password = os.getenv("KAPPOINTMENT_API_PASSWORD", "1")
    
    config = KAppointmentAPIConfig(mkid=mkid, basic_auth_username=basic_auth_username, basic_auth_password=basic_auth_password)
    client = KAppointmentAPIClient(config=config)
    
    try:
        result = await client.get_first_available_slot(department_uuid, request_payload)
        request_context = {"transport_option_names": transport_option_names or [], "advisor_names": advisor_names or [], "opcodes": opcodes or []}
        formatted = _format_slot_response(result, uuid_mapper, request_context)
        
        return {"formatted_summary": formatted, "raw_data": result, "has_data": bool(result.get("dateTime"))}
    except Exception as e:
        logger.error(f"Error in _get_first_available_slot_impl: {e}")
        return {"formatted_summary": f"Error: {str(e)}", "raw_data": None, "has_data": False}
    finally:
        await client.close()


# =============================================================================
# Formatters
# =============================================================================

def _format_slot_response(result: Dict[str, Any], uuid_mapper: Optional[UUIDMapper] = None, request_context: Optional[Dict[str, Any]] = None) -> str:
    """Format first available slot response."""
    error = result.get("error")
    if error:
        return f"Error: {error.get('errorDescription', 'Unknown error')}"
    
    date_time = result.get("dateTime")
    if not date_time:
        return "No available slot found within the search criteria."
    
    try:
        dt = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
        formatted_dt = dt.strftime("%B %d, %Y at %I:%M %p")
    except:
        formatted_dt = date_time
    
    formatted = f"First available slot: {formatted_dt}"
    
    warnings = result.get("warnings", [])
    if warnings:
        descs = [w.get("warningDescription", "") for w in warnings if w.get("warningDescription")]
        if descs:
            formatted += f"\n\nNote: {', '.join(descs)}"
    
    # Add follow-up suggestions
    if request_context:
        has_transport = bool(request_context.get("transport_option_names"))
        has_opcode = bool(request_context.get("opcodes"))
        has_advisor = bool(request_context.get("advisor_names"))
        
        if has_transport and not has_opcode and not has_advisor:
            formatted += "\n\nWould you like me to narrow this down to a specific advisor or service?"
        elif has_opcode and not has_transport and not has_advisor:
            formatted += "\n\nWould you like me to narrow this down to a specific advisor or transport option?"
        elif has_advisor and not has_transport and not has_opcode:
            formatted += "\n\nWould you like me to narrow this down to a specific transport option or service?"
    
    return formatted
