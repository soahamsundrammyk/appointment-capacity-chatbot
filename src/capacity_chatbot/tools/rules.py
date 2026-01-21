"""Rules tool for fetching capacity and assignment rules."""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.config import KAppointmentAPIConfig
from capacity_chatbot.utils.uuid_mapper import UUIDMapper

logger = logging.getLogger(__name__)


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
    """Fetch capacity and assignment rules for the department with optional filtering.
    
    There are two types of rules:
    1. CAPACITY RULES: Define constraints on appointment capacity
    2. ASSIGNMENT RULES: Control how appointments are assigned to advisors/teams
    
    FILTERING OPTIONS:
    - By specific entity name: Use team_name, advisor_name, transport_option, or opcode_name
      Example: team_name="Express Shop" returns only rules mentioning Express Shop
    - By entity type: Use entity_type to get all rules involving that type
      Example: entity_type="team" returns all rules that involve ANY team
    
    Use this tool when the user asks about:
    - "What are the rules?" → Fetch all (no filters)
    - "What are the capacity rules?" → rule_type="CAPACITY"
    - "Rules for Express Shop" → team_name="Express Shop"
    - "All team-based rules" → entity_type="team"
    - "Rules for advisor John" → advisor_name="John"
    - "What are the opcode restrictions?" → entity_type="opcode"
    
    Args:
        rule_type: Optional. 'CAPACITY', 'ASSIGNMENT', or empty for both.
        team_name: Optional. Filter rules mentioning this specific team name.
        advisor_name: Optional. Filter rules mentioning this specific advisor name.
        transport_option: Optional. Filter rules mentioning this transport option.
        opcode_name: Optional. Filter rules mentioning this service/opcode.
        entity_type: Optional. Filter by entity type: 'team', 'advisor', 'transport', 'opcode'.
                     Returns all rules involving ANY entity of that type.
        config: RunnableConfig containing state (automatically provided by ReAct agent)
    
    Returns:
        Human-readable formatted summary of matching rules
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
    
    # Determine rule_type_list
    if rule_type:
        rule_type_upper = rule_type.upper()
        if rule_type_upper == "CAPACITY":
            rule_type_list = ["CAPACITY"]
        elif rule_type_upper == "ASSIGNMENT":
            rule_type_list = ["ASSIGNMENT"]
        else:
            rule_type_list = ["CAPACITY", "ASSIGNMENT"]
    else:
        rule_type_list = ["CAPACITY", "ASSIGNMENT"]
    
    # Build filters dict
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
    
    try:
        result = await _get_rules_impl(
            department_uuid=department_uuid,
            rule_type_list=rule_type_list,
            mkid=mkid,
            cached_data=cached_data,
            filters=filters,
        )
        
        if isinstance(result, dict) and "formatted_summary" in result:
            return result["formatted_summary"]
        return str(result)
    except Exception as e:
        logger.error(f"Error in get_rules_tool: {e}", exc_info=True)
        return f"Error fetching rules: {str(e)}"


async def _get_rules_impl(
    department_uuid: str,
    rule_type_list: List[str],
    mkid: Optional[str] = None,
    cached_data: Optional[Dict[str, Any]] = None,
    filters: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Fetch capacity rules from the API."""
    request_payload = {
        "dealerUUIDList": [],
        "resultSize": 100,
        "startPosition": 0,
        "ruleStatusList": ["ACTIVE"],
        "ruleTypeList": rule_type_list,
    }
    
    config = KAppointmentAPIConfig(mkid=mkid) if mkid else None
    client = KAppointmentAPIClient(config=config)
    
    try:
        result = await client.get_rule_list(department_uuid, request_payload)
        
        uuid_mapper = UUIDMapper(cached_data) if cached_data else None
        formatted_result = _format_rules_response(result, uuid_mapper, filters)
        
        return {
            "formatted_summary": formatted_result,
            "raw_data": result,
            "total_count": result.get("totalCount", 0)
        }
    except Exception as e:
        return {"ruleList": [], "totalCount": 0, "error": str(e), "statusCode": "ERROR"}
    finally:
        await client.close()


def _format_rules_response(
    api_response: Dict[str, Any], 
    uuid_mapper: Optional[UUIDMapper] = None,
    filters: Optional[Dict[str, str]] = None,
) -> str:
    """Format rules API response into conversational English with optional filtering."""
    if not api_response or "ruleList" not in api_response:
        return "No rules found."
    
    rule_list = api_response.get("ruleList", [])
    original_count = len(rule_list)
    
    # Apply filters if provided
    if filters:
        rule_list = [r for r in rule_list if _rule_matches_filter(r, filters)]
    
    filtered_count = len(rule_list)
    
    if filtered_count == 0:
        if filters:
            filter_desc = _describe_filters(filters)
            return f"No rules found matching: {filter_desc}. There are {original_count} total rules in the department."
        return "No active rules found for this department."
    
    formatted_rules = []
    
    for idx, rule in enumerate(rule_list, 1):
        if not rule or not isinstance(rule, dict):
            continue
        
        rule_name = rule.get("ruleName", "Unnamed Rule")
        rule_type = rule.get("ruleType", "")
        
        # Generate natural English description
        description = _build_natural_english_description(rule, uuid_mapper)
        
        formatted_rules.append(f"{idx}. \"{rule_name}\" - {description}")
    
    # Build result header
    if filters:
        filter_desc = _describe_filters(filters)
        result = f"Found {filtered_count} rule(s) matching {filter_desc}:\n" + "\n".join(formatted_rules)
    else:
        result = f"Found {filtered_count} active rule(s):\n" + "\n".join(formatted_rules)
    
    # Check for conflicts in assignment rules (only for filtered results)
    conflicts = _detect_assignment_rule_conflicts(rule_list)
    conflict_count = len(conflicts)
    
    # Build follow-up question with conflict info if any
    if conflict_count > 0:
        conflict_names = [f"'{c['rule1_name']}' and '{c['rule2_name']}'" for c in conflicts[:2]]
        result += f"\n\n⚠️ I detected {conflict_count} conflicting assignment rule(s) ({', '.join(conflict_names)}). "
        result += "Would you like me to explain these conflicts? Note: Conflicting rules will break scheduling."
    elif filters and ("opcode_name" in filters or filters.get("entity_type") == "opcode"):
        # Only show daily limits follow-up for opcode-related queries
        result += "\n\nIf you want to check daily limits for a specific opcode, please share the name."
    else:
        result += "\n\nWould you like me to explain how to modify or create these rules?"
    
    return result


def _rule_matches_filter(rule: Dict[str, Any], filters: Dict[str, str]) -> bool:
    """Check if a rule matches the given filters.
    
    Filters can be:
    - Specific entity: team_name, advisor_name, transport_option, opcode_name
    - Entity type: entity_type (returns rules involving ANY entity of that type)
    """
    if not filters:
        return True
    
    # Get all clauses to check
    if_clauses = rule.get("ifClauses", []) or []
    then_clauses = rule.get("thenClauses", []) or []
    all_clauses = if_clauses + then_clauses
    
    # Mapping of filter keys to field names and verbose field names
    filter_to_fields = {
        "team_name": ["TEAM_UUID", "TEAM"],
        "advisor_name": ["DEALER_ASSOCIATE_UUID", "ADVISOR", "SERVICE_ADVISOR"],
        "transport_option": ["TRANSPORT_OPTION_UUID", "TRANSPORT_OPTION"],
        "opcode_name": ["OPERATION_UUID", "OP_CODE", "OPCODE", "SKILL"],
    }
    
    entity_type_to_fields = {
        "team": ["TEAM_UUID", "TEAM"],
        "advisor": ["DEALER_ASSOCIATE_UUID", "ADVISOR", "SERVICE_ADVISOR"],
        "transport": ["TRANSPORT_OPTION_UUID", "TRANSPORT_OPTION"],
        "opcode": ["OPERATION_UUID", "OP_CODE", "OPCODE", "SKILL"],
    }
    
    # Check entity_type filter (matches ANY rule with that entity type)
    if "entity_type" in filters:
        entity_type = filters["entity_type"].lower()
        target_fields = entity_type_to_fields.get(entity_type, [])
        
        for clause in all_clauses:
            field = clause.get("field", "").upper()
            if any(tf.upper() in field or field in tf.upper() for tf in target_fields):
                return True
        return False
    
    # Check specific entity name filters
    for filter_key, target_fields in filter_to_fields.items():
        if filter_key not in filters:
            continue
        
        filter_value = filters[filter_key].lower()
        
        for clause in all_clauses:
            field = clause.get("field", "").upper()
            
            # Check if this clause is for the right field type
            if not any(tf.upper() in field or field in tf.upper() for tf in target_fields):
                continue
            
            # Check verbose values (human-readable names)
            verbose_values = clause.get("verboseValues", []) or []
            for v in verbose_values:
                if filter_value in str(v).lower():
                    return True
            
            # Check regular values as fallback
            values = clause.get("values", []) or []
            for v in values:
                if filter_value in str(v).lower():
                    return True
    
    return False


def _describe_filters(filters: Dict[str, str]) -> str:
    """Create a human-readable description of the applied filters."""
    descriptions = []
    
    if "team_name" in filters:
        descriptions.append(f"team '{filters['team_name']}'")
    if "advisor_name" in filters:
        descriptions.append(f"advisor '{filters['advisor_name']}'")
    if "transport_option" in filters:
        descriptions.append(f"transport option '{filters['transport_option']}'")
    if "opcode_name" in filters:
        descriptions.append(f"service '{filters['opcode_name']}'")
    if "entity_type" in filters:
        descriptions.append(f"any {filters['entity_type']}-related rules")
    
    return ", ".join(descriptions) if descriptions else "specified criteria"


def _build_natural_english_description(rule: Dict[str, Any], uuid_mapper: Optional[UUIDMapper] = None) -> str:
    """Build a natural English description of a rule.
    
    Examples:
    - "Vishal can only take 1 appointment per day"
    - "Express Shop is blocked on December 23rd"
    - "Donald can only work on Mondays"
    - "Audi vehicles cannot get loaner cars"
    """
    rule_type = rule.get("ruleType", "")
    applicability = rule.get("applicabilityClause", {}) or {}
    if_clauses = rule.get("ifClauses", []) or []
    then_clauses = rule.get("thenClauses", []) or []
    
    # Extract key entities and values
    subject = _extract_subject(if_clauses, uuid_mapper)
    effect = _extract_effect(then_clauses, uuid_mapper)
    timing = _extract_timing(applicability)
    
    # Build natural sentence based on rule type
    if rule_type == "CAPACITY":
        return _build_capacity_rule_sentence(subject, effect, timing)
    elif rule_type == "ASSIGNMENT":
        return _build_assignment_rule_sentence(subject, effect, if_clauses, then_clauses, uuid_mapper)
    else:
        # Fallback
        parts = [p for p in [timing, subject, effect] if p]
        return ", ".join(parts) + "." if parts else "Rule details not available."


def _extract_subject(if_clauses: List[Dict], uuid_mapper: Optional[UUIDMapper]) -> str:
    """Extract the main subject of the rule from if clauses."""
    for clause in if_clauses:
        field = clause.get("field", "")
        values = clause.get("values", []) or []
        verbose_values = clause.get("verboseValues", []) or values
        
        if uuid_mapper and not clause.get("verboseValues"):
            if field == "DEALER_ASSOCIATE_UUID":
                verbose_values = uuid_mapper.replace_uuids_in_list(values, "advisor")
            elif field == "TEAM_UUID":
                verbose_values = uuid_mapper.replace_uuids_in_list(values, "team")
            elif field == "TRANSPORT_OPTION_UUID":
                verbose_values = uuid_mapper.replace_uuids_in_list(values, "transport")
        
        names = ", ".join(str(v) for v in verbose_values) if verbose_values else ""
        
        if field == "DEALER_ASSOCIATE_UUID":
            return names if names else "advisors"
        elif field == "TEAM_UUID":
            return names if names else "teams"
        elif field == "TRANSPORT_OPTION_UUID":
            return f"{names}" if names else "transport options"
        elif field == "VEHICLE_MAKE":
            return f"{names} vehicles" if names else "vehicles"
        elif field in ["OPERATION_UUID", "OP_CODE", "OPCODE"]:
            return f"{names} service" if names else "services"
    
    return ""


def _extract_effect(then_clauses: List[Dict], uuid_mapper: Optional[UUIDMapper]) -> Dict[str, Any]:
    """Extract the effect of the rule from then clauses."""
    for clause in then_clauses:
        field = clause.get("field", "")
        values = clause.get("values", []) or []
        verbose_values = clause.get("verboseValues", []) or values
        frequency = clause.get("frequency", "")
        operator = clause.get("operator", "")
        
        if uuid_mapper and not clause.get("verboseValues"):
            if field == "DEALER_ASSOCIATE_UUID":
                verbose_values = uuid_mapper.replace_uuids_in_list(values, "advisor")
            elif field == "TEAM_UUID":
                verbose_values = uuid_mapper.replace_uuids_in_list(values, "team")
            elif field == "TRANSPORT_OPTION_UUID":
                verbose_values = uuid_mapper.replace_uuids_in_list(values, "transport")
        
        return {
            "field": field,
            "values": verbose_values,
            "raw_values": values,
            "frequency": frequency,
            "operator": operator
        }
    return {}


def _extract_timing(applicability: Dict[str, Any]) -> str:
    """Extract timing info in natural language."""
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
            # Check if it's "all except X" pattern
            all_days = {"Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"}
            day_set = set(days)
            missing = all_days - day_set
            if len(missing) == 1:
                return f"(except {list(missing)[0]}s)"
            elif len(missing) > 0 and len(missing) < 3:
                return f"(except {', '.join(missing)})"
            return f"on {', '.join(days[:3])}"
    
    elif field == "DATE_AND_TIME" and date_list:
        date_str = _format_date(date_list[0])
        times = []
        for day_entry in (day_time_list or []):
            slots = day_entry.get("timeSlots", [])
            times.extend([_format_time(s) for s in slots[:2]])
        if times:
            return f"on {date_str} at {', '.join(times[:2])}"
        return f"on {date_str}"
    
    return ""


def _build_capacity_rule_sentence(subject: str, effect: Dict, timing: str) -> str:
    """Build natural sentence for capacity rules."""
    if not effect:
        return "Capacity rule with no specific effect defined."
    
    field = effect.get("field", "")
    values = effect.get("raw_values", [])
    frequency = effect.get("frequency", "")
    limit = values[0] if values else "0"
    
    freq_text = ""
    if frequency:
        if "SLOT" in frequency.upper():
            freq_text = "per slot"
        elif "DAY" in frequency.upper():
            freq_text = "per day"
    
    # Build natural sentence
    if str(limit) == "0":
        # Blocked
        if subject:
            if timing:
                return f"{subject} is blocked {timing} (no appointments available)."
            return f"{subject} is completely blocked (no appointments available)."
        else:
            if timing:
                return f"All appointments blocked {timing}."
            return "All appointments blocked."
    else:
        # Limited
        if subject:
            if timing:
                return f"{subject} can only take {limit} appointment(s) {freq_text} {timing}."
            return f"{subject} can only take {limit} appointment(s) {freq_text}."
        else:
            return f"Maximum {limit} appointment(s) allowed {freq_text}."


def _build_assignment_rule_sentence(subject: str, effect: Dict, if_clauses: List[Dict], then_clauses: List[Dict], uuid_mapper: Optional[UUIDMapper]) -> str:
    """Build natural sentence for assignment rules showing full IF → THEN details."""
    if not if_clauses and not then_clauses:
        return "Assignment rule with no conditions defined."
    
    # Build IF clause description with all conditions
    if_parts = []
    for clause in if_clauses:
        field = clause.get("field", "")
        values = clause.get("values", []) or []
        verbose_values = clause.get("verboseValues", []) or values
        operator = clause.get("operator", "IN")
        
        # Resolve UUIDs to names
        if uuid_mapper and not clause.get("verboseValues"):
            if field == "DEALER_ASSOCIATE_UUID":
                verbose_values = uuid_mapper.replace_uuids_in_list(values, "advisor")
            elif field == "TEAM_UUID":
                verbose_values = uuid_mapper.replace_uuids_in_list(values, "team")
            elif field == "TRANSPORT_OPTION_UUID":
                verbose_values = uuid_mapper.replace_uuids_in_list(values, "transport")
        
        names = ", ".join(str(v) for v in verbose_values) if verbose_values else ""
        
        # Field name mapping
        FIELD_NAMES = {
            "DEALER_ASSOCIATE_UUID": "Advisor",
            "TEAM_UUID": "Team",
            "TRANSPORT_OPTION_UUID": "Transport Option",
            "OPERATION_UUID": "Opcode",
            "OP_CODE": "Opcode",
            "VEHICLE_MAKE": "Vehicle Make",
            "VEHICLE_MODEL": "Vehicle Model",
        }
        field_name = FIELD_NAMES.get(field, field.replace("_UUID", "").replace("_", " ").title())
        
        if operator == "NOT_IN":
            if_parts.append(f"{field_name} NOT IN ({names})")
        else:
            if_parts.append(f"{field_name}={names}")
    
    # Build THEN clause description
    then_parts = []
    for clause in then_clauses:
        field = clause.get("field", "")
        values = clause.get("values", []) or []
        verbose_values = clause.get("verboseValues", []) or values
        operator = clause.get("operator", "IN")
        
        # Resolve UUIDs to names
        if uuid_mapper and not clause.get("verboseValues"):
            if field == "DEALER_ASSOCIATE_UUID":
                verbose_values = uuid_mapper.replace_uuids_in_list(values, "advisor")
            elif field == "TEAM_UUID":
                verbose_values = uuid_mapper.replace_uuids_in_list(values, "team")
            elif field == "TRANSPORT_OPTION_UUID":
                verbose_values = uuid_mapper.replace_uuids_in_list(values, "transport")
        
        names = ", ".join(str(v) for v in verbose_values) if verbose_values else ""
        
        FIELD_NAMES = {
            "DEALER_ASSOCIATE_UUID": "Advisor",
            "TEAM_UUID": "Team",
            "TRANSPORT_OPTION_UUID": "Transport Option",
        }
        field_name = FIELD_NAMES.get(field, field.replace("_UUID", "").replace("_", " ").title())
        
        if operator == "NOT_IN":
            then_parts.append(f"{field_name} NOT IN ({names})")
        else:
            then_parts.append(f"→ {field_name}: {names}")
    
    # Combine into sentence
    if_text = " AND ".join(if_parts) if if_parts else "Any appointment"
    then_text = ", ".join(then_parts) if then_parts else "assignment restricted"
    
    return f"IF {if_text} {then_text}"


def _build_when_clause(applicability: Dict[str, Any]) -> str:
    """Build the 'when' clause from applicability data."""
    if not applicability:
        return ""
    
    field = applicability.get("field", "")
    date_list = applicability.get("dateList", [])
    day_time_list = applicability.get("dayTimeList", [])
    
    if field == "DATE" and date_list:
        if len(date_list) == 1:
            return f"On {_format_date(date_list[0])}"
        return f"On dates: {', '.join(_format_date(d) for d in date_list[:3])}"
    
    elif field == "DATE_AND_TIME":
        parts = []
        if date_list:
            parts.append(f"on {_format_date(date_list[0])}")
        time_slots = []
        for day_entry in (day_time_list or []):
            if day_entry.get("timeSlots"):
                day_name = day_entry.get("day", "").capitalize()
                slots = [_format_time(s) for s in day_entry.get("timeSlots", [])[:3]]
                time_slots.append(f"{day_name} at {', '.join(slots)}")
        if time_slots:
            parts.append(f"during {', '.join(time_slots[:2])}")
        return " ".join(parts).capitalize() if parts else ""
    
    elif field == "DAY":
        days = [e.get("day", "").capitalize() for e in (day_time_list or []) if e.get("day")]
        return f"On {', '.join(days)}" if days else "On any day"
    
    elif field == "DAY_AND_TIME":
        time_info = []
        for day_entry in (day_time_list or []):
            day_name = day_entry.get("day", "").capitalize()
            slots = day_entry.get("timeSlots", [])
            if slots:
                formatted_slots = [_format_time(s) for s in slots[:2]]
                time_info.append(f"{day_name} at {', '.join(formatted_slots)}")
        return f"On {', '.join(time_info[:2])}" if time_info else "On any day"
    
    return "On any day"


def _build_condition_clause(if_clauses: List[Dict[str, Any]], uuid_mapper: Optional[UUIDMapper] = None) -> str:
    """Build the 'condition' clause from if clauses."""
    if not if_clauses:
        return ""
    
    conditions = []
    for clause in if_clauses:
        if not clause or not isinstance(clause, dict):
            continue
        
        field = clause.get("field", "")
        values = clause.get("values", []) or []
        verbose_values = clause.get("verboseValues", []) or []
        
        display_values = verbose_values if verbose_values else values
        
        if uuid_mapper and not verbose_values:
            if field == "DEALER_ASSOCIATE_UUID":
                display_values = uuid_mapper.replace_uuids_in_list(values, "advisor")
            elif field == "TEAM_UUID":
                display_values = uuid_mapper.replace_uuids_in_list(values, "team")
            elif field == "TRANSPORT_OPTION_UUID":
                display_values = uuid_mapper.replace_uuids_in_list(values, "transport")
        
        values_str = ", ".join(str(v) for v in display_values) if isinstance(display_values, list) else str(display_values)
        
        # Human-readable field name mapping - NEVER show technical field names
        FIELD_DISPLAY_NAMES = {
            "DEALER_ASSOCIATE_UUID": "advisor",
            "TEAM_UUID": "team",
            "TRANSPORT_OPTION_UUID": "transport option",
            "OPERATION_UUID": "service",
            "OP_CODE": "service",
            "OPCODE": "service",
            "SKILL": "service type",
            "VEHICLE_MAKE": "vehicle make",
            "VEHICLE_MODEL": "vehicle model",
            "VEHICLE_YEAR": "vehicle year",
            "CUSTOMER_TYPE": "customer type",
            "SOURCE": "booking source",
            "PRIORITY": "priority",
            "APPOINTMENT_DURATION": "appointment duration",
            "RECALL": "recall status",
        }
        
        display_field = FIELD_DISPLAY_NAMES.get(field, field.replace("_UUID", "").replace("_", " ").lower())
        
        if field in ["DEALER_ASSOCIATE_UUID", "TEAM_UUID"]:
            conditions.append(f"for {display_field} {values_str}")
        elif field == "TRANSPORT_OPTION_UUID":
            conditions.append(f"for {values_str} transport option")
        elif field in ["OPERATION_UUID", "OP_CODE", "OPCODE", "SKILL"]:
            conditions.append(f"for {display_field} {values_str}")
        else:
            conditions.append(f"when {display_field} is {values_str}")
    
    return " and ".join(conditions).capitalize() if conditions else ""


def _build_effect_clause(then_clauses: List[Dict[str, Any]], uuid_mapper: Optional[UUIDMapper] = None) -> str:
    """Build the 'effect' clause from then clauses.
    
    Handles both:
    - Capacity rules: TOTAL_APPOINTMENT_COUNT, TOTAL_SERVICE_HOURS
    - Assignment rules: DEALER_ASSOCIATE_UUID, TEAM_UUID, TRANSPORT_OPTION_UUID
    """
    if not then_clauses:
        return ""
    
    effects = []
    for clause in then_clauses:
        if not clause or not isinstance(clause, dict):
            continue
        
        field = clause.get("field", "")
        values = clause.get("values", []) or []
        verbose_values = clause.get("verboseValues", []) or []
        frequency = clause.get("frequency", "")
        
        # Use verbose values if available, otherwise try to resolve UUIDs
        display_values = verbose_values if verbose_values else values
        
        # Resolve UUIDs to names for assignment rule fields
        if uuid_mapper and not verbose_values:
            if field == "DEALER_ASSOCIATE_UUID":
                display_values = uuid_mapper.replace_uuids_in_list(values, "advisor")
            elif field == "TEAM_UUID":
                display_values = uuid_mapper.replace_uuids_in_list(values, "team")
            elif field == "TRANSPORT_OPTION_UUID":
                display_values = uuid_mapper.replace_uuids_in_list(values, "transport")
        
        # Format based on field type
        if field == "TOTAL_APPOINTMENT_COUNT":
            limit_value = values[0] if values else "0"
            effect_text = "appointments are blocked" if str(limit_value) == "0" else f"maximum {limit_value} appointment(s) allowed"
        elif field == "TOTAL_SERVICE_HOURS":
            limit_value = values[0] if values else "0"
            effect_text = f"maximum {limit_value} service hour(s) allowed"
        elif field == "DEALER_ASSOCIATE_UUID":
            # Assignment rule: restrict to specific advisors
            names = ", ".join(str(v) for v in display_values) if isinstance(display_values, list) else str(display_values)
            effect_text = f"only advisor(s) {names} can be assigned"
        elif field == "TEAM_UUID":
            # Assignment rule: restrict to specific teams
            names = ", ".join(str(v) for v in display_values) if isinstance(display_values, list) else str(display_values)
            effect_text = f"only team(s) {names} can be assigned"
        elif field == "TRANSPORT_OPTION_UUID":
            # Assignment rule: restrict to specific transport options
            names = ", ".join(str(v) for v in display_values) if isinstance(display_values, list) else str(display_values)
            effect_text = f"only transport option(s) {names} available"
        else:
            # Generic fallback with human-readable field name
            limit_value = values[0] if values else "0"
            field_name = field.replace("_UUID", "").replace("_", " ").lower()
            effect_text = f"{field_name} limited to {limit_value}"
        
        # Add frequency if present
        if frequency:
            freq_text = frequency.replace("_", " ").lower()
            if "slot" in freq_text:
                effect_text += " per slot"
            elif "day" in freq_text:
                effect_text += " per day"
            elif "hour" in freq_text:
                effect_text += " per hour"
        
        effects.append(effect_text)
    
    return " and ".join(effects).capitalize() if effects else ""


def _format_date(date_str: str) -> str:
    """Format a date string to be more readable."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    except:
        return date_str


def _format_time(time_str: str) -> str:
    """Format a time string to be more readable."""
    try:
        fmt = "%H:%M:%S" if len(time_str) == 8 else "%H:%M"
        return datetime.strptime(time_str, fmt).strftime("%I:%M %p").lstrip("0")
    except:
        return time_str


def _detect_assignment_rule_conflicts(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect conflicting assignment rules.
    
    Two rules conflict when:
    1. Their IF conditions overlap (can match the same input)
    2. Their THEN actions are different
    
    Note: There is NO priority system for assignment rules.
    Conflicts mean scheduling will break entirely.
    
    Args:
        rules: List of rule dictionaries from API
        
    Returns:
        List of conflict descriptions
    """
    conflicts = []
    
    # Filter to only assignment rules
    assignment_rules = [r for r in rules if r.get("ruleType") == "ASSIGNMENT"]
    
    # Compare each pair of rules
    for i, rule1 in enumerate(assignment_rules):
        for rule2 in assignment_rules[i+1:]:
            overlap = _check_condition_overlap(rule1, rule2)
            if overlap and _has_different_actions(rule1, rule2):
                conflicts.append({
                    "rule1_name": rule1.get("ruleName", "Unnamed Rule"),
                    "rule2_name": rule2.get("ruleName", "Unnamed Rule"),
                    "overlap_field": overlap["field"],
                    "overlap_values": overlap["values"],
                    "rule1_action": _summarize_then_clause(rule1),
                    "rule2_action": _summarize_then_clause(rule2),
                })
    
    return conflicts


def _check_condition_overlap(rule1: Dict[str, Any], rule2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Check if two rules' IF conditions can match the same input.
    
    Returns overlap info if conditions intersect, None otherwise.
    """
    if_clauses1 = rule1.get("ifClauses", []) or []
    if_clauses2 = rule2.get("ifClauses", []) or []
    
    # Build field -> values mapping for each rule
    conditions1 = {}
    for clause in if_clauses1:
        field = clause.get("field", "")
        values = clause.get("values", []) or []
        if field and values:
            conditions1[field] = set(values)
    
    conditions2 = {}
    for clause in if_clauses2:
        field = clause.get("field", "")
        values = clause.get("values", []) or []
        if field and values:
            conditions2[field] = set(values)
    
    # Find fields that appear in both rules
    common_fields = set(conditions1.keys()) & set(conditions2.keys())
    
    # Check for overlapping values in common fields
    for field in common_fields:
        intersection = conditions1[field] & conditions2[field]
        if intersection:
            return {
                "field": field,
                "values": list(intersection)[:3]  # Limit for readability
            }
    
    # If one rule has no conditions (matches everything), it overlaps with all
    if not conditions1 or not conditions2:
        return {"field": "ALL", "values": ["any input"]}
    
    return None


def _has_different_actions(rule1: Dict[str, Any], rule2: Dict[str, Any]) -> bool:
    """Check if two rules have different THEN actions."""
    then1 = _normalize_then_clause(rule1.get("thenClauses", []))
    then2 = _normalize_then_clause(rule2.get("thenClauses", []))
    return then1 != then2


def _normalize_then_clause(then_clauses: List[Dict[str, Any]]) -> str:
    """Normalize THEN clause for comparison."""
    parts = []
    for clause in (then_clauses or []):
        field = clause.get("field", "")
        values = sorted(clause.get("values", []))
        parts.append(f"{field}:{values}")
    return "|".join(sorted(parts))


def _summarize_then_clause(rule: Dict[str, Any]) -> str:
    """Create a human-readable summary of a rule's THEN action."""
    then_clauses = rule.get("thenClauses", []) or []
    summaries = []
    
    for clause in then_clauses:
        field = clause.get("field", "")
        verbose_values = clause.get("verboseValues", []) or clause.get("values", [])
        
        if field == "TEAM_UUID":
            summaries.append(f"Teams: {', '.join(str(v) for v in verbose_values[:2])}")
        elif field == "DEALER_ASSOCIATE_UUID":
            summaries.append(f"Advisors: {', '.join(str(v) for v in verbose_values[:2])}")
        elif field == "TRANSPORT_OPTION_UUID":
            summaries.append(f"Transport: {', '.join(str(v) for v in verbose_values[:2])}")
        else:
            field_name = field.replace("_UUID", "").replace("_", " ").title()
            summaries.append(f"{field_name}: {', '.join(str(v) for v in verbose_values[:2])}")
    
    return "; ".join(summaries) if summaries else "No action defined"
