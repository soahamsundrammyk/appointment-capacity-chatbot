"""Capacity tool for fetching appointment capacity data."""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.config import KAppointmentAPIConfig
from capacity_chatbot.utils.enums import ApplicabilityRuleField, CapacityType, RuleMatchingCriteria
from capacity_chatbot.tools.validation import validate_advisor_names, validate_transport_option_names, validate_team_names
from capacity_chatbot.utils.uuid_mapper import UUIDMapper
from capacity_chatbot.utils.date_parser import parse_date_query, parse_time_query

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
    - "Loaner capacity per advisor" → Get ALL advisors first, then:
      transport_option_names=["Loaner"], advisor_names=["Vishal", "Art", "Donald", ...]
    - Response shows capacity for each advisor+loaner combination
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
        transport_option_names: List of transport option names (auto-mapped to UUIDs).
        advisor_names: List of advisor names (auto-mapped to UUIDs).
        team_names: List of team names (auto-mapped to UUIDs).
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
    """Format capacity API response into conversational summary.
    
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
    
    formatted_parts = []
    
    for capacity_type, date_map in capacity_map.items():
        type_label = "appointment" if capacity_type == "APPOINTMENT_COUNT" else "service hours"
        
        for date_key, entity_data in date_map.items():
            combo_capacity = entity_data.get("combinationWiseCapacity", {})
            if not combo_capacity:
                formatted_parts.append(f"No capacity data for {date_key}.")
                continue
            
            # Filter based on query type
            filtered = {}
            
            # Determine if user specified non-SOURCE entity filters
            user_entity_types = set(requested_entities.keys()) if requested_entities else set()
            has_non_source_filters = bool(user_entity_types - {"SOURCE"})  # e.g., OPERATION_UUID, TRANSPORT_OPTION_UUID
            
            for combo_key, cap_data in combo_capacity.items():
                # Skip SOURCE=Total always (just an aggregate)
                if combo_key == "SOURCE=Total":
                    if not has_entity_filters:
                        filtered[combo_key] = cap_data
                    continue
                
                # Skip SOURCE=DealerApp/Web when user asked about specific entities
                if combo_key.startswith("SOURCE=") and has_non_source_filters:
                    continue  # Don't show SOURCE entries when user asked about operation/advisor/etc
                
                # Check if this entry matches requested entities
                include = not requested_entities
                if requested_entities:
                    for etype, uuids in requested_entities.items():
                        if etype == "SOURCE" and has_non_source_filters:
                            continue  # Skip SOURCE matching when user has specific entity filters
                        for uuid in (uuids or []):
                            if f"{etype}={uuid}" in combo_key:
                                include = True
                                break
                        if include:
                            break
                
                if include:
                    filtered[combo_key] = cap_data
            
            # Fallback
            if requested_entities and not filtered:
                for k, v in combo_capacity.items():
                    filtered[k] = v
                    break
            
            for combo_key, cap_data in filtered.items():
                used = cap_data.get("usedCount", 0.0)
                total = cap_data.get("totalCount", float('inf'))
                limit_info = cap_data.get("limitInfo")
                
                # Build entity display name
                entity_display = ""
                if uuid_mapper:
                    for uuid, name in uuid_mapper.advisor_map.items():
                        if f"DEALER_ASSOCIATE_UUID={uuid}" in combo_key:
                            entity_display = f"for advisor {name}"
                            break
                    for uuid, name in uuid_mapper.team_map.items():
                        if f"TEAM_UUID={uuid}" in combo_key:
                            entity_display = f"for team {name}" if not entity_display else f"{entity_display} in team {name}"
                            break
                    for uuid, name in uuid_mapper.transport_map.items():
                        if f"TRANSPORT_OPTION_UUID={uuid}" in combo_key:
                            entity_display = f"for {name}" if not entity_display else f"{entity_display} with {name}"
                            break
                
                # Build summary
                if total >= 1e308:
                    formatted_parts.append(f"For {date_key} {entity_display}: unlimited capacity, {used:.0f} booked.")
                else:
                    avail = max(0, total - used)
                    formatted_parts.append(f"For {date_key} {entity_display}:\n• Total: {total:.0f}\n• Booked: {used:.0f}\n• Available: {avail:.0f}")
                
                # Add limiting factor info (using new LimitInfo structure)
                if limit_info:
                    # New structure: limitingFactor, limitValue, details, allLimits
                    limiting_factor = limit_info.get("limitingFactor", "")
                    limit_value = limit_info.get("limitValue")
                    limit_details = limit_info.get("details", "")
                    
                    if limit_value is not None and limit_value < 1e308:
                        friendly = {
                            "TRANSPORT_OPTION": "transport option limit",
                            "CAPACITY_RULE": "capacity rule",
                            "DEALER_SCHEDULE": "dealer schedule",
                            "INDIVIDUAL_SCHEDULE": "advisor schedule",
                            "OPCODE_DAILY_LIMIT": "opcode daily limit",
                            "TEAM": "team limit",
                        }.get(limiting_factor, limiting_factor.lower().replace("_", " "))
                        
                        limit_str = f"\nLimiting Factor: {friendly} ({limit_value:.0f})"
                        if limit_details:
                            limit_str += f" - {limit_details}"
                        formatted_parts.append(limit_str)
                        formatted_parts.append("\nWould you like me to explain how to increase this capacity?")
    
    return "\n".join(formatted_parts)
