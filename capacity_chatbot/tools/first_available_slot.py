"""First available slot tool for capacity chatbot."""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.config.api_config import KAppointmentAPIConfig
from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.tools.validation import (
    validate_advisor_names,
    validate_team_names,
    validate_transport_option_names,
)
from capacity_chatbot.utils.uuid_mapper import UUIDMapper

logger = logging.getLogger(__name__)


# =============================================================================
# Main Tool
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
    """Find the first available appointment slot.

    EXAMPLES:
    - "When is the first available appointment?" → no filters
    - "When can I book with Vishal?" → advisor_names=["Vishal"]
    - "First loaner appointment?" → transport_option_names=["Loaner"]

    Args:
        advisor_names: Advisor names (optional - uses all if not specified)
        team_names: Team names (optional)
        transport_option_names: Transport option names (optional)
        dates: Dates or natural language ('tomorrow', 'this week')
        start_time: Start time in HH:mm:ss format
        end_time: End time in HH:mm:ss format
        opcodes: Opcode UUIDs from search_opcode
        config: RunnableConfig (auto-provided)
    """
    state, error = _extract_state(config)
    if error:
        return error

    cached_data = state.cached_data or {}

    try:
        result = await _fetch_first_available_slot(
            department_uuid=state.department_uuid,
            advisor_names=advisor_names,
            team_names=team_names,
            transport_option_names=transport_option_names,
            dates=dates,
            start_time=start_time,
            end_time=end_time,
            opcodes=opcodes,
            cached_data=cached_data,
        )
        return result.get("formatted_summary", str(result))
    except Exception as e:
        logger.error(f"Error in get_first_available_slot_tool: {e}", exc_info=True)
        return f"Error finding first available slot: {str(e)}"


# =============================================================================
# State Extraction
# =============================================================================


def _extract_state(config: RunnableConfig) -> Tuple[Optional[CapacityChatbotState], Optional[str]]:
    """Extract and validate state from config."""
    if not config:
        return None, "Error: Config not available"

    state: CapacityChatbotState = config.get("configurable", {}).get("state")
    if not state:
        return None, "Error: State not available"

    if not state.department_uuid:
        return None, "Error: Department UUID is required. Please ensure the UI client provides this value."

    return state, None


# =============================================================================
# Entity Validation
# =============================================================================


def _validate_entities(
    advisor_names: Optional[List[str]],
    team_names: Optional[List[str]],
    transport_option_names: Optional[List[str]],
    cached_data: Dict[str, Any],
) -> Tuple[Dict[str, List[str]], Optional[str]]:
    """Validate entity names and return UUIDs."""
    uuids = {"advisor": [], "team": [], "transport": []}
    errors = []

    if advisor_names and cached_data:
        result = validate_advisor_names(advisor_names, cached_data, fuzzy_match=True)
        uuids["advisor"] = [uuid for _, uuid in result["valid"]]
        if result["invalid"]:
            errors.append(result["message"])

    if transport_option_names and cached_data:
        result = validate_transport_option_names(transport_option_names, cached_data, fuzzy_match=True)
        uuids["transport"] = [uuid for _, uuid in result["valid"]]
        if result["invalid"]:
            errors.append(result["message"])

    if team_names and cached_data:
        result = validate_team_names(team_names, cached_data, fuzzy_match=True)
        uuids["team"] = [uuid for _, uuid in result["valid"]]
        if result["invalid"]:
            errors.append(result["message"])

    if errors:
        return uuids, "Entity validation failed:\n" + "\n".join(errors)

    return uuids, None


# =============================================================================
# API Call
# =============================================================================


async def _fetch_first_available_slot(
    department_uuid: str,
    advisor_names: Optional[List[str]],
    team_names: Optional[List[str]],
    transport_option_names: Optional[List[str]],
    dates: Optional[List[str]],
    start_time: Optional[str],
    end_time: Optional[str],
    opcodes: Optional[List[str]],
    cached_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Fetch first available slot from API."""
    uuid_mapper = UUIDMapper(cached_data) if cached_data else None

    # Validate entities
    uuids, error = _validate_entities(advisor_names, team_names, transport_option_names, cached_data)
    if error:
        return {"formatted_summary": error, "raw_data": None}

    # Fallback to all advisors if none specified
    if not uuids["advisor"] and cached_data:
        advisors = cached_data.get("advisors", [])
        uuids["advisor"] = [a.get("uuid") for a in advisors if a.get("uuid")]
        if not uuids["advisor"]:
            return {"formatted_summary": "Error: At least one advisor is required.", "raw_data": None}

    # Build request
    request_payload = _build_slot_request(uuids, dates, start_time, end_time, opcodes)

    basic_auth_username = os.getenv("APPOINTMENT_CAPACITY_CHATBOT_USERNAME", "1")
    basic_auth_password = os.getenv("APPOINTMENT_CAPACITY_CHATBOT_PASSWORD", "1")

    config = KAppointmentAPIConfig(
        basic_auth_username=basic_auth_username,
        basic_auth_password=basic_auth_password,
    )
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
        return {"formatted_summary": formatted, "raw_data": result}
    finally:
        await client.close()


def _build_slot_request(
    uuids: Dict[str, List[str]],
    dates: Optional[List[str]],
    start_time: Optional[str],
    end_time: Optional[str],
    opcodes: Optional[List[str]],
) -> Dict[str, Any]:
    """Build API request payload."""
    selected_attributes = {"dealerAssociateUuidList": uuids["advisor"]}

    if uuids["team"]:
        selected_attributes["teamUuidList"] = uuids["team"]
    if uuids["transport"]:
        selected_attributes["transportOptionUuidList"] = uuids["transport"]

    request = {"selectedAvailabilityAttributes": selected_attributes}

    # Parse natural language dates - API requires exactly ONE date
    if dates:
        from capacity_chatbot.utils.date_parser import parse_date_query
        parsed = []
        for d in dates:
            parsed.extend(parse_date_query(d))
        if parsed:
            request["dates"] = [parsed[0]]

    if start_time:
        request["startTime"] = start_time
    if end_time:
        request["endTime"] = end_time
    if opcodes:
        request["selectedOperationUuidSet"] = opcodes

    return request


# =============================================================================
# Response Formatting
# =============================================================================


def _format_slot_response(
    result: Dict[str, Any],
    uuid_mapper: Optional[UUIDMapper],
    request_context: Dict[str, Any],
) -> str:
    """Format first available slot response."""
    error = result.get("error")
    if error:
        return f"Error: {error.get('errorDescription', 'Unknown error')}"

    date_time = result.get("dateTime")
    if not date_time:
        return "No available slot found within the search criteria."

    # Parse and format datetime
    try:
        dt = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
        formatted_dt = dt.strftime("%A, %B %d, %Y at %I:%M %p")
    except Exception:
        formatted_dt = date_time

    # Extract context
    requested_advisors = request_context.get("advisor_names", [])
    requested_transport = request_context.get("transport_option_names", [])
    requested_teams = request_context.get("team_names", [])
    requested_opcodes = request_context.get("opcodes", [])
    is_no_preference = len(requested_advisors) == 0

    # Extract result details
    advisor_name = _get_entity_name(result, "dealerAssociate", uuid_mapper)
    transport_name = _get_transport_name(result, uuid_mapper)
    team_name = _get_team_name(result, uuid_mapper)

    parts = []

    # Search criteria
    criteria = _build_search_criteria(requested_transport, requested_advisors, requested_teams, requested_opcodes)
    parts.append(f"**Search Criteria:** {criteria}")
    parts.append("")

    # Result
    parts.append(f"**First Available Slot:** {formatted_dt}")
    parts.append("")

    # Slot details
    parts.append("**Slot Details:**")
    if is_no_preference:
        parts.append(f"| Advisor | {advisor_name} _(auto-selected)_ |")
    else:
        parts.append(f"| Advisor | {advisor_name} |")

    if team_name:
        parts.append(f"| Team | {team_name} |")
    if transport_name:
        parts.append(f"| Transport | {transport_name} |")

    # No preference explanation
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
    suggestions = _build_suggestions(is_no_preference, requested_transport, requested_opcodes)
    if suggestions:
        parts.append(f"\nWould you like me to check availability for {suggestions}?")

    return "\n".join(parts)


def _get_entity_name(result: Dict[str, Any], key_prefix: str, uuid_mapper: Optional[UUIDMapper]) -> str:
    """Get entity name from result, using UUID mapper if available."""
    uuid = result.get(f"{key_prefix}Uuid")
    if uuid and uuid_mapper:
        name = uuid_mapper.get_advisor_name(uuid)
        if name:
            return name
    return result.get(f"{key_prefix}Name", "Available Advisor")


def _get_transport_name(result: Dict[str, Any], uuid_mapper: Optional[UUIDMapper]) -> Optional[str]:
    """Get transport option name from result."""
    uuid = result.get("transportOptionUuid")
    if uuid and uuid_mapper:
        name = uuid_mapper.get_transport_name(uuid)
        if name:
            return name
    return result.get("transportOptionName")


def _get_team_name(result: Dict[str, Any], uuid_mapper: Optional[UUIDMapper]) -> Optional[str]:
    """Get team name from result."""
    uuid = result.get("teamUuid")
    if uuid and uuid_mapper:
        return uuid_mapper.get_team_name(uuid)
    return None


def _build_search_criteria(
    transport: List[str],
    advisors: List[str],
    teams: List[str],
    opcodes: List[str],
) -> str:
    """Build search criteria string."""
    criteria = []
    if transport:
        criteria.append(f"Transport: {', '.join(transport)}")
    if advisors:
        criteria.append(f"Advisor: {', '.join(advisors)}")
    if teams:
        criteria.append(f"Team: {', '.join(teams)}")
    if opcodes:
        criteria.append(f"Service: {len(opcodes)} opcode(s)")

    return " | ".join(criteria) if criteria else "All available slots (no specific filters)"


def _build_suggestions(is_no_preference: bool, transport: List[str], opcodes: List[str]) -> str:
    """Build follow-up suggestions string."""
    suggestions = []
    if is_no_preference:
        suggestions.append("a specific advisor")
    if not transport:
        suggestions.append("a transport option")
    if not opcodes:
        suggestions.append("a specific service")

    return ", ".join(suggestions)
