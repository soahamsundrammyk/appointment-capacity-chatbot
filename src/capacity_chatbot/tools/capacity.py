"""Capacity tool for fetching appointment capacity data."""

import json
import logging
from datetime import datetime, timedelta
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
from capacity_chatbot.utils.date_parser import parse_date_query, parse_time_query
from capacity_chatbot.utils.enums import (
    ApplicabilityRuleField,
    CapacityType,
    RuleMatchingCriteria,
)
from capacity_chatbot.utils.uuid_mapper import UUIDMapper

logger = logging.getLogger(__name__)


@tool
async def get_capacity_tool(
    dates: Optional[List[str]] = None,
    transport_option_names: Optional[List[str]] = None,
    advisor_names: Optional[List[str]] = None,
    team_names: Optional[List[str]] = None,
    opcodes: Optional[List[str]] = None,
    source: Optional[str] = None,
    start_time: Optional[str] = None,
    config: RunnableConfig = None,
) -> str:
    """Fetch capacity information for appointments.

    This tool retrieves capacity data showing:
    - How many appointments are used vs available
    - Capacity broken down by advisors, transport options
    - limiting factors information when filtering by specific entities

    SIMPLE QUERY (no filters):
    - "How many slots tomorrow?" → Just call with dates, no other filters
    - Returns total capacity for the day

    FILTERED QUERY (with entities):
    - "Capacity for Loaner?" → transport_option_names=["Loaner"]
    - Returns breakdown with limiting factors info

    SOURCE FILTER (by booking channel):
    - "Online scheduler capacity" → source="Web"
    - "Dealer app capacity" → source="DealerApp"
    - Valid values: "Web" (online scheduler), "DealerApp", "DMS"

    COMBINED FILTERS (for breakdown/comparison):
    - "Loaner capacity per advisor" → transport_option_names=["Loaner"], advisor_names=["ALL"]
    - "Capacity for all teams" → team_names=["ALL"]
    - "ALL" auto-resolves to all available entities from cached data
    - Use this for "which X has most/least Y?" queries

    TIME SLOT FILTER:
    - "Capacity at 9 AM" → start_time="9 AM"
    - "Capacity at 2:30 PM" → start_time="2:30 PM"
    - "Morning capacity" → start_time="morning"
    - Formats: "9 AM", "9:30 AM", "14:00", "morning", "afternoon", "evening"

    Args:
        dates: List of dates in YYYY-MM-DD format OR natural language expressions.
               Supports: 'tomorrow', 'Thursday', 'this week', 'next week', 'next 7 days'.
               Defaults to tomorrow if not specified.
        transport_option_names: List of transport option names, or ["ALL"] to include all.
        advisor_names: List of advisor names, or ["ALL"] to include all.
        team_names: List of team names, or ["ALL"] to include all.
        opcodes: List of opcode UUIDs from search_opcode tool.
        source: Booking source filter - "Web" (online scheduler), "DealerApp", or "DMS".
        start_time: Time slot filter in natural language (e.g., '9 AM', '14:00', 'morning').
        config: RunnableConfig (automatically provided by ReAct agent)

    Returns:
        Human-readable formatted summary with capacity counts
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

    # Ensure cached_data is populated
    if not cached_data:
        from capacity_chatbot.utils.test_data import ensure_cached_data
        ensure_cached_data(state)
        cached_data = state.cached_data or {}

    # Resolve "ALL" keyword to actual entity names from cached data
    if advisor_names and len(advisor_names) == 1 and advisor_names[0].upper() == "ALL":
        advisors = cached_data.get("advisors", [])
        advisor_names = []
        for a in advisors:
            name = f"{a.get('firstName', '')} {a.get('lastName', '')}".strip()
            if not name:
                name = a.get("associateName", "") or a.get("name", "")
            if name:
                advisor_names.append(name)
        if not advisor_names:
            return "No advisors found in cached data. Cannot resolve 'ALL'."

    if team_names and len(team_names) == 1 and team_names[0].upper() == "ALL":
        teams = cached_data.get("teams", [])
        team_names = [t.get("name") for t in teams if t.get("name")]
        if not team_names:
            return "No teams found in cached data. Cannot resolve 'ALL'."

    if transport_option_names and len(transport_option_names) == 1 and transport_option_names[0].upper() == "ALL":
        options = cached_data.get("transport_options", [])
        transport_option_names = [t.get("customName") or t.get("optionName") for t in options if t.get("customName") or t.get("optionName")]
        if not transport_option_names:
            return "No transport options found in cached data. Cannot resolve 'ALL'."

    # Track if user specified filters explicitly (for simple vs filtered query logic)
    has_entity_filters = bool(transport_option_names or advisor_names or team_names or opcodes)

    # Validate and map entity names
    final_transport_uuids = []
    final_advisor_uuids = []
    final_team_uuids = []
    validation_errors = []

    if transport_option_names and cached_data:
        result = validate_transport_option_names(transport_option_names, cached_data, fuzzy_match=True)
        final_transport_uuids = [uuid for name, uuid in result["valid"]]
        if result["invalid"]:
            validation_errors.append(result["message"])

    if advisor_names and cached_data:
        result = validate_advisor_names(advisor_names, cached_data, fuzzy_match=True)
        final_advisor_uuids = [uuid for name, uuid in result["valid"]]
        if result["invalid"]:
            validation_errors.append(result["message"])

    if team_names and cached_data:
        result = validate_team_names(team_names, cached_data, fuzzy_match=True)
        final_team_uuids = [uuid for name, uuid in result["valid"]]
        if result["invalid"]:
            validation_errors.append(result["message"])

    if validation_errors:
        return "Entity validation failed:\n" + "\n".join(validation_errors)

    # Parse and validate dates
    # Now supports natural language: 'tomorrow', 'Thursday', 'this week', etc.
    today = datetime.now().date()
    parsed_dates = []

    if not dates:
        # Default to tomorrow
        parsed_dates = [(today + timedelta(days=1)).strftime("%Y-%m-%d")]
    else:
        for d in dates:
            # Try to parse as natural language first
            parsed = parse_date_query(d, reference_date=today)
            if parsed:
                parsed_dates.extend(parsed)
            else:
                # Try as YYYY-MM-DD format
                try:
                    dt = datetime.strptime(d, "%Y-%m-%d").date()
                    if dt.year >= 2024 and dt >= (today - timedelta(days=365)):
                        parsed_dates.append(d)
                except ValueError:
                    continue

        # Fallback to tomorrow if nothing parsed
        if not parsed_dates:
            parsed_dates = [(today + timedelta(days=1)).strftime("%Y-%m-%d")]

    # Remove duplicates and sort
    dates = sorted(list(set(parsed_dates)))

    # Build entity map - ALWAYS include SOURCE to prevent API validation error
    # Default sources: DealerApp and Web (covers both channels)
    entity_map = {
        "SOURCE": ["DealerApp", "Web"]
    }
    field_combinations = [["SOURCE"]]

    # Add user-specified entity filters
    if has_entity_filters:
        if final_transport_uuids:
            entity_map["TRANSPORT_OPTION_UUID"] = final_transport_uuids
            field_combinations.append(["TRANSPORT_OPTION_UUID"])

        if final_advisor_uuids:
            entity_map["DEALER_ASSOCIATE_UUID"] = final_advisor_uuids
            field_combinations.append(["DEALER_ASSOCIATE_UUID"])

        if final_team_uuids:
            entity_map["TEAM_UUID"] = final_team_uuids
            field_combinations.append(["TEAM_UUID"])

        if opcodes:
            entity_map["OPERATION_UUID"] = opcodes
            field_combinations.append(["OPERATION_UUID"])

    # Override SOURCE in entityMap when user specifies source filter
    if source:
        source_mapping = {
            "web": "Web",
            "online": "Web",
            "online scheduler": "Web",
            "dealerapp": "DealerApp",
            "dealer app": "DealerApp",
            "dms": "DMS",
        }
        mapped_source = source_mapping.get(source.lower(), source)
        entity_map["SOURCE"] = [mapped_source]  # Override default with user's choice

    # Parse time if specified
    parsed_start_time = None
    if start_time:
        parsed_start_time = parse_time_query(start_time)
        if not parsed_start_time:
            return f"Error: Could not parse time '{start_time}'. Use formats like '9 AM', '14:00', or 'morning'."

    try:
        result = await _get_capacity_impl(
            department_uuid=department_uuid,
            dates=dates,
            entity_map=entity_map,
            field_combinations=field_combinations,
            mkid=mkid,
            cached_data=cached_data,
            has_entity_filters=has_entity_filters,
            start_time=parsed_start_time,
        )

        if isinstance(result, dict) and "formatted_summary" in result:
            return result["formatted_summary"]
        return str(result)
    except Exception as e:
        logger.error(f"Error in get_capacity_tool: {e}", exc_info=True)
        return f"Error fetching capacity: {str(e)}"


async def _get_capacity_impl(
    department_uuid: str,
    dates: List[str],
    entity_map: Optional[Dict[str, List[str]]] = None,
    field_combinations: Optional[List[List[str]]] = None,
    mkid: Optional[str] = None,
    cached_data: Optional[Dict[str, Any]] = None,
    has_entity_filters: bool = False,
    start_time: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch capacity information from the API."""
    # Use DATE_AND_TIME when time is specified, otherwise DATE
    applicability_field = ApplicabilityRuleField.DATE_AND_TIME.value if start_time else ApplicabilityRuleField.DATE.value

    request_payload = {
        "applicabilityRuleField": applicability_field,
        "applicabilityFieldValues": list(set(dates)),
        "capacityTypeSet": [CapacityType.APPOINTMENT_COUNT.value],
        "ruleMatchingCriteria": RuleMatchingCriteria.EXACTLY_MATCHES.value,
        "includeLimitInfo": True,
    }

    # Add startTime if specified
    if start_time:
        request_payload["startTime"] = start_time

    if entity_map:
        request_payload["entityMap"] = {k: list(set(v)) for k, v in entity_map.items()}
    if field_combinations:
        request_payload["fieldCombinations"] = [list(set(c)) for c in field_combinations]

    logger.info(f"get_capacity API Request: {json.dumps(request_payload, indent=2)}")

    config = KAppointmentAPIConfig(mkid=mkid) if mkid else None
    client = KAppointmentAPIClient(config=config)

    try:
        result = await client.get_capacity(department_uuid, request_payload)
        uuid_mapper = UUIDMapper(cached_data) if cached_data else None
        formatted = _format_capacity_response(result, uuid_mapper, entity_map, has_entity_filters)

        return {"formatted_summary": formatted, "raw_data": result, "has_data": bool(result.get("capacityMap"))}
    except Exception as e:
        logger.error(f"Error in _get_capacity_impl: {e}")
        return {"formatted_summary": f"Error fetching capacity: {str(e)}", "raw_data": {}, "has_data": False}
    finally:
        await client.close()


def _format_capacity_response(
    api_response: Dict[str, Any],
    uuid_mapper: Optional[UUIDMapper] = None,
    requested_entities: Optional[Dict[str, List[str]]] = None,
    has_entity_filters: bool = False,
) -> str:
    """Format capacity API response into conversational summary or table.

    Args:
        api_response: Raw API response
        uuid_mapper: For mapping UUIDs to names
        requested_entities: Entity map used in request
        has_entity_filters: If True, user specified entity filters (show breakdown).
                           If False, simple query (show SOURCE=Total only).
    """
    if not api_response or "capacityMap" not in api_response:
        return "No capacity data found."

    capacity_map = api_response.get("capacityMap", {})
    if not capacity_map:
        return "No capacity data available for the requested criteria."

    # Collect all capacity entries for potential table formatting
    all_entries = []
    limiting_factors = []

    for capacity_type, date_map in capacity_map.items():

        for date_key, entity_data in date_map.items():
            combo_capacity = entity_data.get("combinationWiseCapacity", {})
            if not combo_capacity:
                continue

            # Determine if user specified non-SOURCE entity filters
            user_entity_types = set(requested_entities.keys()) if requested_entities else set()
            has_non_source_filters = bool(user_entity_types - {"SOURCE"})

            for combo_key, cap_data in combo_capacity.items():
                # Skip SOURCE=Total always (just an aggregate)
                if combo_key == "SOURCE=Total":
                    if not has_entity_filters:
                        all_entries.append((date_key, "", cap_data, combo_key))
                    continue

                # Skip SOURCE=DealerApp/Web when user asked about specific entities
                if combo_key.startswith("SOURCE=") and has_non_source_filters:
                    continue

                # Check if this entry matches requested entities
                include = not requested_entities
                if requested_entities:
                    for etype, uuids in requested_entities.items():
                        if etype == "SOURCE" and has_non_source_filters:
                            continue
                        for uuid in (uuids or []):
                            if f"{etype}={uuid}" in combo_key:
                                include = True
                                break
                        if include:
                            break

                if include:
                    # Build entity display name
                    entity_display = ""
                    if uuid_mapper:
                        for uuid, name in uuid_mapper.advisor_map.items():
                            if f"DEALER_ASSOCIATE_UUID={uuid}" in combo_key:
                                entity_display = name
                                break
                        for uuid, name in uuid_mapper.team_map.items():
                            if f"TEAM_UUID={uuid}" in combo_key:
                                entity_display = name if not entity_display else f"{entity_display} ({name})"
                                break
                        for uuid, name in uuid_mapper.transport_map.items():
                            if f"TRANSPORT_OPTION_UUID={uuid}" in combo_key:
                                entity_display = name if not entity_display else f"{entity_display} - {name}"
                                break

                    all_entries.append((date_key, entity_display, cap_data, combo_key))

                    # Collect limiting factor info
                    limit_info = cap_data.get("limitInfo")
                    if limit_info:
                        limiting_factor = limit_info.get("limitingFactor", "")
                        limit_value = limit_info.get("limitValue")
                        limit_details = limit_info.get("details", "")
                        if limit_value is not None and limit_value < 1e308:
                            limiting_factors.append((entity_display or date_key, limiting_factor, limit_value, limit_details))

    if not all_entries:
        return "No capacity data available for the requested criteria."

    # Decide format: table for multiple entries, conversational for single
    if len(all_entries) >= 3:
        # Use markdown table format
        return _format_as_table(all_entries, limiting_factors)
    else:
        # Use conversational format for 1-2 entries
        return _format_conversational(all_entries, limiting_factors)


def _format_as_table(entries: List, limiting_factors: List) -> str:
    """Format capacity entries as a markdown table."""
    # Group by date
    dates = sorted(set(e[0] for e in entries))
    has_entities = any(e[1] for e in entries)

    parts = []

    for date_key in dates:
        date_entries = [e for e in entries if e[0] == date_key]

        if has_entities:
            parts.append(f"**{date_key}**\n")
            parts.append("| Entity | Booked | Available | Total |")
            parts.append("|--------|--------|-----------|-------|")

            for _, entity, cap_data, _ in date_entries:
                used = int(cap_data.get("usedCount", 0))
                total = cap_data.get("totalCount", float('inf'))
                if total >= 1e308:
                    total_str = "∞"
                    avail_str = "∞"
                else:
                    total_str = str(int(total))
                    avail_str = str(max(0, int(total) - used))

                entity_name = entity if entity else "Total"
                parts.append(f"| {entity_name} | {used} | {avail_str} | {total_str} |")
            parts.append("")
        else:
            # Single total entry
            cap_data = date_entries[0][2]
            used = int(cap_data.get("usedCount", 0))
            total = cap_data.get("totalCount", float('inf'))
            if total >= 1e308:
                parts.append(f"**{date_key}**: Unlimited capacity, {used} booked.")
            else:
                avail = max(0, int(total) - used)
                parts.append(f"**{date_key}**: {avail} available ({used}/{int(total)} booked)")

    # Add limiting factors if any
    if limiting_factors:
        parts.append("\n**Limiting Factors:**")
        friendly_names = {
            "TRANSPORT_OPTION": "transport option limit",
            "CAPACITY_RULE": "capacity rule",
            "DEALER_SCHEDULE": "dealer schedule",
            "INDIVIDUAL_SCHEDULE": "advisor schedule",
            "OPCODE_DAILY_LIMIT": "opcode daily limit",
            "TEAM": "team limit",
        }
        seen = set()
        for entity, factor, value, details in limiting_factors:
            friendly = friendly_names.get(factor, factor.lower().replace("_", " "))
            key = (entity, factor, value)
            if key not in seen:
                seen.add(key)
                detail_str = f" - {details}" if details else ""
                parts.append(f"- {entity}: {friendly} ({int(value)}){detail_str}")

        parts.append("\nWould you like me to explain how to increase any of these?")

    return "\n".join(parts)


def _format_conversational(entries: List, limiting_factors: List) -> str:
    """Format capacity entries in conversational style for 1-2 entries."""
    parts = []

    for date_key, entity, cap_data, _ in entries:
        used = cap_data.get("usedCount", 0.0)
        total = cap_data.get("totalCount", float('inf'))

        entity_str = f" for {entity}" if entity else ""

        if total >= 1e308:
            parts.append(f"For {date_key}{entity_str}: unlimited capacity, {int(used)} booked.")
        else:
            avail = max(0, total - used)
            parts.append(f"For {date_key}{entity_str}:\n• Total: {int(total)}\n• Booked: {int(used)}\n• Available: {int(avail)}")

    # Add limiting factors
    if limiting_factors:
        friendly_names = {
            "TRANSPORT_OPTION": "transport option limit",
            "CAPACITY_RULE": "capacity rule",
            "DEALER_SCHEDULE": "dealer schedule",
            "INDIVIDUAL_SCHEDULE": "advisor schedule",
            "OPCODE_DAILY_LIMIT": "opcode daily limit",
            "TEAM": "team limit",
        }
        for entity, factor, value, details in limiting_factors:
            friendly = friendly_names.get(factor, factor.lower().replace("_", " "))
            detail_str = f" - {details}" if details else ""
            parts.append(f"\nLimiting Factor: {friendly} ({int(value)}){detail_str}")
        parts.append("\nWould you like me to explain how to increase this capacity?")

    return "\n".join(parts)

