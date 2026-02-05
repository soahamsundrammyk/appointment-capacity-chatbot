"""First available slot tool for capacity chatbot.

This module contains everything related to the get_first_available_slot tool.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.config import KAppointmentAPIConfig
from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.tools.validation import (
    validate_advisor_names,
    validate_team_names,
    validate_transport_option_names,
)
from capacity_chatbot.utils.uuid_mapper import UUIDMapper

logger = logging.getLogger(__name__)


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
    - If multiple dates provided, uses the first date as the start date
    - If no dates specified, API defaults to today and searches forward up to 90 days

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

    # Parse natural language dates using date_parser
    # NOTE: first-available-slot API requires exactly ONE date (or none to default to today)
    # The API will search forward from the start date for up to 90 days
    if dates:
        from capacity_chatbot.utils.date_parser import parse_date_query
        parsed_dates = []
        for d in dates:
            parsed = parse_date_query(d)
            parsed_dates.extend(parsed)
        if parsed_dates:
            # Take only the first date - API requires exactly one date as start date
            request_payload["dates"] = [parsed_dates[0]]
    # If no dates specified, don't send dates - API will default to today

    if start_time:
        request_payload["startTime"] = start_time
    if end_time:
        request_payload["endTime"] = end_time
    if opcodes:
        request_payload["selectedOperationUuidSet"] = opcodes

    basic_auth_username = os.getenv("APPOINTMENT_CAPACITY_CHATBOT_USERNAME", "1")
    basic_auth_password = os.getenv("APPOINTMENT_CAPACITY_CHATBOT_PASSWORD", "1")

    config = KAppointmentAPIConfig(mkid=mkid, basic_auth_username=basic_auth_username, basic_auth_password=basic_auth_password)
    client = KAppointmentAPIClient(config=config)

    try:
        result = await client.get_first_available_slot(department_uuid, request_payload)
        request_context = {
            "transport_option_names": transport_option_names or [],
            "advisor_names": advisor_names or [],
            "team_names": team_names or [],
            "opcodes": opcodes or [],
        }
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
    """Format first available slot response with full context.
    
    Shows:
    1. Search criteria used (what the user asked for)
    2. The first available slot found
    3. Whether "No Preference" was used for advisor selection
    """
    error = result.get("error")
    if error:
        return f"Error: {error.get('errorDescription', 'Unknown error')}"

    date_time = result.get("dateTime")
    if not date_time:
        return "No available slot found within the search criteria."

    # Parse and format the datetime
    try:
        dt = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
        formatted_dt = dt.strftime("%A, %B %d, %Y at %I:%M %p")
    except:
        formatted_dt = date_time

    # Extract request context
    requested_advisors = request_context.get("advisor_names", []) if request_context else []
    requested_transport = request_context.get("transport_option_names", []) if request_context else []
    requested_opcodes = request_context.get("opcodes", []) if request_context else []
    requested_teams = request_context.get("team_names", []) if request_context else []

    # Determine if "No Preference" was used (no specific advisor requested)
    is_no_preference = len(requested_advisors) == 0

    # Get result details
    advisor_uuid = result.get("dealerAssociateUuid")
    advisor_name = None
    if advisor_uuid and uuid_mapper:
        advisor_name = uuid_mapper.get_advisor_name(advisor_uuid)
    if not advisor_name:
        advisor_name = result.get("dealerAssociateName", "Available Advisor")

    transport_uuid = result.get("transportOptionUuid")
    transport_name = None
    if transport_uuid and uuid_mapper:
        transport_name = uuid_mapper.get_transport_name(transport_uuid)
    if not transport_name:
        transport_name = result.get("transportOptionName")

    team_uuid = result.get("teamUuid")
    team_name = None
    if team_uuid and uuid_mapper:
        team_name = uuid_mapper.get_team_name(team_uuid)

    # Build response
    parts = []

    # 1. Show search criteria
    search_criteria = []
    if requested_transport:
        search_criteria.append(f"Transport: {', '.join(requested_transport)}")
    if requested_advisors:
        search_criteria.append(f"Advisor: {', '.join(requested_advisors)}")
    if requested_teams:
        search_criteria.append(f"Team: {', '.join(requested_teams)}")
    if requested_opcodes:
        search_criteria.append(f"Service: {len(requested_opcodes)} opcode(s)")

    if search_criteria:
        parts.append(f"**Search Criteria:** {' | '.join(search_criteria)}")
    else:
        parts.append("**Search Criteria:** All available slots (no specific filters)")

    parts.append("")

    # 2. Show the result
    parts.append(f"**First Available Slot:** {formatted_dt}")
    parts.append("")

    # 3. Show slot details in a clear format
    parts.append("**Slot Details:**")

    # Advisor with No Preference indicator
    if is_no_preference:
        parts.append(f"| Advisor | {advisor_name} _(auto-selected based on availability)_ |")
    else:
        parts.append(f"| Advisor | {advisor_name} |")

    if team_name:
        parts.append(f"| Team | {team_name} |")

    if transport_name:
        parts.append(f"| Transport | {transport_name} |")

    # 4. Explain No Preference if used
    if is_no_preference:
        parts.append("")
        parts.append("ℹ️ _No specific advisor was requested. The system selected the advisor with the earliest available slot._")

    # Warnings
    warnings = result.get("warnings", [])
    if warnings:
        descs = [w.get("warningDescription", "") for w in warnings if w.get("warningDescription")]
        if descs:
            parts.append(f"\n⚠️ Note: {', '.join(descs)}")

    # Follow-up suggestions
    suggestions = []
    if is_no_preference:
        suggestions.append("a specific advisor")
    if not requested_transport:
        suggestions.append("a transport option")
    if not requested_opcodes:
        suggestions.append("a specific service")

    if suggestions:
        parts.append(f"\nWould you like me to check availability for {', '.join(suggestions)}?")

    return "\n".join(parts)


