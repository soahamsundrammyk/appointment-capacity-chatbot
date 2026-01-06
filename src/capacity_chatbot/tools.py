"""Tools for the capacity chatbot agent.

Tools are functions that the LLM can call dynamically during conversation.
They use structured input/output for type safety and better LLM understanding.
"""

from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field
from enum import Enum

import logging

from langchain_core.tools import StructuredTool
from capacity_chatbot.services.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.config.api_config import KAppointmentAPIConfig
from capacity_chatbot.utils.uuid_mapper import UUIDMapper

logger = logging.getLogger(__name__)


# ============================================================================
# Enums (matching Java enums)
# ============================================================================

class CapacityType(str, Enum):
    """Capacity type enum."""
    APPOINTMENT_COUNT = "APPOINTMENT_COUNT"
    SERVICE_HOURS = "SERVICE_HOURS"


class ApplicabilityRuleField(str, Enum):
    """Applicability rule field enum."""
    DAY = "DAY"
    DATE = "DATE"
    DATE_AND_TIME = "DATE_AND_TIME"
    DAY_AND_TIME = "DAY_AND_TIME"


class RuleMatchingCriteria(str, Enum):
    """Rule matching criteria enum."""
    EXACTLY_MATCHES = "EXACTLY_MATCHES"
    INCLUSIVELY_MATCHES = "INCLUSIVELY_MATCHES"


class RuleField(str, Enum):
    """Rule field enum for entity/filter mapping."""
    TRANSPORT_OPTION_UUID = "TRANSPORT_OPTION_UUID"
    DEALER_ASSOCIATE_UUID = "DEALER_ASSOCIATE_UUID"
    TEAM_UUID = "TEAM_UUID"
    OPERATION_UUID = "OPERATION_UUID"
    SKILL_UUID = "SKILL_UUID"
    VEHICLE_MAKE = "VEHICLE_MAKE"
    VEHICLE_MODEL = "VEHICLE_MODEL"
    VEHICLE_YEAR = "VEHICLE_YEAR"
    SOURCE = "SOURCE"
    CUSTOMER_UUID = "CUSTOMER_UUID"


# ============================================================================
# Request/Response Models (Pydantic)
# ============================================================================

class GetRulesRequest(BaseModel):
    """Request model for getRules tool."""
    
    dealer_uuid_list: List[str] = Field(
        default_factory=list,
        description="List of dealer UUIDs to filter rules. Empty list means all dealers."
    )
    result_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of rules to return"
    )
    start_position: int = Field(
        default=0,
        ge=0,
        description="Starting position for pagination"
    )
    rule_status_list: List[str] = Field(
        default=["ACTIVE"],
        description="Filter by rule status. Options: ACTIVE, INACTIVE"
    )
    rule_type_list: List[str] = Field(
        default=["CAPACITY", "ASSIGNMENT"],
        description="Filter by rule type. Options: CAPACITY, ASSIGNMENT. Default is both. Use ['CAPACITY'] for capacity rules only, ['ASSIGNMENT'] for assignment rules only, or ['CAPACITY', 'ASSIGNMENT'] for both."
    )


class RuleResponse(BaseModel):
    """Response model for a single rule."""
    
    uuid: str = Field(description="Rule UUID")
    rule_name: str = Field(description="Name of the rule")
    dealer_uuid: str = Field(description="Dealer UUID this rule applies to")
    rule_type: str = Field(description="Type of rule (CAPACITY, SCHEDULE, etc.)")
    rule_status: str = Field(description="Status of rule (ACTIVE, INACTIVE)")
    if_verbiage: str = Field(description="Human-readable 'if' condition")
    then_verbiage: str = Field(description="Human-readable 'then' action")
    applicability_clause: Dict[str, Any] = Field(description="When this rule applies")
    if_clauses: List[Dict[str, Any]] = Field(default_factory=list, description="If conditions")
    then_clauses: List[Dict[str, Any]] = Field(default_factory=list, description="Then actions")


class GetRulesResponse(BaseModel):
    """Response model for getRules tool."""
    
    rule_list: List[RuleResponse] = Field(default_factory=list, description="List of rules")
    total_count: int = Field(description="Total number of rules matching the filter")
    status_code: Optional[str] = Field(None, description="Status code if any")
    warnings: Optional[List[str]] = Field(None, description="Warnings if any")
    error: Optional[str] = Field(None, description="Error message if any")


def _format_rules_response(api_response: Dict[str, Any], uuid_mapper: Optional[UUIDMapper] = None) -> str:
    """Format rules API response into a readable string for the LLM.
    
    This creates a clean, structured format that the LLM can easily
    understand and convert to user-friendly language.
    
    Args:
        api_response: Raw API response from get_rule_list
        uuid_mapper: Optional UUID mapper to replace UUIDs with names
    """
    if not api_response or "ruleList" not in api_response:
        return "No rules found."
    
    rule_list = api_response.get("ruleList", [])
    total_count = api_response.get("totalCount", 0)
    
    if total_count == 0:
        return "No active capacity rules found for this department."
    
    formatted_rules = []
    formatted_rules.append(f"Found {total_count} active capacity rule(s):\n")
    
    for idx, rule in enumerate(rule_list, 1):
        # Handle case where rule might be None or invalid
        if not rule or not isinstance(rule, dict):
            logger.warning(f"Skipping invalid rule at index {idx}: {rule}")
            continue
        
        rule_name = rule.get("ruleName", "Unnamed Rule")
        rule_type = rule.get("ruleType", "UNKNOWN")
        rule_status = rule.get("ruleStatus", "UNKNOWN")
        
        # Debug: Log full rule structure for first rule
        if idx == 1:
            logger.info(f"Sample rule structure keys: {list(rule.keys())}")
            logger.info(f"Sample rule type: {rule_type}")
            logger.info(f"Sample rule ifClauses type: {type(rule.get('ifClauses'))}, value: {rule.get('ifClauses')}")
            logger.info(f"Sample rule thenClauses type: {type(rule.get('thenClauses'))}, value: {rule.get('thenClauses')}")
            logger.info(f"Sample rule applicabilityClause type: {type(rule.get('applicabilityClause'))}, value: {rule.get('applicabilityClause')}")
        
        # Extract applicability clause
        applicability = rule.get("applicabilityClause", {}) or {}
        # Handle case where applicabilityClause might be None
        if not isinstance(applicability, dict):
            applicability = {}
        # API returns "field" not "applicabilityRuleField"
        applicability_field = applicability.get("field", "") or applicability.get("applicabilityRuleField", "")
        # API returns "dateList" not "applicabilityFieldValues"
        applicability_values = applicability.get("dateList", []) or applicability.get("applicabilityFieldValues", [])
        
        # Extract if clauses (conditions) - REPLACE UUIDs with names
        if_clauses = rule.get("ifClauses", []) or []
        # Handle case where ifClauses might be None
        if not isinstance(if_clauses, list):
            if_clauses = []
        logger.info(f"Rule '{rule_name}' has {len(if_clauses)} if clauses")
        if_conditions = []
        for clause in if_clauses:
            # Handle case where clause might be None
            if not clause or not isinstance(clause, dict):
                logger.warning(f"Skipping invalid clause in rule '{rule_name}': {clause}")
                continue
            # API returns "field" not "ruleField"
            field = clause.get("field", "") or clause.get("ruleField", "")
            operator = clause.get("operator", "")
            values = clause.get("values", []) or []
            verbose_values = clause.get("verboseValues", []) or []
            
            # Debug: Log the clause structure
            logger.debug(f"Processing clause for rule '{rule_name}': field={field}, operator={operator}, values={values}, verboseValues={verbose_values}")
            
            # Use verboseValues if available (API already provides human-readable names)
            # Otherwise, use UUID mapper to replace UUIDs with names
            if verbose_values:
                # API already provided human-readable names
                display_values = verbose_values
                logger.debug(f"Using verboseValues from API: {display_values}")
            elif uuid_mapper and values:
                # Convert to list if it's a single value
                if not isinstance(values, list):
                    values = [values]
                
                original_values = values.copy()
                
                # Replace UUIDs with names using mapper
                if field == "DEALER_ASSOCIATE_UUID":
                    display_values = uuid_mapper.replace_uuids_in_list(original_values, "advisor")
                    logger.info(f"Replaced advisor UUIDs: {original_values} -> {display_values}")
                elif field == "TEAM_UUID":
                    display_values = uuid_mapper.replace_uuids_in_list(original_values, "team")
                    logger.info(f"Replaced team UUIDs: {original_values} -> {display_values}")
                elif field == "TRANSPORT_OPTION_UUID":
                    display_values = uuid_mapper.replace_uuids_in_list(original_values, "transport")
                    logger.info(f"Replaced transport UUIDs: {original_values} -> {display_values}")
                else:
                    display_values = values
                    logger.debug(f"Field '{field}' not mapped, keeping original values: {values}")
            else:
                # Fallback to raw values
                display_values = values if isinstance(values, list) else [values]
                if not uuid_mapper:
                    logger.debug(f"No UUID mapper available, using raw values")
            
            # Format the condition nicely
            if field == "DEALER_ASSOCIATE_UUID":
                field_display = "Service Advisor"
            elif field == "TEAM_UUID":
                field_display = "Team"
            elif field == "TRANSPORT_OPTION_UUID":
                field_display = "Transport Option"
            else:
                field_display = field
            
            # Format values for display
            if isinstance(display_values, list):
                values_str = ', '.join(map(str, display_values))
            else:
                values_str = str(display_values)
            
            if_conditions.append(f"{field_display} {operator} {values_str}")
        
        # Extract then clauses (actions)
        then_clauses = rule.get("thenClauses", []) or []
        # Handle case where thenClauses might be None
        if not isinstance(then_clauses, list):
            then_clauses = []
        then_actions = []
        for clause in then_clauses:
            # Handle case where clause might be None
            if not clause or not isinstance(clause, dict):
                logger.warning(f"Skipping invalid then clause in rule '{rule_name}': {clause}")
                continue
            # API returns "field" not "ruleField"
            field = clause.get("field", "") or clause.get("ruleField", "")
            operator = clause.get("operator", "")
            values = clause.get("values", []) or []
            # Use verboseValues if available, otherwise use values
            verbose_values = clause.get("verboseValues", []) or []
            display_values = verbose_values if verbose_values else values
            then_actions.append(f"{field} {operator} {', '.join(map(str, display_values))}")
        
        # Build formatted rule
        rule_text = f"Rule {idx}: {rule_name}\n"
        rule_text += f"  Type: {rule_type}\n"
        rule_text += f"  Status: {rule_status}\n"
        
        if applicability_field:
            rule_text += f"  Applies to: {applicability_field}"
            if applicability_values:
                rule_text += f" = {', '.join(map(str, applicability_values))}"
            rule_text += "\n"
        
        if if_conditions:
            rule_text += f"  Conditions: {' AND '.join(if_conditions)}\n"
        
        if then_actions:
            rule_text += f"  Actions: {' AND '.join(then_actions)}\n"
        
        formatted_rules.append(rule_text)
    
    return "\n".join(formatted_rules)


# ============================================================================
# Capacity Response Formatting
# ============================================================================

def _format_capacity_response(
    api_response: Dict[str, Any], 
    uuid_mapper: Optional[UUIDMapper] = None,
    requested_entities: Optional[Dict[str, List[str]]] = None,
) -> str:
    """Format capacity API response with diagnostics into a readable string for the LLM.
    
    This creates a clean, structured format that includes:
    - Capacity status (used/total/available)
    - Bottleneck identification
    - All contributing limits
    - Actionable advice on how to change limiting factors
    
    IMPORTANT: Only shows capacity data for entities that were explicitly requested.
    This prevents the LLM from seeing irrelevant data and giving wrong advice.
    
    Args:
        api_response: Raw API response from getCapacity
        uuid_mapper: Optional UUID mapper to replace UUIDs with names
        requested_entities: Dict of requested entity UUIDs to filter response by.
            Keys: DEALER_ASSOCIATE_UUID, TRANSPORT_OPTION_UUID, TEAM_UUID, OPERATION_UUID
            Values: List of UUIDs that were requested
            Only combinations containing these UUIDs will be shown.
        
    Returns:
        Formatted human-readable string with diagnostics and actionable advice
    """
    if not api_response or "capacityMap" not in api_response:
        return "No capacity data found."
    
    capacity_map = api_response.get("capacityMap", {})
    if not capacity_map:
        return "No capacity data available for the requested criteria."
    
    formatted_parts = []
    
    # Process each capacity type (APPOINTMENT_COUNT, SERVICE_HOURS)
    for capacity_type, date_map in capacity_map.items():
        formatted_parts.append(f"=== {capacity_type} CAPACITY ===")
        formatted_parts.append("")
        
        # Process each date/day
        for date_key, entity_combination_capacity in date_map.items():
            formatted_parts.append(f"Date/Day: {date_key}")
            formatted_parts.append("")
            
            combination_wise_capacity = entity_combination_capacity.get("combinationWiseCapacity", {})
            if not combination_wise_capacity:
                formatted_parts.append("  No capacity data for this date.")
                formatted_parts.append("")
                continue
            
            # Filter combinations to only show requested entities
            filtered_combinations = {}
            for combination_key, capacity_data in combination_wise_capacity.items():
                # Skip "SOURCE=Total" - always include if it exists but prioritize specific matches
                if combination_key == "SOURCE=Total":
                    # Only include Total if no specific entities were requested
                    if not requested_entities:
                        filtered_combinations[combination_key] = capacity_data
                    continue
                
                # Check if this combination matches any requested entities
                should_include = False
                
                if requested_entities:
                    # Check each requested entity type
                    for entity_type, entity_uuids in requested_entities.items():
                        if not entity_uuids:
                            continue
                        # Check if any of the requested UUIDs are in this combination key
                        for uuid in entity_uuids:
                            if f"{entity_type}={uuid}" in combination_key:
                                should_include = True
                                break
                        if should_include:
                            break
                else:
                    # No specific entities requested - include all
                    should_include = True
                
                if should_include:
                    filtered_combinations[combination_key] = capacity_data
            
            # If we have specific requested entities but found no matches, log warning
            if requested_entities and not filtered_combinations:
                logger.warning(f"No capacity data found for requested entities: {requested_entities}")
                logger.warning(f"Available combinations: {list(combination_wise_capacity.keys())}")
                # Fall back to showing the first relevant combination or Total
                for combination_key, capacity_data in combination_wise_capacity.items():
                    filtered_combinations[combination_key] = capacity_data
                    break
            
            # Process filtered combinations
            for combination_key, capacity_data in filtered_combinations.items():
                used_count = capacity_data.get("usedCount", 0.0)
                total_count = capacity_data.get("totalCount", float('inf'))
                diagnostics = capacity_data.get("diagnostics")
                
                # Format combination key (replace UUIDs with names if mapper available)
                display_key = combination_key
                if uuid_mapper:
                    # Replace UUIDs in combination key with names
                    # Handle multiple UUIDs in combination key (e.g., "DEALER_ASSOCIATE_UUID=xxx,TEAM_UUID=yyy")
                    if "DEALER_ASSOCIATE_UUID=" in combination_key:
                        for uuid, name in uuid_mapper.advisor_map.items():
                            if f"DEALER_ASSOCIATE_UUID={uuid}" in combination_key:
                                display_key = display_key.replace(f"DEALER_ASSOCIATE_UUID={uuid}", f"Advisor: {name}")
                    
                    if "TRANSPORT_OPTION_UUID=" in combination_key:
                        for uuid, name in uuid_mapper.transport_map.items():
                            if f"TRANSPORT_OPTION_UUID={uuid}" in combination_key:
                                display_key = display_key.replace(f"TRANSPORT_OPTION_UUID={uuid}", f"Transport: {name}")
                    
                    if "TEAM_UUID=" in combination_key:
                        for uuid, name in uuid_mapper.team_map.items():
                            if f"TEAM_UUID={uuid}" in combination_key:
                                display_key = display_key.replace(f"TEAM_UUID={uuid}", f"Team: {name}")
                    
                    # Clean up any remaining UUIDs that weren't mapped
                    if "UUID=" in display_key and display_key == combination_key:
                        # No replacements happened, keep original
                        pass
                
                formatted_parts.append(f"  Combination: {display_key}")
                
                # Format capacity numbers
                if total_count == float('inf') or total_count >= 1e308:
                    formatted_parts.append(f"  - Used: {used_count:.0f} appointments")
                    formatted_parts.append(f"  - Total: Unlimited")
                    formatted_parts.append(f"  - Available: Unlimited")
                else:
                    available = max(0, total_count - used_count)
                    formatted_parts.append(f"  - Used: {used_count:.0f} appointments")
                    formatted_parts.append(f"  - Total: {total_count:.0f} appointments")
                    formatted_parts.append(f"  - Available: {available:.0f} appointments")
                
                # Add diagnostics if available
                if diagnostics:
                    limit_breakdown = diagnostics.get("limitBreakdown", {})
                    bottleneck_reason = diagnostics.get("bottleneckReason", "")
                    
                    if limit_breakdown:
                        formatted_parts.append("")
                        formatted_parts.append("  DIAGNOSTICS:")
                        
                        # Show all contributing limits
                        dealer_schedule_limit = limit_breakdown.get("dealerScheduleLimit")
                        individual_schedule_limit = limit_breakdown.get("individualScheduleLimit")
                        operation_limit = limit_breakdown.get("operationLimit")
                        rule_limit = limit_breakdown.get("ruleLimit")
                        transport_option_limit = limit_breakdown.get("transportOptionLimit")
                        effective_limit = limit_breakdown.get("effectiveLimit")
                        limit_source = limit_breakdown.get("limitSource", "")
                        
                        formatted_parts.append("  Contributing Limits:")
                        
                        if dealer_schedule_limit and dealer_schedule_limit < 1e308:
                            formatted_parts.append(f"    - Dealer Schedule: {dealer_schedule_limit:.0f} appointments")
                        
                        if individual_schedule_limit and individual_schedule_limit < 1e308:
                            formatted_parts.append(f"    - Individual Schedule: {individual_schedule_limit:.0f} appointments")
                        
                        if operation_limit and operation_limit < 1e308:
                            formatted_parts.append(f"    - Operation/Opcode Limit: {operation_limit:.0f} appointments")
                        
                        if rule_limit and rule_limit < 1e308:
                            limit_source_details = limit_breakdown.get("limitSourceDetails", "")
                            rule_info = f" (Rule: {limit_source_details})" if limit_source_details else ""
                            formatted_parts.append(f"    - Capacity Rule: {rule_limit:.0f} appointments{rule_info}")
                        
                        if transport_option_limit and transport_option_limit < 1e308:
                            formatted_parts.append(f"    - Transport Option Limit: {transport_option_limit:.0f} appointments")
                        
                        # Identify bottleneck
                        if effective_limit and effective_limit < 1e308:
                            formatted_parts.append("")
                            formatted_parts.append(f"  BOTTLENECK: {limit_source}")
                            if bottleneck_reason:
                                formatted_parts.append(f"  Reason: {bottleneck_reason}")
                            
                            # Add actionable advice based on bottleneck type
                            formatted_parts.append("")
                            formatted_parts.append("  HOW TO INCREASE CAPACITY:")
                            
                            if limit_source == "TRANSPORT_OPTION_LIMIT":
                                formatted_parts.append("  To increase capacity for this transport option:")
                                formatted_parts.append("  1. Go to Settings > Appointments > Transport Options")
                                formatted_parts.append("  2. Select the transport option from the dropdown menu")
                                formatted_parts.append("  3. In the capacity configuration section at the bottom, increase the limit")
                                formatted_parts.append("  4. You can set limits per day of the week or for specific dates")
                                formatted_parts.append("  5. Click 'Allow changes only for selected dates' for date-specific changes")
                                formatted_parts.append(f"  Current limit: {transport_option_limit:.0f} appointments per day")
                                formatted_parts.append("  To allow more appointments, increase this number in the transport option settings.")
                            
                            elif limit_source == "CAPACITY_RULE":
                                limit_source_details = limit_breakdown.get("limitSourceDetails", "")
                                formatted_parts.append("  To increase capacity limited by a capacity rule:")
                                formatted_parts.append("  1. Go to Settings > Capacity Rules (or Rules Management)")
                                formatted_parts.append("  2. Find the rule that's limiting capacity")
                                if limit_source_details and "Rule:" in limit_source_details:
                                    # Extract rule name from details
                                    rule_name = limit_source_details.split("Rule:")[-1].split("(UUID:")[0].strip()
                                    formatted_parts.append(f"  3. Look for rule: {rule_name}")
                                formatted_parts.append("  4. Edit the rule's 'Then' clause to increase the capacity limit")
                                formatted_parts.append("  5. The limit is set in the TOTAL_APPOINTMENT_COUNT field")
                                formatted_parts.append(f"  Current rule limit: {rule_limit:.0f} appointments")
                                formatted_parts.append("  Increase this value in the rule's Then clause to allow more appointments.")
                            
                            elif limit_source == "DEALER_SCHEDULE":
                                formatted_parts.append("  To increase capacity limited by dealer schedule:")
                                formatted_parts.append("  1. Go to Settings > Appointments > Dealer Schedule")
                                formatted_parts.append("  2. Find the day in the grid view (Sunday-Saturday)")
                                formatted_parts.append("  3. Increase the appointment limit for that day")
                                formatted_parts.append("  4. For date-specific changes, toggle 'Allow Changes Only for Selected Dates'")
                                formatted_parts.append(f"  Current dealer schedule limit: {dealer_schedule_limit:.0f} appointments")
                                formatted_parts.append("  Increase this value in the dealer schedule grid to allow more appointments.")
                            
                            elif limit_source == "INDIVIDUAL_SCHEDULE":
                                formatted_parts.append("  To increase capacity limited by individual advisor schedule:")
                                formatted_parts.append("  1. Go to Settings > Appointments > Individuals")
                                formatted_parts.append("  2. Select the advisor from the list")
                                formatted_parts.append("  3. In the grid view, increase the appointment limit for the specific day")
                                formatted_parts.append("  4. For date-specific changes, toggle 'Allow Changes Only for Selected Dates'")
                                formatted_parts.append(f"  Current individual schedule limit: {individual_schedule_limit:.0f} appointments")
                                formatted_parts.append("  Increase this value in the individual schedule grid to allow more appointments.")
                            
                            elif limit_source == "OPERATION_LIMIT":
                                formatted_parts.append("  To increase capacity limited by operation/opcode limit:")
                                formatted_parts.append("  1. Go to Settings > Operations/Opcode Settings")
                                formatted_parts.append("  2. Find the operation/opcode that's limiting capacity")
                                formatted_parts.append("  3. Increase the appointment count limit for that operation")
                                formatted_parts.append(f"  Current operation limit: {operation_limit:.0f} appointments")
                                formatted_parts.append("  Increase this value in the operation settings to allow more appointments.")
                            
                            else:
                                formatted_parts.append(f"  The capacity is limited by: {limit_source}")
                                formatted_parts.append(f"  Current effective limit: {effective_limit:.0f} appointments")
                                formatted_parts.append("  Review the contributing limits above to identify which setting needs adjustment.")
                
                formatted_parts.append("")
        
        formatted_parts.append("")
    
    return "\n".join(formatted_parts)


# ============================================================================
# Tool Implementation
# ============================================================================

async def get_rules_tool_impl(
    department_uuid: str,
    dealer_uuid_list: Optional[List[str]] = None,
    result_size: int = 100,
    start_position: int = 0,
    rule_status_list: Optional[List[str]] = None,
    rule_type_list: Optional[List[str]] = None,
    mkid: Optional[str] = None,
    cached_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fetch capacity rules for a department.
    
    This tool calls the kappointment-api endpoint to get all capacity rules
    that apply to the specified department. Rules define constraints like
    "maximum appointments per day" or "blocked time slots".
    
    Args:
        department_uuid: Department UUID to fetch rules for
        dealer_uuid_list: Optional list of dealer UUIDs to filter by (empty = all)
        result_size: Maximum number of rules to return (1-1000, default: 100)
        start_position: Starting position for pagination (default: 0)
        rule_status_list: Filter by status (default: ["ACTIVE"])
        rule_type_list: Filter by type (default: ["CAPACITY"])
        mkid: MyKaarma cookie ID for authentication
        cached_data: Optional cached data from UI (advisors, teams, transport_options)
                     Used to map UUIDs to human-readable names
        
    Returns:
        Dictionary with formatted_summary (human-readable), raw_data, and total_count
        
    Example:
        >>> result = await get_rules_tool_impl(
        ...     department_uuid="dept-123",
        ...     rule_type_list=["CAPACITY"],
        ...     cached_data={"advisors": [...], "teams": [...]}
        ... )
        >>> print(result["total_count"])
        5
    """
    import asyncio
    
    # Build request payload
    request_payload = {
        "dealerUUIDList": dealer_uuid_list or [],
        "resultSize": result_size,
        "startPosition": start_position,
        "ruleStatusList": rule_status_list or ["ACTIVE"],
        "ruleTypeList": rule_type_list or ["CAPACITY"],
    }
    
    # Initialize API client with mkid if provided
    config = KAppointmentAPIConfig(mkid=mkid) if mkid else None
    client = KAppointmentAPIClient(config=config)
    
    try:
        # Call the API using the client method
        result = await client.get_rule_list(department_uuid, request_payload)
        
        # Create UUID mapper from cached data if available
        uuid_mapper = None
        if cached_data:
            logger.info(f"Creating UUID mapper with cached_data keys: {list(cached_data.keys())}")
            uuid_mapper = UUIDMapper(cached_data)
            logger.info(f"UUID Mapper created: {len(uuid_mapper.advisor_map)} advisors, {len(uuid_mapper.team_map)} teams, {len(uuid_mapper.transport_map)} transport options")
            # Log sample mappings for debugging
            if uuid_mapper.advisor_map:
                sample_advisor = list(uuid_mapper.advisor_map.items())[0]
                logger.info(f"Sample advisor mapping: {sample_advisor[0][:20]}... -> {sample_advisor[1]}")
                # Test specific UUIDs from the rules
                test_advisor_uuid = "dca22399976b1ca1321835f3183d0c3ffca68faea388d5661c49d81e8db382de"
                if test_advisor_uuid in uuid_mapper.advisor_map:
                    logger.info(f"Test advisor UUID found in mapper: {test_advisor_uuid} -> {uuid_mapper.advisor_map[test_advisor_uuid]}")
                else:
                    logger.warning(f"Test advisor UUID NOT found in mapper: {test_advisor_uuid}")
            if uuid_mapper.team_map:
                sample_team = list(uuid_mapper.team_map.items())[0]
                logger.info(f"Sample team mapping: {sample_team[0][:20]}... -> {sample_team[1]}")
                # Test specific UUIDs from the rules
                test_team_uuid = "BLcD5aDSn_1aB9ZVMqMUBm1-_ayGFhSgoOaKPL8fzO4"
                if test_team_uuid in uuid_mapper.team_map:
                    logger.info(f"Test team UUID found in mapper: {test_team_uuid} -> {uuid_mapper.team_map[test_team_uuid]}")
                else:
                    logger.warning(f"Test team UUID NOT found in mapper: {test_team_uuid}")
                    logger.info(f"Available team UUIDs: {list(uuid_mapper.team_map.keys())[:3]}...")
        else:
            logger.warning("No UUID mapper created - cached_data is None or empty")
        
        # Format the response with UUID mapper to replace UUIDs with names
        formatted_result = _format_rules_response(result, uuid_mapper)
        
        # Return both formatted and raw (for debugging)
        return {
            "formatted_summary": formatted_result,
            "raw_data": result,  # Keep raw data in case LLM needs details
            "total_count": result.get("totalCount", 0)
        }
        
    except Exception as e:
        # Return error in a structured format
        return {
            "ruleList": [],
            "totalCount": 0,
            "error": str(e),
            "statusCode": "ERROR"
        }
    finally:
        await client.close()


# ============================================================================
# LangChain Tool Definition
# ============================================================================

get_rules_tool = StructuredTool.from_function(
    func=get_rules_tool_impl,
    name="get_rules",
    description="""Fetch capacity rules for a department. 
    
    Rules define constraints on appointment capacity, such as:
    - Maximum appointments per day/slot
    - Blocked time periods
    - Advisor-specific limits
    - Transport option limits
    
    Use this tool when the user asks about:
    - "What are the capacity rules?"
    - "Why is capacity limited?"
    - "Show me the rules for this department"
    - "What constraints are in place?"
    
    The tool returns a list of rules with their conditions and actions in human-readable format.
    """,
    args_schema=GetRulesRequest,
    return_schema=GetRulesResponse,
)


# ============================================================================
# getCapacity Request/Response Models
# ============================================================================

class GetCapacityRequest(BaseModel):
    """Request model for getCapacity tool."""
    
    applicability_rule_field: ApplicabilityRuleField = Field(
        default=ApplicabilityRuleField.DATE,
        description="How to apply rules: DAY (day of week), DATE (specific dates), DATE_AND_TIME, DAY_AND_TIME"
    )
    
    applicability_field_values: List[str] = Field(
        default_factory=list,
        description="List of dates (YYYY-MM-DD) or days (MONDAY, TUESDAY, etc.) to get capacity for"
    )
    
    capacity_type_set: List[CapacityType] = Field(
        default_factory=lambda: [CapacityType.APPOINTMENT_COUNT],
        description="Types of capacity to fetch: APPOINTMENT_COUNT, SERVICE_HOURS"
    )
    
    start_time: Optional[str] = Field(
        None,
        description="Optional start time filter (HH:mm:ss format)"
    )
    
    end_time: Optional[str] = Field(
        None,
        description="Optional end time filter (HH:mm:ss format)"
    )
    
    # Optional filters
    filter_map: Optional[Dict[str, List[str]]] = Field(
        None,
        description="Optional filter map: {RuleField: [uuid1, uuid2]} to filter entities"
    )
    
    entity_map: Optional[Dict[str, List[str]]] = Field(
        None,
        description="Optional entity map: {RuleField: [uuid1, uuid2]} to include specific entities"
    )
    
    field_combinations: Optional[List[List[str]]] = Field(
        None,
        description="Optional field combinations: [[RuleField1], [RuleField2]] to get capacity for specific combinations"
    )
    
    rule_matching_criteria: RuleMatchingCriteria = Field(
        default=RuleMatchingCriteria.EXACTLY_MATCHES,
        description="How to match rules: EXACTLY_MATCHES or INCLUSIVELY_MATCHES"
    )
    
    caller_da_uuid: Optional[str] = Field(
        None,
        description="Optional caller dealer associate UUID"
    )


class Capacity(BaseModel):
    """Capacity model for a specific combination."""
    
    used_count: float = Field(description="Number of appointments/hours used")
    total_count: float = Field(description="Total capacity (can be unlimited/infinity)")


class EntityCombinationCapacity(BaseModel):
    """Capacity for entity combinations."""
    
    combination_wise_capacity: Dict[str, Capacity] = Field(
        default_factory=dict,
        description="Map of combination key to capacity (e.g., 'TRANSPORT_OPTION_UUID=xyz': {usedCount: 5, totalCount: 10})"
    )


class GetCapacityResponse(BaseModel):
    """Response model for getCapacity tool."""
    
    capacity_map: Dict[str, Dict[str, EntityCombinationCapacity]] = Field(
        description="Nested map: CapacityType -> Date/Day -> EntityCombinationCapacity"
    )


# ============================================================================
# getCapacity Tool Implementation
# ============================================================================

async def get_capacity_tool_impl(
    department_uuid: str,
    applicability_rule_field: ApplicabilityRuleField = ApplicabilityRuleField.DATE,
    applicability_field_values: Optional[List[str]] = None,
    capacity_type_set: Optional[List[CapacityType]] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    filter_map: Optional[Dict[str, List[str]]] = None,
    entity_map: Optional[Dict[str, List[str]]] = None,
    field_combinations: Optional[List[List[str]]] = None,
    rule_matching_criteria: RuleMatchingCriteria = RuleMatchingCriteria.EXACTLY_MATCHES,
    caller_da_uuid: Optional[str] = None,
    mkid: Optional[str] = None,
    cached_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fetch capacity information for a department.
    
    This tool calls the kappointment-api getCapacity endpoint to get capacity
    information (appointment counts, service hours) for specific dates/days
    and entity combinations (advisors, transport options, teams, etc.).
    
    Args:
        department_uuid: Department UUID to fetch capacity for
        applicability_rule_field: How to apply rules (DAY, DATE, DATE_AND_TIME, DAY_AND_TIME)
        applicability_field_values: List of dates (YYYY-MM-DD) or days (MONDAY, etc.)
        capacity_type_set: Types of capacity to fetch (APPOINTMENT_COUNT, SERVICE_HOURS)
        start_time: Optional start time filter (HH:mm:ss)
        end_time: Optional end time filter (HH:mm:ss)
        filter_map: Optional filter for specific entities
        entity_map: Optional entities to include in calculation
        field_combinations: Optional combinations to get capacity for
        rule_matching_criteria: How to match rules (EXACTLY_MATCHES, INCLUSIVELY_MATCHES)
        caller_da_uuid: Optional caller dealer associate UUID
        
    Returns:
        Dictionary with capacityMap structure:
        {
            "APPOINTMENT_COUNT": {
                "2025-01-15": {
                    "combinationWiseCapacity": {
                        "TRANSPORT_OPTION_UUID=xyz": {
                            "usedCount": 5.0,
                            "totalCount": 10.0
                        }
                    }
                }
            }
        }
        
    Example:
        >>> result = await get_capacity_tool_impl(
        ...     department_uuid="dept-123",
        ...     applicability_field_values=["2025-01-15"],
        ...     capacity_type_set=[CapacityType.APPOINTMENT_COUNT]
        ... )
        >>> print(result["capacityMap"]["APPOINTMENT_COUNT"]["2025-01-15"])
    """
    import asyncio
    
    # Build request payload matching Java CapacityRequest structure
    request_payload: Dict[str, Any] = {}
    
    if caller_da_uuid:
        request_payload["callerDaUuid"] = caller_da_uuid
    
    request_payload["applicabilityRuleField"] = applicability_rule_field.value
    
    if applicability_field_values:
        # Convert to HashSet (list in JSON)
        request_payload["applicabilityFieldValues"] = list(set(applicability_field_values))
    else:
        request_payload["applicabilityFieldValues"] = []
    
    if start_time:
        request_payload["startTime"] = start_time
    
    if end_time:
        request_payload["endTime"] = end_time
    
    # Convert CapacityType enum to string values
    if capacity_type_set:
        request_payload["capacityTypeSet"] = [ct.value for ct in capacity_type_set]
    else:
        request_payload["capacityTypeSet"] = [CapacityType.APPOINTMENT_COUNT.value]
    
    # Convert filter_map to Java HashMap<RuleField, HashSet<String>> format
    if filter_map:
        request_payload["filterMap"] = {
            k: list(set(v)) for k, v in filter_map.items()
        }
    
    # Convert entity_map to Java HashMap<RuleField, HashSet<String>> format
    if entity_map:
        request_payload["entityMap"] = {
            k: list(set(v)) for k, v in entity_map.items()
        }
    
    # Convert field_combinations to Java HashSet<HashSet<RuleField>> format
    if field_combinations:
        request_payload["fieldCombinations"] = [
            list(set(combo)) for combo in field_combinations
        ]
    
    request_payload["ruleMatchingCriteria"] = rule_matching_criteria.value
    
    # Always include diagnostics for detailed reasoning
    request_payload["includeDiagnostics"] = True
    
    # Log the exact request body being sent
    import json
    logger.info("=" * 80)
    logger.info("get_capacity API Request Details:")
    logger.info(f"  URL: POST /appointment/v2/webservice/department/{department_uuid}/capacity")
    logger.info(f"  Department UUID: {department_uuid}")
    logger.info("  Request Body (JSON):")
    logger.info(json.dumps(request_payload, indent=2, default=str))
    logger.info("=" * 80)
    
    # Initialize API client with mkid if provided
    config = KAppointmentAPIConfig(mkid=mkid) if mkid else None
    client = KAppointmentAPIClient(config=config)
    
    try:
        # Call the API
        result = await client.get_capacity(department_uuid, request_payload)
        
        # Create UUID mapper from cached data if available
        uuid_mapper = None
        if cached_data:
            uuid_mapper = UUIDMapper(cached_data)
        
        # Build requested_entities from entity_map for filtering
        # This ensures LLM only sees capacity for entities that were actually requested
        requested_entities = entity_map if entity_map else None
        
        # Format the response with diagnostics for human-readable output
        # Pass requested_entities to filter out irrelevant advisor/team/transport data
        formatted_result = _format_capacity_response(result, uuid_mapper, requested_entities)
        
        # Return both formatted and raw (for debugging)
        return {
            "formatted_summary": formatted_result,
            "raw_data": result,  # Keep raw data in case LLM needs details
            "has_data": bool(result.get("capacityMap"))
        }
        
    except Exception as e:
        # Return error in a structured format
        logger.error(f"Error in get_capacity_tool_impl: {e}")
        return {
            "formatted_summary": f"Error fetching capacity: {str(e)}",
            "raw_data": {
                "capacityMap": {},
                "error": str(e),
                "statusCode": "ERROR"
            },
            "has_data": False
        }
    finally:
        await client.close()


# ============================================================================
# LangChain Tool Definition for getCapacity
# ============================================================================

get_capacity_tool = StructuredTool.from_function(
    func=get_capacity_tool_impl,
    name="get_capacity",
    description="""Fetch capacity information for appointments and service hours with detailed diagnostics.
    
    This tool retrieves capacity data showing:
    - How many appointments are used vs available
    - Service hours capacity
    - Capacity broken down by advisors, transport options, teams, etc.
    - Capacity for specific dates or days of the week
    - DIAGNOSTIC INFORMATION: Identifies bottlenecks and provides actionable advice
    
    The tool ALWAYS includes diagnostics, which show:
    - All contributing limits (dealer schedule, individual schedule, rules, transport options, operations)
    - The bottleneck (which limit is constraining capacity)
    - Detailed reasoning for why capacity is limited
    - Step-by-step instructions on how to increase capacity
    
    Use this tool when the user asks about:
    - "What's the capacity for tomorrow?"
    - "How many slots are available?"
    - "What's the capacity for advisor X?"
    - "Show me capacity for loaner transport"
    - "Why can't I book for tomorrow?"
    - "What's limiting the capacity?"
    - "How can I increase capacity?"
    - "What's the capacity for next week?"
    
    The tool returns detailed capacity information including:
    - Used/total counts for different entity combinations
    - Diagnostic breakdown showing all limits
    - Bottleneck identification
    - Actionable advice on how to change limiting factors
    """,
    args_schema=GetCapacityRequest,
    return_schema=GetCapacityResponse,
)


class GetFirstAvailableSlotRequest(BaseModel):
    """Request model for getFirstAvailableSlot tool."""
    
    advisor_names: Optional[List[str]] = Field(
        None,
        description="List of advisor names (e.g., ['Vishal', 'Art']). At least one advisor is required. Will be automatically mapped to UUIDs."
    )
    team_names: Optional[List[str]] = Field(
        None,
        description="List of team names (e.g., ['Express Shop', 'Main Shop']). Will be automatically mapped to UUIDs."
    )
    transport_option_names: Optional[List[str]] = Field(
        None,
        description="List of transport option names (e.g., ['loaner', 'shuttle']). Will be automatically mapped to UUIDs."
    )
    dates: Optional[List[str]] = Field(
        None,
        description="List of start dates in YYYY-MM-DD format to search from. If not provided, searches from today up to 90 days."
    )
    start_time: Optional[str] = Field(
        None,
        description="Start time in HH:mm:ss format (e.g., '08:00:00'). Time from which to search for availability."
    )
    end_time: Optional[str] = Field(
        None,
        description="End time in HH:mm:ss format (e.g., '17:00:00'). Time until which to search for availability."
    )
    opcodes: Optional[List[str]] = Field(
        None,
        description="List of opcode/service UUIDs that user has selected (optional)."
    )


class SearchOpcodeRequest(BaseModel):
    """Request model for search_opcode tool."""
    
    concern_text: str = Field(
        ...,
        description="User's concern or query text describing the service/opcode they're looking for. Examples: 'oil change', 'tire rotation', 'Why can't I book for oil change?', 'brake inspection'"
    )


def _format_opcode_search_response(
    result: Dict[str, Any]
) -> str:
    """Format opcode search response for LLM.
    
    Args:
        result: API response dictionary with matchedOpcodes
        
    Returns:
        Formatted human-readable string with opcode UUIDs and names
    """
    if not result or "matchedOpcodes" not in result:
        return "No opcodes found matching your query."
    
    matched_opcodes = result.get("matchedOpcodes", [])
    
    if not matched_opcodes:
        return "No opcodes found matching your query. Try rephrasing or using different keywords."
    
    formatted_results = []
    formatted_results.append(f"Found {len(matched_opcodes)} matching opcode(s):\n")
    
    for idx, match in enumerate(matched_opcodes, 1):
        operation_dto = match.get("operationDTO", {})
        score = match.get("score", 0.0)
        
        opcode_uuid = operation_dto.get("uuid", "Unknown")
        opcode_name = operation_dto.get("opCodeName", "Unknown")
        description = operation_dto.get("description", "")
        labor_opcode = operation_dto.get("laborOpCode", "")
        duration_minutes = operation_dto.get("opCodeDurationInMinutes", "")
        
        # Format the result
        result_text = f"{idx}. **{opcode_name}**"
        if labor_opcode and labor_opcode != opcode_name:
            result_text += f" ({labor_opcode})"
        result_text += f"\n"
        result_text += f"   - UUID: {opcode_uuid}\n"
        if description:
            result_text += f"   - Description: {description}\n"
        if duration_minutes:
            result_text += f"   - Duration: {duration_minutes} minutes\n"
        result_text += f"   - Match Score: {score:.2%}\n"
        
        formatted_results.append(result_text)
    
    return "\n".join(formatted_results)


def _format_first_available_slot_response(
    result: Dict[str, Any],
    uuid_mapper: Optional[UUIDMapper] = None
) -> str:
    """Format first available slot response for LLM.
    
    Args:
        result: API response dictionary
        uuid_mapper: Optional mapper to convert UUIDs to names
        
    Returns:
        Formatted human-readable string
    """
    # Check for errors
    error = result.get("error")
    if error:
        error_desc = error.get("errorDescription", "Unknown error")
        error_code = error.get("errorCode", "")
        return f"Error finding first available slot: {error_desc} (Code: {error_code})"
    
    # Extract dateTime
    date_time = result.get("dateTime")
    if not date_time:
        return "No available slot found within the search criteria."
    
    # Format the response
    formatted = f"First Available Slot: {date_time}"
    
    # Add warnings if any
    warnings = result.get("warnings", [])
    if warnings:
        warning_descs = [w.get("warningDescription", "") for w in warnings if w.get("warningDescription")]
        if warning_descs:
            formatted += f"\n\nWarnings: {', '.join(warning_descs)}"
    
    # Add status code info
    status_code = result.get("statusCode", 0)
    if status_code != 0:
        formatted += f"\nStatus Code: {status_code}"
    
    return formatted


async def get_first_available_slot_tool_impl(
    department_uuid: str,
    advisor_names: Optional[List[str]] = None,
    team_names: Optional[List[str]] = None,
    transport_option_names: Optional[List[str]] = None,
    dates: Optional[List[str]] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    opcodes: Optional[List[str]] = None,
    mkid: Optional[str] = None,
    basic_auth_username: Optional[str] = None,
    basic_auth_password: Optional[str] = None,
    cached_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Find the first available appointment slot.
    
    This tool finds the earliest available appointment slot based on selected
    attributes (advisors, teams, transport options) and optional filters
    (dates, times, opcodes).
    
    Args:
        department_uuid: Department UUID
        advisor_names: List of advisor names (at least one required)
        team_names: List of team names (optional)
        transport_option_names: List of transport option names (optional)
        dates: List of start dates in YYYY-MM-DD format (optional, searches from today if not provided)
        start_time: Start time in HH:mm:ss format (optional)
        end_time: End time in HH:mm:ss format (optional)
        opcodes: List of opcode UUIDs (optional)
        mkid: MyKaarma cookie ID for authentication
        basic_auth_username: Username for basic auth (defaults to env var or "1")
        basic_auth_password: Password for basic auth (defaults to env var or "1")
        cached_data: Optional cached data from UI for UUID mapping
        
    Returns:
        Dictionary with formatted_summary and raw_data
        
    Example:
        >>> result = await get_first_available_slot_tool_impl(
        ...     department_uuid="dept-123",
        ...     advisor_names=["Vishal"],
        ...     transport_option_names=["loaner"],
        ...     dates=["2025-12-29"]
        ... )
        >>> print(result["formatted_summary"])
        First Available Slot: 2025-12-29 10:30:00
    """
    # Create UUID mapper from cached data
    uuid_mapper = None
    if cached_data:
        uuid_mapper = UUIDMapper(cached_data)
    
    # Convert advisor names to UUIDs (REQUIRED)
    advisor_uuids = []
    if advisor_names:
        if uuid_mapper:
            for name in advisor_names:
                uuid = uuid_mapper.get_advisor_uuid_by_name(name)
                if uuid:
                    advisor_uuids.append(uuid)
                else:
                    logger.warning(f"Advisor name '{name}' not found in cached data")
        else:
            logger.warning("No cached_data provided - cannot map advisor names to UUIDs")
            # If no mapper, assume advisor_names are actually UUIDs
            advisor_uuids = advisor_names
    
    # At least one advisor UUID is required
    # If no advisor specified but we have cached_data, use all advisors as fallback
    if not advisor_uuids:
        if cached_data and uuid_mapper:
            # Get all advisor UUIDs from cached data
            advisors = cached_data.get("advisors", [])
            advisor_uuids = [a.get("uuid") for a in advisors if a.get("uuid")]
            if advisor_uuids:
                logger.info(f"No advisor specified, using all {len(advisor_uuids)} advisors from cached data as fallback")
            else:
                return {
                    "formatted_summary": "Error: At least one advisor must be specified. Please provide advisor names.",
                    "raw_data": None,
                    "has_data": False
                }
        else:
            return {
                "formatted_summary": "Error: At least one advisor must be specified. Please provide advisor names.",
                "raw_data": None,
                "has_data": False
            }
    
    # Convert team names to UUIDs (optional)
    team_uuids = []
    if team_names and uuid_mapper:
        for name in team_names:
            uuid = uuid_mapper.get_team_uuid_by_name(name)
            if uuid:
                team_uuids.append(uuid)
    
    # Convert transport option names to UUIDs (optional)
    transport_option_uuids = []
    if transport_option_names and uuid_mapper:
        for name in transport_option_names:
            uuid = uuid_mapper.get_transport_uuid_by_name(name)
            if uuid:
                transport_option_uuids.append(uuid)
    
    # Build selectedAvailabilityAttributes (REQUIRED)
    selected_attributes = {
        "dealerAssociateUuidList": advisor_uuids
    }
    
    # Add optional attributes
    if team_uuids:
        selected_attributes["teamUuidList"] = team_uuids
    if transport_option_uuids:
        selected_attributes["transportOptionUuidList"] = transport_option_uuids
    
    # Build request payload
    request_payload = {
        "selectedAvailabilityAttributes": selected_attributes
    }
    
    # Add optional fields
    if dates:
        request_payload["dates"] = dates
    if start_time:
        request_payload["startTime"] = start_time
    if end_time:
        request_payload["endTime"] = end_time
    if opcodes:
        request_payload["selectedOperationUuidSet"] = opcodes
    
    # Initialize API client with basic auth
    config = KAppointmentAPIConfig(
        mkid=mkid,
        basic_auth_username=basic_auth_username,
        basic_auth_password=basic_auth_password
    )
    client = KAppointmentAPIClient(config=config)
    
    try:
        # Call the API
        result = await client.get_first_available_slot(department_uuid, request_payload)
        
        # Format the response
        formatted_result = _format_first_available_slot_response(result, uuid_mapper)
        
        return {
            "formatted_summary": formatted_result,
            "raw_data": result,
            "has_data": bool(result.get("dateTime"))
        }
    except Exception as e:
        logger.error(f"Error in get_first_available_slot_tool_impl: {e}")
        return {
            "formatted_summary": f"Error finding first available slot: {str(e)}",
            "raw_data": None,
            "has_data": False
        }
    finally:
        await client.close()


async def search_opcode_tool_impl(
    concern_text: str,
    dealer_uuid: str,
    mkid: Optional[str] = None,
) -> Dict[str, Any]:
    """Search for opcodes using RAG endpoint.
    
    This tool uses a RAG (Retrieval Augmented Generation) endpoint to find opcodes
    that match a user's concern text. Use this tool FIRST when a user mentions
    a service/opcode by name (e.g., "oil change", "tire rotation") and you need
    to find the corresponding opcode UUID to use in other tools like get_capacity.
    
    Args:
        concern_text: User's concern or query text (e.g., "oil change", "Why can't I book for oil change?")
        dealer_uuid: Dealer UUID (required for the API endpoint)
        mkid: MyKaarma cookie ID for authentication
        
    Returns:
        Dictionary with:
            - formatted_summary: Human-readable list of matched opcodes with UUIDs
            - raw_data: Full API response
            - opcode_uuids: List of opcode UUIDs found (for easy extraction by LLM)
            - opcode_names: List of opcode names found
            - has_data: Boolean indicating if any opcodes were found
        
    Example:
        >>> result = await search_opcode_tool_impl(
        ...     concern_text="oil change",
        ...     dealer_uuid="dealer-123",
        ...     mkid="mkid-value"
        ... )
        >>> print(result["opcode_uuids"])
        ["-INfX47G-DQLknoXOhTxr2Al8v7GC90wCg998hwYkwQ"]
    """
    # Initialize API client with mkid if provided
    config = KAppointmentAPIConfig(mkid=mkid) if mkid else None
    client = KAppointmentAPIClient(config=config)
    
    try:
        # Call the API
        result = await client.search_opcode(dealer_uuid, concern_text)
        
        # Extract opcode UUIDs and names for easy access
        matched_opcodes = result.get("matchedOpcodes", [])
        opcode_uuids = []
        opcode_names = []
        
        for match in matched_opcodes:
            operation_dto = match.get("operationDTO", {})
            uuid = operation_dto.get("uuid")
            name = operation_dto.get("opCodeName") or operation_dto.get("laborOpCode")
            
            if uuid:
                opcode_uuids.append(uuid)
            if name:
                opcode_names.append(name)
        
        # Format the response
        formatted_result = _format_opcode_search_response(result)
        
        return {
            "formatted_summary": formatted_result,
            "raw_data": result,
            "opcode_uuids": opcode_uuids,
            "opcode_names": opcode_names,
            "has_data": len(opcode_uuids) > 0
        }
    except Exception as e:
        logger.error(f"Error in search_opcode_tool_impl: {e}")
        return {
            "formatted_summary": f"Error searching for opcodes: {str(e)}",
            "raw_data": None,
            "opcode_uuids": [],
            "opcode_names": [],
            "has_data": False
        }
    finally:
        await client.close()

