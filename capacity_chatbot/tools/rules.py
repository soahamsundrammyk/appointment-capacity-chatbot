"""Rules tool for fetching capacity and assignment rules."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.config.api_config import KAppointmentAPIConfig
from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.enums import FieldDisplayName, FilterField
from capacity_chatbot.utils.uuid_mapper import UUIDMapper

logger = logging.getLogger(__name__)


# =============================================================================
# Main Tool
# =============================================================================


@tool
async def get_rules_tool(
    rule_type: Optional[str] = None,
    team_name: Optional[str] = None,
    advisor_name: Optional[str] = None,
    transport_option: Optional[str] = None,
    opcode_name: Optional[str] = None,
    entity_type: Optional[str] = None,
    config: RunnableConfig = None,
) -> str:
    """Fetch capacity and assignment rules with optional filtering.

    RULE TYPES:
    - CAPACITY: Define appointment capacity constraints
    - ASSIGNMENT: Control appointment assignment to advisors/teams

    FILTERING OPTIONS:
    - By specific entity name: Use team_name, advisor_name, transport_option, or opcode_name
      Example: team_name="Express Shop" returns only rules mentioning Express Shop
    - By entity type: Use entity_type to get all rules involving that type
      Example: entity_type="team" returns all rules that involve ANY team

    EXAMPLES:
    - "What are the rules?" → no filters
    - "Rules for Express Shop" → team_name="Express Shop"
    - "All team-based rules" → entity_type="team"
    - "Capacity rules for Loaner" → rule_type="CAPACITY", transport_option="Loaner"
    - "What are the opcode restrictions?" → entity_type="opcode"


    Args:
        rule_type: 'CAPACITY', 'ASSIGNMENT', or empty for both
        team_name: Filter by specific team name
        advisor_name: Filter by specific advisor name
        transport_option: Filter by transport option name
        opcode_name: Filter by opcode/service name
        entity_type: Filter by type: 'team', 'advisor', 'transport', 'opcode'
        config: RunnableConfig (auto-provided)
    """
    state, error = _extract_state(config)
    if error:
        return error

    # Build rule type list
    rule_type_list = _get_rule_type_list(rule_type)

    # Build filters
    filters = _build_filters(team_name, advisor_name, transport_option, opcode_name, entity_type)

    try:
        result = await _fetch_rules(
            department_uuid=state.department_uuid,
            rule_type_list=rule_type_list,
            cached_data=state.cached_data or {},
            filters=filters,
        )
        return result.get("formatted_summary", str(result))
    except Exception as e:
        logger.error(f"Error in get_rules_tool: {e}", exc_info=True)
        return f"Error fetching rules: {str(e)}"


# =============================================================================
# State & Input Processing
# =============================================================================


def _extract_state(config: RunnableConfig) -> Tuple[Optional[CapacityChatbotState], Optional[str]]:
    """Extract and validate state from config."""
    if not config:
        return None, "Error: Config not available"

    state: CapacityChatbotState = config.get("configurable", {}).get("state")
    if not state:
        return None, "Error: State not available"

    if not state.department_uuid:
        return None, "Error: Department UUID is required."

    return state, None


def _get_rule_type_list(rule_type: Optional[str]) -> List[str]:
    """Get rule type list from input."""
    if not rule_type:
        return ["CAPACITY", "ASSIGNMENT"]

    upper = rule_type.upper()
    if upper == "CAPACITY":
        return ["CAPACITY"]
    if upper == "ASSIGNMENT":
        return ["ASSIGNMENT"]
    return ["CAPACITY", "ASSIGNMENT"]


def _build_filters(
    team_name: Optional[str],
    advisor_name: Optional[str],
    transport_option: Optional[str],
    opcode_name: Optional[str],
    entity_type: Optional[str],
) -> Dict[str, str]:
    """Build filters dict from inputs."""
    filters = {}
    if team_name:
        filters["team_name"] = team_name
    if advisor_name:
        filters["advisor_name"] = advisor_name
    if transport_option:
        filters["transport_option"] = transport_option
    if opcode_name:
        filters["opcode_name"] = opcode_name
    if entity_type:
        filters["entity_type"] = entity_type.lower()
    return filters


# =============================================================================
# API Call
# =============================================================================


async def _fetch_rules(
    department_uuid: str,
    rule_type_list: List[str],
    cached_data: Dict[str, Any],
    filters: Dict[str, str],
) -> Dict[str, Any]:
    """Fetch rules from API."""
    request = {
        "dealerUUIDList": [],
        "resultSize": 100,
        "startPosition": 0,
        "ruleStatusList": ["ACTIVE"],
        "ruleTypeList": rule_type_list,
    }

    async with KAppointmentAPIClient(config=KAppointmentAPIConfig()) as client:
        result = await client.get_rule_list(department_uuid, request)
        uuid_mapper = UUIDMapper(cached_data) if cached_data else None
        formatted = _format_rules_response(result, uuid_mapper, filters)
        return {"formatted_summary": formatted, "raw_data": result}


# =============================================================================
# Response Formatting
# =============================================================================


def _format_rules_response(
    api_response: Dict[str, Any],
    uuid_mapper: Optional[UUIDMapper],
    filters: Dict[str, str],
) -> str:
    """Format rules API response."""
    if not api_response or "ruleList" not in api_response:
        return "No rules found."

    rule_list = api_response.get("ruleList", [])
    original_count = len(rule_list)

    # Apply filters
    if filters:
        rule_list = [r for r in rule_list if _rule_matches_filter(r, filters)]

    filtered_count = len(rule_list)

    if filtered_count == 0:
        if filters:
            desc = _describe_filters(filters)
            return f"No rules found matching: {desc}. There are {original_count} total rules."
        return "No active rules found for this department."

    # Format each rule
    formatted = []
    for idx, rule in enumerate(rule_list, 1):
        if not rule:
            continue
        name = rule.get("ruleName", "Unnamed Rule")
        desc = _build_rule_description(rule, uuid_mapper)
        formatted.append(f"{idx}. \"{name}\" - {desc}")

    # Build result
    if filters:
        result = f"Found {filtered_count} rule(s) matching {_describe_filters(filters)}:\n" + "\n".join(formatted)
    else:
        result = f"Found {filtered_count} active rule(s):\n" + "\n".join(formatted)

    # Check for conflicts in assignment rules
    conflicts = _detect_conflicts(rule_list)
    if conflicts:
        names = [f"'{c['rule1_name']}' and '{c['rule2_name']}'" for c in conflicts[:2]]
        result += f"\n\n⚠️ Detected {len(conflicts)} conflicting assignment rule(s) ({', '.join(names)}). "
        result += "Would you like me to explain these conflicts?"
    elif filters and ("opcode_name" in filters or filters.get("entity_type") == "opcode"):
        result += "\n\nIf you want to check daily limits for a specific opcode, please share the name."
    else:
        result += "\n\nWould you like me to explain how to modify or create these rules?"

    return result


# =============================================================================
# Rule Filtering
# =============================================================================


def _rule_matches_filter(rule: Dict[str, Any], filters: Dict[str, str]) -> bool:
    """Check if a rule matches the given filters."""
    if not filters:
        return True

    if_clauses = rule.get("ifClauses", []) or []
    then_clauses = rule.get("thenClauses", []) or []
    all_clauses = if_clauses + then_clauses

    # Entity type filter - matches rules with ANY entity of that type
    if "entity_type" in filters:
        filter_field = FilterField.from_entity_type(filters["entity_type"])
        if filter_field:
            target_fields = filter_field.fields
            for clause in all_clauses:
                field = clause.get("field", "").upper()
                if any(tf.upper() in field for tf in target_fields):
                    return True
        return False

    # Specific entity name filters
    for filter_key in ["team_name", "advisor_name", "transport_option", "opcode_name"]:
        if filter_key not in filters:
            continue

        filter_field = FilterField.from_param_name(filter_key)
        if not filter_field:
            continue
        target_fields = filter_field.fields

        filter_value = filters[filter_key].lower()
        for clause in all_clauses:
            field = clause.get("field", "").upper()
            if not any(tf.upper() in field for tf in target_fields):
                continue

            # Check verbose values first, then regular values
            for v in clause.get("verboseValues", []) or clause.get("values", []):
                if filter_value in str(v).lower():
                    return True

    return False


def _describe_filters(filters: Dict[str, str]) -> str:
    """Create human-readable filter description."""
    parts = []
    if "team_name" in filters:
        parts.append(f"team '{filters['team_name']}'")
    if "advisor_name" in filters:
        parts.append(f"advisor '{filters['advisor_name']}'")
    if "transport_option" in filters:
        parts.append(f"transport '{filters['transport_option']}'")
    if "opcode_name" in filters:
        parts.append(f"service '{filters['opcode_name']}'")
    if "entity_type" in filters:
        parts.append(f"any {filters['entity_type']}-related rules")
    return ", ".join(parts) or "specified criteria"


# =============================================================================
# Rule Description Building
# =============================================================================


def _build_rule_description(rule: Dict[str, Any], uuid_mapper: Optional[UUIDMapper]) -> str:
    """Build natural English description of a rule."""
    rule_type = rule.get("ruleType", "")
    applicability = rule.get("applicabilityClause", {}) or {}
    if_clauses = rule.get("ifClauses", []) or []
    then_clauses = rule.get("thenClauses", []) or []

    subject = _extract_subject(if_clauses, uuid_mapper)
    effect = _extract_effect(then_clauses, uuid_mapper)
    timing = _format_timing(applicability)

    if rule_type == "CAPACITY":
        return _build_capacity_sentence(subject, effect, timing)
    elif rule_type == "ASSIGNMENT":
        return _build_assignment_sentence(if_clauses, then_clauses, uuid_mapper)

    parts = [p for p in [timing, subject, str(effect)] if p]
    return ", ".join(parts) + "." if parts else "Rule details not available."


def _extract_subject(if_clauses: List[Dict], uuid_mapper: Optional[UUIDMapper]) -> str:
    """Extract main subject from if clauses."""
    for clause in if_clauses:
        field = clause.get("field", "")
        values = clause.get("verboseValues", []) or clause.get("values", [])

        # Resolve UUIDs if needed
        if uuid_mapper and not clause.get("verboseValues"):
            values = _resolve_uuids(field, values, uuid_mapper)

        names = ", ".join(str(v) for v in values) if values else ""

        if field == "DEALER_ASSOCIATE_UUID":
            return names or "advisors"
        elif field == "TEAM_UUID":
            return names or "teams"
        elif field == "TRANSPORT_OPTION_UUID":
            return names or "transport options"
        elif field == "VEHICLE_MAKE":
            return f"{names} vehicles" if names else "vehicles"
        elif field in ["OPERATION_UUID", "OP_CODE", "OPCODE"]:
            return f"{names} service" if names else "services"

    return ""


def _extract_effect(then_clauses: List[Dict], uuid_mapper: Optional[UUIDMapper]) -> Dict[str, Any]:
    """Extract effect from then clauses."""
    for clause in then_clauses:
        field = clause.get("field", "")
        values = clause.get("verboseValues", []) or clause.get("values", [])

        if uuid_mapper and not clause.get("verboseValues"):
            values = _resolve_uuids(field, values, uuid_mapper)

        return {
            "field": field,
            "values": values,
            "raw_values": clause.get("values", []),
            "frequency": clause.get("frequency", ""),
            "operator": clause.get("operator", ""),
        }
    return {}


def _resolve_uuids(field: str, values: List, uuid_mapper: UUIDMapper) -> List:
    """Resolve UUIDs to names based on field type."""
    if field == "DEALER_ASSOCIATE_UUID":
        return uuid_mapper.replace_uuids_in_list(values, "advisor")
    elif field == "TEAM_UUID":
        return uuid_mapper.replace_uuids_in_list(values, "team")
    elif field == "TRANSPORT_OPTION_UUID":
        return uuid_mapper.replace_uuids_in_list(values, "transport")
    return values


def _format_timing(applicability: Dict[str, Any]) -> str:
    """Format timing info from applicability clause."""
    if not applicability:
        return ""

    field = applicability.get("field", "")
    date_list = applicability.get("dateList", [])
    day_time_list = applicability.get("dayTimeList", [])

    if field == "DATE" and date_list:
        dates = [_format_date(d) for d in date_list[:2]]
        return f"on {', '.join(dates)}"

    elif field in ["DAY", "DAY_AND_TIME"]:
        days = [e.get("day", "").capitalize() for e in (day_time_list or []) if e.get("day")]
        if days:
            all_days = {"Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"}
            missing = all_days - set(days)
            if len(missing) == 1:
                return f"(except {list(missing)[0]}s)"
            elif len(missing) > 0 and len(missing) < 3:
                return f"(except {', '.join(missing)})"
            return f"on {', '.join(days[:3])}"

    elif field == "DATE_AND_TIME" and date_list:
        date_str = _format_date(date_list[0])
        times = []
        for entry in (day_time_list or []):
            for slot in entry.get("timeSlots", [])[:2]:
                times.append(_format_time(slot))
        if times:
            return f"on {date_str} at {', '.join(times[:2])}"
        return f"on {date_str}"

    return ""


def _build_capacity_sentence(subject: str, effect: Dict, timing: str) -> str:
    """Build natural sentence for capacity rules."""
    if not effect:
        return "Capacity rule with no specific effect defined."

    values = effect.get("raw_values", [])
    frequency = effect.get("frequency", "")
    limit = values[0] if values else "0"

    freq_text = ""
    if frequency:
        if "SLOT" in frequency.upper():
            freq_text = "per slot"
        elif "DAY" in frequency.upper():
            freq_text = "per day"

    if str(limit) == "0":
        if subject:
            return f"{subject} is blocked {timing} (no appointments)." if timing else f"{subject} is blocked."
        return f"All appointments blocked {timing}." if timing else "All appointments blocked."
    else:
        if subject:
            msg = f"{subject} can only take {limit} appointment(s) {freq_text}"
            return f"{msg} {timing}." if timing else f"{msg}."
        return f"Maximum {limit} appointment(s) allowed {freq_text}."


def _build_assignment_sentence(if_clauses: List[Dict], then_clauses: List[Dict], uuid_mapper: Optional[UUIDMapper]) -> str:
    """Build natural sentence for assignment rules."""
    if not if_clauses and not then_clauses:
        return "Assignment rule with no conditions defined."

    # Build IF parts
    if_parts = []
    for clause in if_clauses:
        field = clause.get("field", "")
        values = clause.get("verboseValues", []) or clause.get("values", [])
        operator = clause.get("operator", "IN")

        if uuid_mapper and not clause.get("verboseValues"):
            values = _resolve_uuids(field, values, uuid_mapper)

        names = ", ".join(str(v) for v in values) if values else ""
        field_name = FieldDisplayName.get(field)

        if operator == "NOT_IN":
            if_parts.append(f"{field_name} NOT IN ({names})")
        else:
            if_parts.append(f"{field_name}={names}")

    # Build THEN parts
    then_parts = []
    for clause in then_clauses:
        field = clause.get("field", "")
        values = clause.get("verboseValues", []) or clause.get("values", [])
        operator = clause.get("operator", "IN")

        if uuid_mapper and not clause.get("verboseValues"):
            values = _resolve_uuids(field, values, uuid_mapper)

        names = ", ".join(str(v) for v in values) if values else ""
        field_name = FieldDisplayName.get(field)

        if operator == "NOT_IN":
            then_parts.append(f"{field_name} NOT IN ({names})")
        else:
            then_parts.append(f"→ {field_name}: {names}")

    if_text = " AND ".join(if_parts) if if_parts else "Any appointment"
    then_text = ", ".join(then_parts) if then_parts else "assignment restricted"

    return f"IF {if_text} {then_text}"


# =============================================================================
# Conflict Detection
# =============================================================================


def _detect_conflicts(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect conflicting assignment rules."""
    conflicts = []
    assignment_rules = [r for r in rules if r.get("ruleType") == "ASSIGNMENT"]

    for i, rule1 in enumerate(assignment_rules):
        for rule2 in assignment_rules[i+1:]:
            overlap = _check_condition_overlap(rule1, rule2)
            if overlap and _has_different_actions(rule1, rule2):
                conflicts.append({
                    "rule1_name": rule1.get("ruleName", "Unnamed"),
                    "rule2_name": rule2.get("ruleName", "Unnamed"),
                    "overlap_field": overlap["field"],
                    "rule1_action": _summarize_then(rule1),
                    "rule2_action": _summarize_then(rule2),
                })

    return conflicts


def _check_condition_overlap(rule1: Dict[str, Any], rule2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Check if two rules' conditions can match the same input."""
    cond1 = {c.get("field", ""): set(c.get("values", [])) for c in (rule1.get("ifClauses") or [])}
    cond2 = {c.get("field", ""): set(c.get("values", [])) for c in (rule2.get("ifClauses") or [])}

    # Find overlapping fields
    for field in set(cond1.keys()) & set(cond2.keys()):
        intersection = cond1[field] & cond2[field]
        if intersection:
            return {"field": field, "values": list(intersection)[:3]}

    # If one has no conditions, it matches everything
    if not cond1 or not cond2:
        return {"field": "ALL", "values": ["any input"]}

    return None


def _has_different_actions(rule1: Dict[str, Any], rule2: Dict[str, Any]) -> bool:
    """Check if two rules have different THEN actions."""
    def normalize(clauses):
        parts = [f"{c.get('field', '')}:{sorted(c.get('values', []))}" for c in (clauses or [])]
        return "|".join(sorted(parts))

    return normalize(rule1.get("thenClauses", [])) != normalize(rule2.get("thenClauses", []))


def _summarize_then(rule: Dict[str, Any]) -> str:
    """Summarize a rule's THEN action."""
    parts = []
    for clause in (rule.get("thenClauses") or []):
        field = clause.get("field", "")
        values = clause.get("verboseValues", []) or clause.get("values", [])
        name = FieldDisplayName.get(field)
        parts.append(f"{name}: {', '.join(str(v) for v in values[:2])}")
    return "; ".join(parts) if parts else "No action"


# =============================================================================
# Utilities
# =============================================================================


def _format_date(date_str: str) -> str:
    """Format date string to readable format."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        return date_str


def _format_time(time_str: str) -> str:
    """Format time string to readable format."""
    try:
        fmt = "%H:%M:%S" if len(time_str) == 8 else "%H:%M"
        return datetime.strptime(time_str, fmt).strftime("%I:%M %p").lstrip("0")
    except Exception:
        return time_str
