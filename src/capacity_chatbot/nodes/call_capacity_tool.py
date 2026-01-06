"""Simple node that calls the get_capacity tool directly."""

import logging
import os
import asyncio
from datetime import datetime, timedelta

from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.tools import (
    get_capacity_tool_impl,
    CapacityType,
    ApplicabilityRuleField,
    RuleMatchingCriteria
)

logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> str:
    """Parse date string to YYYY-MM-DD format.
    
    Handles relative dates like "tomorrow", "today", etc.
    """
    date_str_lower = date_str.lower().strip()
    today = datetime.now().date()
    
    if date_str_lower == "today":
        return today.strftime("%Y-%m-%d")
    elif date_str_lower == "tomorrow":
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif date_str_lower == "yesterday":
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        # Assume it's already in YYYY-MM-DD format or try to parse
        try:
            # Try parsing common formats
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                try:
                    parsed = datetime.strptime(date_str, fmt).date()
                    return parsed.strftime("%Y-%m-%d")
                except ValueError:
                    continue
            # If all parsing fails, return as-is (might be invalid)
            return date_str
        except Exception:
            return date_str


def call_capacity_tool(state: CapacityChatbotState) -> CapacityChatbotState:
    """Call the get_capacity tool to fetch capacity for the department.
    
    This node extracts entities from the state and calls the getCapacity tool.
    """
    # Get department_uuid
    department_uuid = state.department_uuid
    if not department_uuid:
        # Try to get from env as fallback
        department_uuid = os.getenv("DEFAULT_DEPARTMENT_UUID")
        if department_uuid:
            state.department_uuid = department_uuid
            logger.info(f"Using default department_uuid from env: {department_uuid}")
        else:
            state.errors.append("Department UUID is required for fetching capacity")
            return state
    
    # Extract entities from state
    entities = state.extracted_entities
    dates = entities.get("dates", [])
    
    # Parse dates
    parsed_dates = [parse_date(d) for d in dates] if dates else []
    
    # If no dates provided, default to tomorrow
    if not parsed_dates:
        tomorrow = (datetime.now() + timedelta(days=1)).date().strftime("%Y-%m-%d")
        parsed_dates = [tomorrow]
        state.reasoning.append(f"No date provided, defaulting to tomorrow: {tomorrow}")
    
    # Build entity_map and field_combinations from extracted entities
    entity_map = {}
    field_combinations = []
    
    # Add transport options if specified
    transport_uuids = entities.get("transport_option_uuids", [])
    if transport_uuids:
        entity_map["TRANSPORT_OPTION_UUID"] = transport_uuids
        field_combinations.append(["TRANSPORT_OPTION_UUID"])
    
    # Add advisors if specified
    advisor_uuids = entities.get("advisor_uuids", [])
    if advisor_uuids:
        entity_map["DEALER_ASSOCIATE_UUID"] = advisor_uuids
        if ["DEALER_ASSOCIATE_UUID"] not in field_combinations:
            field_combinations.append(["DEALER_ASSOCIATE_UUID"])
    
    # Add teams if specified
    team_uuids = entities.get("team_uuids", [])
    if team_uuids:
        entity_map["TEAM_UUID"] = team_uuids
        if ["TEAM_UUID"] not in field_combinations:
            field_combinations.append(["TEAM_UUID"])
    
    # If no field combinations specified, get overall capacity
    if not field_combinations:
        field_combinations = []
    
    try:
        # Call the tool
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            get_capacity_tool_impl(
                department_uuid=department_uuid,
                applicability_rule_field=ApplicabilityRuleField.DATE,
                applicability_field_values=parsed_dates,
                capacity_type_set=[CapacityType.APPOINTMENT_COUNT],
                entity_map=entity_map if entity_map else None,
                field_combinations=field_combinations if field_combinations else None,
                rule_matching_criteria=RuleMatchingCriteria.INCLUSIVELY_MATCHES
            )
        )
        
        # Store result in state
        state.capacity_data = result
        state.reasoning.append(
            f"Successfully fetched capacity for dates: {parsed_dates}"
        )
        logger.info(f"Fetched capacity data for {len(parsed_dates)} date(s)")
        
        # Format capacity for response
        capacity_map = result.get("capacityMap", {})
        if capacity_map:
            appointment_count = capacity_map.get("APPOINTMENT_COUNT", {})
            if appointment_count:
                capacity_summary = f"Capacity Information for {', '.join(parsed_dates)}:\n\n"
                for date, entity_capacity in appointment_count.items():
                    capacity_summary += f"Date: {date}\n"
                    combo_capacity = entity_capacity.get("combinationWiseCapacity", {})
                    for combo_key, capacity in combo_capacity.items():
                        used = capacity.get("usedCount", 0)
                        total = capacity.get("totalCount", 0)
                        available = total - used if total != float('inf') else "unlimited"
                        capacity_summary += f"  {combo_key}: {used} used, {total} total, {available} available\n"
                    capacity_summary += "\n"
                state.response_message = capacity_summary
            else:
                state.response_message = f"No appointment count capacity data found for {', '.join(parsed_dates)}."
        else:
            state.response_message = f"No capacity data found for {', '.join(parsed_dates)}."
        
    except Exception as e:
        logger.error(f"Error calling get_capacity tool: {e}")
        state.errors.append(f"Error fetching capacity: {str(e)}")
        state.response_message = f"I encountered an error while fetching capacity: {str(e)}"
    
    return state

