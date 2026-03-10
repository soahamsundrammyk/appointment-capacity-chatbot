"""Rules tool for fetching capacity and assignment rules."""

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.config.api_config import KAppointmentAPIConfig
from capacity_chatbot.enums import FieldDisplayName, FilterField
from capacity_chatbot.utils.date_parser import format_timing
from capacity_chatbot.utils.rule_analysis import detect_complementary_rules, detect_conflicts
from capacity_chatbot.utils.state_extractor import extract_state
from capacity_chatbot.utils.uuid_mapper import UUIDMapper, resolve_uuids_by_field

logger = logging.getLogger(__name__)

# Constants
MAX_RULES_RESULT_SIZE = 100
MAX_INTERSECTION_VALUES = 3
MAX_SUMMARY_VALUES = 2


@tool
async def get_rules_tool(
    rule_type: str | None = None,
    team_name: str | None = None,
    advisor_name: str | None = None,
    transport_option: str | None = None,
    opcode_name: str | None = None,
    entity_type: str | None = None,
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
    state, error = extract_state(config)
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
            cached_data=state.cached_data,
            filters=filters,
        )
        return result.get("formatted_summary", str(result))
    except Exception as e:
        logger.error("Error in get_rules_tool: %s", e, exc_info=True)
        return "Error fetching rules: %s" % str(e)


def _get_rule_type_list(rule_type: str | None) -> list[str]:
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
    team_name: str | None,
    advisor_name: str | None,
    transport_option: str | None,
    opcode_name: str | None,
    entity_type: str | None,
) -> dict[str, str]:
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


async def _fetch_rules(
    department_uuid: str,
    rule_type_list: list[str],
    cached_data: dict[str, Any],
    filters: dict[str, str],
) -> dict[str, Any]:
    """Fetch rules from API."""
    request = {
        "dealerUUIDList": [],
        "resultSize": MAX_RULES_RESULT_SIZE,
        "startPosition": 0,
        "ruleStatusList": ["ACTIVE"],
        "ruleTypeList": rule_type_list,
    }

    async with KAppointmentAPIClient(config=KAppointmentAPIConfig()) as client:
        result = await client.get_rule_list(department_uuid, request)
        uuid_mapper = UUIDMapper(cached_data) if cached_data else None
        formatted = _format_rules_response(result, uuid_mapper, filters)
        return {"formatted_summary": formatted, "raw_data": result}


def _format_rules_response(
    api_response: dict[str, Any],
    uuid_mapper: UUIDMapper | None,
    filters: dict[str, str],
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
            return "No rules found matching: %s. There are %d total rules." % (desc, original_count)
        return "No active rules found for this department."

    # Format each rule
    formatted = []
    for idx, rule in enumerate(rule_list, 1):
        if not rule:
            continue
        name = rule.get("ruleName", "Unnamed Rule")
        desc = _build_rule_description(rule, uuid_mapper)
        formatted.append('%d. "%s" - %s' % (idx, name, desc))

    # Build result
    if filters:
        result = "Found %d rule(s) matching %s:\n%s" % (
            filtered_count,
            _describe_filters(filters),
            "\n".join(formatted),
        )
    else:
        result = "Found %d active rule(s):\n%s" % (filtered_count, "\n".join(formatted))

    # Pre-computed conflict and complementary analysis
    # The LLM should RELAY these results, not make its own conflict judgments.
    conflicts = detect_conflicts(rule_list)
    complementary = detect_complementary_rules(rule_list)

    result += "\n\n--- RULE ANALYSIS (pre-computed, do not override) ---"

    if conflicts:
        result += "\n⚠️ CONFLICTS DETECTED (%d):" % len(conflicts)
        for c in conflicts:
            if c["type"] == "CAPACITY":
                result += (
                    "\n- CAPACITY CONFLICT: '%s' and '%s' have overlapping time slots on %s "
                    "with different limits (%s vs %s)"
                    % (
                        c["rule1_name"],
                        c["rule2_name"],
                        ", ".join(c["overlap_days"]),
                        c["rule1_action"],
                        c["rule2_action"],
                    )
                )
            else:
                result += (
                    "\n- ASSIGNMENT CONFLICT: '%s' and '%s' have overlapping conditions "
                    "but different actions (%s vs %s)"
                    % (
                        c["rule1_name"],
                        c["rule2_name"],
                        c["rule1_action"],
                        c["rule2_action"],
                    )
                )
    else:
        result += "\n✅ No rule conflicts detected."

    if complementary:
        result += "\nℹ️ COMPLEMENTARY RULES (%d pairs - these are NOT conflicts):" % len(
            complementary
        )
        for c in complementary:
            result += "\n- '%s' and '%s' cover different time slots for the same entity (no conflict)" % (
                c["rule1_name"],
                c["rule2_name"],
            )

    result += "\n--- END ANALYSIS ---"

    if filters and ("opcode_name" in filters or filters.get("entity_type") == "opcode"):
        result += (
            "\n\nIf you want to check daily limits for a specific opcode, please share the name."
        )
    else:
        result += "\n\nWould you like me to explain how to modify or create these rules?"

    return result


def _rule_matches_filter(rule: dict[str, Any], filters: dict[str, str]) -> bool:
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
            for v in _get_clause_values(clause):
                if filter_value in str(v).lower():
                    return True

    return False


def _describe_filters(filters: dict[str, str]) -> str:
    """Create human-readable filter description."""
    parts = []
    if "team_name" in filters:
        parts.append("team '%s'" % filters["team_name"])
    if "advisor_name" in filters:
        parts.append("advisor '%s'" % filters["advisor_name"])
    if "transport_option" in filters:
        parts.append("transport '%s'" % filters["transport_option"])
    if "opcode_name" in filters:
        parts.append("service '%s'" % filters["opcode_name"])
    if "entity_type" in filters:
        parts.append("any %s-related rules" % filters["entity_type"])
    return ", ".join(parts) or "specified criteria"


def _get_clause_values(clause: dict[str, Any]) -> list[Any]:
    """Extract values from a clause, preferring verboseValues over values."""
    return clause.get("verboseValues", []) or clause.get("values", [])


def _build_rule_description(rule: dict[str, Any], uuid_mapper: UUIDMapper | None) -> str:
    """Build natural English description of a rule."""
    rule_type = rule.get("ruleType", "")
    applicability = rule.get("applicabilityClause", {}) or {}
    if_clauses = rule.get("ifClauses", []) or []
    then_clauses = rule.get("thenClauses", []) or []

    subject = _extract_subject(if_clauses, uuid_mapper)
    effect = _extract_effect(then_clauses, uuid_mapper)
    timing = format_timing(applicability)

    if rule_type == "CAPACITY":
        return _build_capacity_sentence(subject, effect, timing)
    elif rule_type == "ASSIGNMENT":
        return _build_assignment_sentence(if_clauses, then_clauses, uuid_mapper)

    parts = [p for p in [timing, subject, str(effect)] if p]
    return ", ".join(parts) + "." if parts else "Rule details not available."


def _extract_subject(if_clauses: list[dict[str, Any]], uuid_mapper: UUIDMapper | None) -> str:
    """Extract main subject from if clauses."""
    for clause in if_clauses:
        field = clause.get("field", "")
        values = _get_clause_values(clause)

        # Resolve UUIDs if needed
        if uuid_mapper and not clause.get("verboseValues"):
            values = resolve_uuids_by_field(field, values, uuid_mapper)

        names = ", ".join(str(v) for v in values) if values else ""

        if field == "DEALER_ASSOCIATE_UUID":
            return names or "advisors"
        elif field == "TEAM_UUID":
            return names or "teams"
        elif field == "TRANSPORT_OPTION_UUID":
            return names or "transport options"
        elif field == "VEHICLE_MAKE":
            return "%s vehicles" % names if names else "vehicles"
        elif field in ["OPERATION_UUID", "OP_CODE", "OPCODE"]:
            return "%s service" % names if names else "services"

    return ""


def _extract_effect(
    then_clauses: list[dict[str, Any]], uuid_mapper: UUIDMapper | None
) -> dict[str, Any]:
    """Extract effect from then clauses."""
    for clause in then_clauses:
        field = clause.get("field", "")
        values = _get_clause_values(clause)

        if uuid_mapper and not clause.get("verboseValues"):
            values = resolve_uuids_by_field(field, values, uuid_mapper)

        return {
            "field": field,
            "values": values,
            "raw_values": clause.get("values", []),
            "frequency": clause.get("frequency", ""),
            "operator": clause.get("operator", ""),
        }
    return {}


def _build_capacity_sentence(subject: str, effect: dict, timing: str) -> str:
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
            return (
                "%s is blocked %s (no appointments)." % (subject, timing)
                if timing
                else "%s is blocked." % subject
            )
        return "All appointments blocked %s." % timing if timing else "All appointments blocked."
    else:
        if subject:
            msg = "%s can only take %s appointment(s) %s" % (subject, limit, freq_text)
            return "%s %s." % (msg, timing) if timing else "%s." % msg
        return "Maximum %s appointment(s) allowed %s." % (limit, freq_text)


def _build_assignment_sentence(
    if_clauses: list[dict[str, Any]],
    then_clauses: list[dict[str, Any]],
    uuid_mapper: UUIDMapper | None,
) -> str:
    """Build natural sentence for assignment rules."""
    if not if_clauses and not then_clauses:
        return "Assignment rule with no conditions defined."

    # Build IF parts
    if_parts = []
    for clause in if_clauses:
        field = clause.get("field", "")
        values = _get_clause_values(clause)
        operator = clause.get("operator", "IN")

        if uuid_mapper and not clause.get("verboseValues"):
            values = resolve_uuids_by_field(field, values, uuid_mapper)

        names = ", ".join(str(v) for v in values) if values else ""
        field_name = FieldDisplayName.get(field)

        if operator == "NOT_IN":
            if_parts.append("%s NOT IN (%s)" % (field_name, names))
        else:
            if_parts.append("%s=%s" % (field_name, names))

    # Build THEN parts
    then_parts = []
    for clause in then_clauses:
        field = clause.get("field", "")
        values = _get_clause_values(clause)
        operator = clause.get("operator", "IN")

        if uuid_mapper and not clause.get("verboseValues"):
            values = resolve_uuids_by_field(field, values, uuid_mapper)

        names = ", ".join(str(v) for v in values) if values else ""
        field_name = FieldDisplayName.get(field)

        if operator == "NOT_IN":
            then_parts.append("%s NOT IN (%s)" % (field_name, names))
        else:
            then_parts.append("→ %s: %s" % (field_name, names))

    if_text = " AND ".join(if_parts) if if_parts else "Any appointment"
    then_text = ", ".join(then_parts) if then_parts else "assignment restricted"

    return "IF %s %s" % (if_text, then_text)


