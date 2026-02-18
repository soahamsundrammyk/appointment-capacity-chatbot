"""Capacity tool for fetching appointment capacity data."""

import logging
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.config.api_config import KAppointmentAPIConfig
from capacity_chatbot.tools.validation import (
    _extract_advisor_name,
    _extract_team_name,
    _extract_transport_name,
    validate_advisor_names,
    validate_team_names,
    validate_transport_option_names,
)
from capacity_chatbot.utils.date_parser import parse_date_query, parse_time_query
from capacity_chatbot.utils.state_extractor import extract_state
from capacity_chatbot.enums import (
    ApplicabilityRuleField,
    CapacityType,
    LimitingFactor,
    RuleMatchingCriteria,
    SourceType,
)
from capacity_chatbot.utils.uuid_mapper import UUIDMapper
from capacity_chatbot.model.requests import EntityFilterRequest, GetCapacityRequest

logger = logging.getLogger(__name__)
UNLIMITED_CAPACITY = 1e308  # Represents unlimited capacity in API responses
MIN_YEAR = 2024  # Minimum year for date validation

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
    - Limiting factors information when filtering by specific entities

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
    # Extract state and validate
    state, error = extract_state(config)
    if error:
        return error

    cached_data = state.cached_data or {}
    if not cached_data:
        from capacity_chatbot.utils.test_data import ensure_cached_data
        ensure_cached_data(state)
        cached_data = state.cached_data or {}

    # Create request model
    request = EntityFilterRequest(
        dates=dates,
        transport_option_names=transport_option_names,
        advisor_names=advisor_names,
        team_names=team_names,
        opcodes=opcodes,
        source=source,
        start_time=start_time,
    )

    # Prepare request (resolve ALL, validate, parse)
    prepared, error = _prepare_capacity_request(request, cached_data)
    if error:
        return error

    try:
        result = await _fetch_capacity(
            department_uuid=state.department_uuid,
            request=prepared,
            cached_data=cached_data,
        )
        return result.get("formatted_summary", str(result))
    except Exception as e:
        logger.error("Error in get_capacity_tool: %s", e, exc_info=True)
        return "Error fetching capacity: %s" % str(e)


def _prepare_capacity_request(
    request: EntityFilterRequest,
    cached_data: Dict[str, Any],
) -> Tuple[Optional[GetCapacityRequest], Optional[str]]:
    """Prepare and validate capacity request.
    
    Returns:
        Tuple of (GetCapacityRequest, error_string)
    """
    # Resolve "ALL" keywords
    advisor_names, team_names, transport_option_names, err = _resolve_all_keywords(
        request.advisor_names,
        request.team_names,
        request.transport_option_names,
        cached_data,
    )
    if err:
        return None, err

    has_entity_filters = bool(transport_option_names or advisor_names or team_names or request.opcodes)

    # Validate entity names and get UUIDs
    uuids, validation_error = _validate_entities(
        advisor_names, team_names, transport_option_names, cached_data
    )
    if validation_error:
        return None, validation_error

    # Parse dates with fallback to tomorrow
    parsed_dates = _parse_dates(request.dates)

    # Parse source
    parsed_source = _parse_source(request.source)

    # Build entity map for API
    entity_map, field_combinations = _build_entity_map(
        uuids, request.opcodes, parsed_source
    )

    # Parse time filter
    parsed_time = None
    if request.start_time:
        parsed_time = parse_time_query(request.start_time)
        if not parsed_time:
            return None, "Error: Could not parse time '%s'. Use '9 AM', '14:00', or 'morning'." % request.start_time

    return GetCapacityRequest(
        dates=parsed_dates,
        entity_map=entity_map,
        field_combinations=field_combinations,
        has_entity_filters=has_entity_filters,
        start_time=parsed_time,
    ), None



def _resolve_single_entity_all_keyword(
    names: Optional[List[str]],
    entity_list: List[Dict[str, Any]],
    name_extractor: Callable[[Dict[str, Any]], Optional[str]],
    entity_type: str,
) -> Tuple[Optional[List[str]], Optional[str]]:
    """Resolve a single "ALL" keyword to actual entity names.
    
    Returns:
        Tuple of (resolved_names, error_string)
    """
    if not names or len(names) != 1 or names[0].upper() != "ALL":
        return names, None
    
    resolved = []
    for entity in entity_list:
        name = name_extractor(entity)
        if name:
            resolved.append(name)
    
    if not resolved:
        return None, "No %s found in cached data. Cannot resolve 'ALL'." % entity_type
    
    return resolved, None


def _resolve_all_keywords(
    advisor_names: Optional[List[str]],
    team_names: Optional[List[str]],
    transport_option_names: Optional[List[str]],
    cached_data: Dict[str, Any],
) -> Tuple[Optional[List[str]], Optional[List[str]], Optional[List[str]], Optional[str]]:
    """Resolve all "ALL" keywords to actual entity names from cached data.
    
    Returns:
        Tuple of (resolved_advisor_names, resolved_team_names, resolved_transport_names, error)
    """
    errors = []
    
    # Resolve advisors
    if advisor_names and len(advisor_names) == 1 and advisor_names[0].upper() == "ALL":
        advisors = cached_data.get("advisors", [])
        resolved, err = _resolve_single_entity_all_keyword(
            advisor_names, advisors, _extract_advisor_name, "advisors"
        )
        if err:
            errors.append(err)
        advisor_names = resolved
    
    # Resolve teams
    if team_names and len(team_names) == 1 and team_names[0].upper() == "ALL":
        teams = cached_data.get("teams", [])
        resolved, err = _resolve_single_entity_all_keyword(
            team_names, teams, _extract_team_name, "teams"
        )
        if err:
            errors.append(err)
        team_names = resolved
    
    # Resolve transport options
    if transport_option_names and len(transport_option_names) == 1 and transport_option_names[0].upper() == "ALL":
        options = cached_data.get("transport_options", [])
        resolved, err = _resolve_single_entity_all_keyword(
            transport_option_names, options, _extract_transport_name, "transport options"
        )
        if err:
            errors.append(err)
        transport_option_names = resolved
    
    error = "\n".join(errors) if errors else None
    return advisor_names, team_names, transport_option_names, error


def _validate_entities(
    advisor_names: Optional[List[str]],
    team_names: Optional[List[str]],
    transport_option_names: Optional[List[str]],
    cached_data: Dict[str, Any],
) -> Tuple[Dict[str, List[str]], Optional[str]]:
    """Validate entity names and return UUIDs."""
    uuids = {"advisor": [], "team": [], "transport": []}
    errors = []

    # Map of entity type -> (names, validation_function, uuid_key)
    entity_validations = [
        (transport_option_names, validate_transport_option_names, "transport"),
        (advisor_names, validate_advisor_names, "advisor"),
        (team_names, validate_team_names, "team"),
    ]

    for names, validate_func, uuid_key in entity_validations:
        if names and cached_data:
            result = validate_func(names, cached_data)
            uuids[uuid_key] = [uuid for _, uuid in result["valid"]]
            if len(result["valid"]) < len(names):
                errors.append(result["message"])

    if errors:
        return uuids, "Entity validation failed:\n" + "\n".join(errors)

    return uuids, None

def _get_default_date() -> str:
    """Get default date (tomorrow) as YYYY-MM-DD string."""
    today = datetime.now().date()
    return (today + timedelta(days=1)).strftime("%Y-%m-%d")


def _parse_dates(dates: Optional[List[str]]) -> List[str]:
    """Parse dates from natural language or YYYY-MM-DD format."""
    today = datetime.now().date()
    default_date = _get_default_date()

    if not dates:
        return [default_date]

    parsed = []
    for d in dates:
        result = parse_date_query(d, reference_date=today)
        if result:
            parsed.extend(result)
        else:
            try:
                dt = datetime.strptime(d, "%Y-%m-%d").date()
                if dt.year >= MIN_YEAR and dt >= (today - timedelta(days=365)):
                    parsed.append(d)
            except ValueError:
                continue

    if not parsed:
        return [default_date]

    return sorted(list(set(parsed)))


def _parse_source(source: Optional[str]) -> Optional[str]:
    """Map source string to API value."""
    if not source:
        return None
    try:
        return SourceType.from_input(source).value
    except (KeyError, AttributeError):
        return source

def _build_entity_map(
    uuids: Dict[str, List[str]],
    opcodes: Optional[List[str]],
    source: Optional[str],
) -> Tuple[Dict[str, List[str]], List[List[str]]]:
    """Build API entity map and field combinations."""
    # Always include SOURCE to prevent API validation error
    entity_map = {"SOURCE": [source] if source else ["DealerApp", "Web"]}
    field_combinations = [["SOURCE"]]

    # Map of uuid_key -> (entity_map_key, field_combination_key)
    entity_mappings = [
        ("transport", "TRANSPORT_OPTION_UUID"),
        ("advisor", "DEALER_ASSOCIATE_UUID"),
        ("team", "TEAM_UUID"),
    ]

    for uuid_key, entity_key in entity_mappings:
        if uuids[uuid_key]:
            entity_map[entity_key] = uuids[uuid_key]
            field_combinations.append([entity_key])

    if opcodes:
        entity_map["OPERATION_UUID"] = opcodes
        field_combinations.append(["OPERATION_UUID"])

    return entity_map, field_combinations


# =============================================================================
# API Call
# =============================================================================


async def _fetch_capacity(
    department_uuid: str,
    request: GetCapacityRequest,
    cached_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Fetch capacity from API and format response."""
    applicability_field = (
        ApplicabilityRuleField.DATE_AND_TIME.value if request.start_time
        else ApplicabilityRuleField.DATE.value
    )

    request_payload = {
        "applicabilityRuleField": applicability_field,
        "applicabilityFieldValues": list(set(request.dates)),
        "capacityTypeSet": [CapacityType.APPOINTMENT_COUNT.value],
        "ruleMatchingCriteria": RuleMatchingCriteria.EXACTLY_MATCHES.value,
        "includeLimitInfo": True,
        "entityMap": {k: list(set(v)) for k, v in request.entity_map.items()},
        "fieldCombinations": [list(set(c)) for c in request.field_combinations],
    }

    if request.start_time:
        request_payload["startTime"] = request.start_time

    async with KAppointmentAPIClient(config=KAppointmentAPIConfig()) as client:
        result = await client.get_capacity(department_uuid, request_payload)
        uuid_mapper = UUIDMapper(cached_data) if cached_data else None
        formatted = _format_capacity_response(result, uuid_mapper, request.entity_map, request.has_entity_filters)
        return {"formatted_summary": formatted, "raw_data": result}


# =============================================================================
# Response Formatting
# =============================================================================


def _format_capacity_response(
    api_response: Dict[str, Any],
    uuid_mapper: Optional[UUIDMapper],
    entity_map: Optional[Dict[str, List[str]]],
    has_entity_filters: bool,
) -> str:
    """Format capacity API response into summary or table."""
    if not api_response or "capacityMap" not in api_response:
        return "No capacity data found."

    capacity_map = api_response.get("capacityMap", {})
    if not capacity_map:
        return "No capacity data available for the requested criteria."

    entries, limiting_factors = _extract_capacity_entries(
        capacity_map, uuid_mapper, entity_map, has_entity_filters
    )

    if not entries:
        return "No capacity data available for the requested criteria."

    # Table for 3+ entries, conversational for 1-2
    if len(entries) >= 3:
        return _format_as_table(entries, limiting_factors)
    return _format_conversational(entries, limiting_factors)


def _extract_limiting_factor(cap_data: Dict[str, Any]) -> Optional[Tuple[str, float, str]]:
    """Extract limiting factor from capacity data.
    
    Returns:
        Tuple of (factor_name, value, details) or None if no limiting factor
    """
    limit_info = cap_data.get("limitInfo")
    if not limit_info:
        return None
    
    factor = limit_info.get("limitingFactor", "")
    value = limit_info.get("limitValue")
    details = limit_info.get("details", "")
    
    if value is not None and value < UNLIMITED_CAPACITY:
        return (factor, value, details)
    
    return None


def _extract_capacity_entries(
    capacity_map: Dict[str, Any],
    uuid_mapper: Optional[UUIDMapper],
    entity_map: Optional[Dict[str, List[str]]],
    has_entity_filters: bool,
) -> Tuple[List[Tuple], List[Tuple]]:
    """Extract capacity entries and limiting factors from API response."""
    entries = []
    limiting_factors = []

    user_entity_types = set(entity_map.keys()) if entity_map else set()
    has_non_source_filters = bool(user_entity_types - {"SOURCE"})

    for _, date_map in capacity_map.items():
        for date_key, entity_data in date_map.items():
            combo_capacity = entity_data.get("combinationWiseCapacity", {})
            if not combo_capacity:
                continue

            for combo_key, cap_data in combo_capacity.items():
                # Handle SOURCE=Total for simple queries
                if combo_key == "SOURCE=Total":
                    if not has_entity_filters:
                        entries.append((date_key, "", cap_data, combo_key))
                    continue

                # Skip SOURCE entries when user asked about specific entities
                if combo_key.startswith("SOURCE=") and has_non_source_filters:
                    continue

                # Check if entry matches requested entities
                if not _entry_matches_filter(combo_key, entity_map, has_non_source_filters):
                    continue

                entity_display = _build_entity_display_name(combo_key, uuid_mapper)
                entries.append((date_key, entity_display, cap_data, combo_key))

                # Collect limiting factor
                limit_result = _extract_limiting_factor(cap_data)
                if limit_result:
                    factor, value, details = limit_result
                    limiting_factors.append((entity_display or date_key, factor, value, details))

    return entries, limiting_factors


def _entry_matches_filter(
    combo_key: str,
    entity_map: Optional[Dict[str, List[str]]],
    has_non_source_filters: bool,
) -> bool:
    """Check if a combo key matches requested entity filters."""
    if not entity_map:
        return True

    for etype, uuids in entity_map.items():
        if etype == "SOURCE" and has_non_source_filters:
            continue
        for uuid in (uuids or []):
            if "%s=%s" % (etype, uuid) in combo_key:
                return True
    return False


def _build_entity_display_name(combo_key: str, uuid_mapper: Optional[UUIDMapper]) -> str:
    """Build display name from combo key using UUID mapper."""
    if not uuid_mapper:
        return ""

    # Map of entity type prefix -> (uuid_map, separator)
    entity_maps = [
        ("DEALER_ASSOCIATE_UUID=", uuid_mapper.advisor_map, ""),
        ("TEAM_UUID=", uuid_mapper.team_map, " (%s)"),
        ("TRANSPORT_OPTION_UUID=", uuid_mapper.transport_map, " - %s"),
    ]

    display = ""
    for prefix, uuid_map, separator in entity_maps:
        for uuid, name in uuid_map.items():
            if "%s%s" % (prefix, uuid) in combo_key:
                if not display:
                    display = name
                else:
                    display = display + separator % name
                break
        if display:
            break

    return display


def _calculate_capacity_metrics(cap_data: Dict[str, Any]) -> Tuple[int, float, int, bool]:
    """Calculate capacity metrics from capacity data.
    
    Returns:
        Tuple of (used, total, available, is_unlimited)
    """
    used = int(cap_data.get("usedCount", 0))
    total = cap_data.get("totalCount", float('inf'))
    is_unlimited = total >= UNLIMITED_CAPACITY
    available = 0 if is_unlimited else max(0, int(total) - used)
    return used, total, available, is_unlimited


def _get_limiting_factor_name(factor: str) -> str:
    """Get human-readable name for a limiting factor."""
    try:
        return LimitingFactor(factor).display_name
    except ValueError:
        return factor.lower().replace("_", " ")


def _format_as_table(entries: List[Tuple], limiting_factors: List[Tuple]) -> str:
    """Format capacity entries as markdown table."""
    dates = sorted(set(e[0] for e in entries))
    has_entities = any(e[1] for e in entries)
    parts = []

    for date_key in dates:
        date_entries = [e for e in entries if e[0] == date_key]

        if has_entities:
            parts.append("**%s**\n" % date_key)
            parts.append("| Entity | Booked | Available | Total |")
            parts.append("|--------|--------|-----------|-------|")

            for _, entity, cap_data, _ in date_entries:
                used, total, available, is_unlimited = _calculate_capacity_metrics(cap_data)
                total_str = "∞" if is_unlimited else str(int(total))
                avail_str = "∞" if is_unlimited else str(available)
                entity_name = entity or "Total"
                parts.append("| %s | %d | %s | %s |" % (entity_name, used, avail_str, total_str))
            parts.append("")
        else:
            cap_data = date_entries[0][2]
            used, total, available, is_unlimited = _calculate_capacity_metrics(cap_data)
            if is_unlimited:
                parts.append("**%s**: Unlimited capacity, %d booked." % (date_key, used))
            else:
                parts.append("**%s**: %d available (%d/%d booked)" % (date_key, available, used, int(total)))

    if limiting_factors:
        parts.append("\n**Limiting Factors:**")
        seen = set()
        for entity, factor, value, details in limiting_factors:
            friendly = _get_limiting_factor_name(factor)
            key = (entity, factor, value)
            if key not in seen:
                seen.add(key)
                detail_str = " - %s" % details if details else ""
                parts.append("- %s: %s (%d)%s" % (entity, friendly, int(value), detail_str))
        parts.append("\nWould you like me to explain how to increase any of these?")

    return "\n".join(parts)


def _format_conversational(entries: List[Tuple], limiting_factors: List[Tuple]) -> str:
    """Format capacity entries in conversational style."""
    parts = []

    for date_key, entity, cap_data, _ in entries:
        used, total, available, is_unlimited = _calculate_capacity_metrics(cap_data)
        entity_str = " for %s" % entity if entity else ""

        if is_unlimited:
            parts.append("For %s%s: unlimited capacity, %d booked." % (date_key, entity_str, used))
        else:
            parts.append("For %s%s:\n• Total: %d\n• Booked: %d\n• Available: %d" % (
                date_key, entity_str, int(total), used, available
            ))

    if limiting_factors:
        for entity, factor, value, details in limiting_factors:
            friendly = _get_limiting_factor_name(factor)
            detail_str = " - %s" % details if details else ""
            parts.append("\nLimiting Factor: %s (%d)%s" % (friendly, int(value), detail_str))
        parts.append("\nWould you like me to explain how to increase this capacity?")

    return "\n".join(parts)
