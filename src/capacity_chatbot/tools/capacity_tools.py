"""LangChain tools for capacity chatbot ReAct agent.

These tools wrap the tool implementations and provide access to state via config.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.tools import (
    get_rules_tool_impl,
    get_capacity_tool_impl,
    get_first_available_slot_tool_impl,
    search_opcode_tool_impl,
)
from capacity_chatbot.tools import CapacityType, ApplicabilityRuleField, RuleMatchingCriteria
from capacity_chatbot.tools.knowledge_base_tools import KNOWLEDGE_BASE_TOOLS

logger = logging.getLogger(__name__)


@tool
async def get_rules_tool(
    rule_type: Optional[str] = None,
    config: RunnableConfig = None,  # Automatically provided by ReAct agent
) -> str:
    """Fetch capacity and assignment rules for the department.
    
    There are two types of rules:
    1. CAPACITY RULES: Define constraints on appointment capacity
    2. ASSIGNMENT RULES: Control how appointments are assigned to advisors/teams
    
    Use this tool when the user asks about:
    - "What are the rules?" → Fetch both types (default)
    - "What are the capacity rules?" → Use rule_type="CAPACITY"
    - "What are the assignment rules?" → Use rule_type="ASSIGNMENT"
    
    Args:
        rule_type: Optional rule type filter. Use 'CAPACITY' for capacity rules only,
                  'ASSIGNMENT' for assignment rules only, or leave empty to fetch both.
        config: RunnableConfig containing state (automatically provided by ReAct agent)
    
    Returns:
        Human-readable formatted summary of rules
    """
    if not config:
        return "Error: Config not available"
    
    state: CapacityChatbotState = config.get("configurable", {}).get("state")
    
    if not state:
        return "Error: State not available"
    
    # Get department_uuid and mkid from state
    department_uuid = state.department_uuid or os.getenv("DEFAULT_DEPARTMENT_UUID")
    if not department_uuid:
        return "Error: Department UUID is required"
    
    mkid = state.mkid or os.getenv("MYKAARMA_MKID")
    cached_data = state.cached_data or {}
    
    # Determine rule_type_list based on input
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
    
    try:
        result = await get_rules_tool_impl(
            department_uuid=department_uuid,
            dealer_uuid_list=[],
            result_size=100,
            start_position=0,
            rule_status_list=["ACTIVE"],
            rule_type_list=rule_type_list,
            mkid=mkid,
            cached_data=cached_data,
        )
        
        # Return formatted summary
        if isinstance(result, dict) and "formatted_summary" in result:
            return result["formatted_summary"]
        else:
            return str(result)
    except Exception as e:
        logger.error(f"Error in get_rules_tool: {e}", exc_info=True)
        return f"Error fetching rules: {str(e)}"


@tool
async def get_capacity_tool(
    dates: Optional[List[str]] = None,
    transport_option_names: Optional[List[str]] = None,
    advisor_names: Optional[List[str]] = None,
    opcodes: Optional[List[str]] = None,
    config: RunnableConfig = None,  # Automatically provided by ReAct agent
) -> str:
    """Fetch capacity information for appointments with detailed diagnostics.
    
    This tool retrieves capacity data showing:
    - How many appointments are used vs available
    - Service hours capacity
    - Capacity broken down by advisors, transport options, teams, operations
    - DIAGNOSTIC INFORMATION: Always includes detailed diagnostics showing:
      * All contributing limits (dealer schedule, individual schedule, rules, transport options, operations)
      * The bottleneck (which limit is constraining capacity)
      * Detailed reasoning for why capacity is limited
      * Step-by-step actionable advice on how to increase capacity
    
    Use this tool when the user asks about:
    - "What's the capacity for tomorrow?"
    - "How many slots are available?"
    - "What's the capacity for advisor X?"
    - "Show me capacity for loaner transport"
    - "Why can't I book for tomorrow?"
    - "What's the capacity for oil change?" (requires opcode UUID from search_opcode tool)
    
    CRITICAL - COMBINE MULTIPLE FILTERS IN ONE CALL:
    - If user asks for capacity with MULTIPLE filters (e.g., "loaner AND Vishal"),
      you MUST combine them in a SINGLE get_capacity call with BOTH parameters
    - If user mentions a service/opcode, FIRST call search_opcode to get opcode UUID,
      THEN use that UUID in get_capacity with opcodes parameter
    
    Args:
        dates: List of dates in YYYY-MM-DD format (e.g., ['2025-12-29']).
               Defaults to tomorrow if not provided.
        transport_option_names: List of transport option names (e.g., ['loaner', 'shuttle']).
                               Will be automatically mapped to UUIDs.
        advisor_names: List of advisor names (e.g., ['Vishal', 'Art']).
                      Will be automatically mapped to UUIDs.
        opcodes: List of opcode/operation UUIDs (e.g., ['-INfX47G-DQLknoXOhTxr2Al8v7GC90wCg998hwYkwQ']).
                Use opcode UUIDs from search_opcode tool. These are already UUIDs (no mapping needed).
        config: RunnableConfig containing state (automatically provided by ReAct agent)
    
    Returns:
        Human-readable formatted summary with diagnostics
    """
    if not config:
        return "Error: Config not available"
    
    state: CapacityChatbotState = config.get("configurable", {}).get("state")
    
    if not state:
        return "Error: State not available"
    
    # Get department_uuid and mkid from state
    department_uuid = state.department_uuid or os.getenv("DEFAULT_DEPARTMENT_UUID")
    if not department_uuid:
        return "Error: Department UUID is required"
    
    mkid = state.mkid or os.getenv("MYKAARMA_MKID")
    cached_data = state.cached_data or {}
    
    # Debug: Log initial state
    logger.info(f"get_capacity_tool called with transport_option_names={transport_option_names}, advisor_names={advisor_names}, opcodes={opcodes}, dates={dates}")
    logger.info(f"Initial cached_data type: {type(cached_data)}, empty: {not cached_data}, keys: {list(cached_data.keys()) if isinstance(cached_data, dict) else 'N/A'}")
    
    # Ensure cached_data is available (load test data if needed)
    if not cached_data:
        logger.warning("cached_data is empty, attempting to load test data...")
        from capacity_chatbot.utils.test_data import ensure_cached_data
        ensure_cached_data(state)
        cached_data = state.cached_data or {}
        logger.info(f"After ensure_cached_data: cached_data type: {type(cached_data)}, empty: {not cached_data}, keys: {list(cached_data.keys()) if isinstance(cached_data, dict) else 'N/A'}")
    
    # Check transport_options structure
    if cached_data and isinstance(cached_data, dict):
        transport_options = cached_data.get("transport_options", [])
        logger.info(f"Found {len(transport_options)} transport options in cached_data")
        if transport_options:
            first_transport = transport_options[0]
            logger.info(f"First transport option keys: {list(first_transport.keys()) if isinstance(first_transport, dict) else 'N/A'}")
            logger.info(f"First transport option: {first_transport}")
    
    # Use UUID mapper to convert names to UUIDs
    from capacity_chatbot.utils.uuid_mapper import UUIDMapper
    uuid_mapper = UUIDMapper(cached_data) if cached_data else None
    
    # Debug logging
    if transport_option_names:
        logger.info(f"Attempting to map transport option names: {transport_option_names}")
        if uuid_mapper:
            logger.info(f"UUIDMapper has {len(uuid_mapper.transport_map)} transport options mapped: {list(uuid_mapper.transport_map.values())}")
            logger.info(f"UUIDMapper transport_map keys (UUIDs): {list(uuid_mapper.transport_map.keys())[:2]}...")  # Show first 2 UUIDs
        else:
            logger.warning("UUIDMapper is None - cached_data might be empty or invalid")
    
    # Map transport option names to UUIDs
    final_transport_option_uuids = []
    if transport_option_names and uuid_mapper:
        for name in transport_option_names:
            uuid = uuid_mapper.get_transport_uuid_by_name(name)
            if uuid:
                final_transport_option_uuids.append(uuid)
            else:
                logger.warning(f"Could not map transport option name '{name}' to UUID. Available options: {list(uuid_mapper.transport_map.values())}")
    elif transport_option_names and not uuid_mapper:
        logger.warning(f"Transport option names provided ({transport_option_names}) but UUIDMapper is None (cached_data missing?)")
    
    # Map advisor names to UUIDs
    final_advisor_uuids = []
    if advisor_names and uuid_mapper:
        for name in advisor_names:
            uuid = uuid_mapper.get_advisor_uuid_by_name(name)
            if uuid:
                final_advisor_uuids.append(uuid)
            else:
                logger.warning(f"Could not map advisor name '{name}' to UUID. Available advisors: {list(uuid_mapper.advisor_map.values())}")
    elif advisor_names and not uuid_mapper:
        logger.warning(f"Advisor names provided ({advisor_names}) but UUIDMapper is None (cached_data missing?)")
    
    # Fallback to cached data if no names provided
    if not final_transport_option_uuids:
        final_transport_option_uuids = cached_data.get("transport_option_uuids", [])
    if not final_advisor_uuids:
        final_advisor_uuids = cached_data.get("advisor_uuids", [])
    
    final_team_uuids = cached_data.get("team_uuids", [])
    
    # Handle dates - validate and default to tomorrow if needed
    from datetime import datetime, timedelta
    today = datetime.now().date()
    
    if not dates:
        tomorrow = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        dates = [tomorrow]
    else:
        # Validate dates
        validated_dates = []
        for date_str in dates:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                if date_obj.year < 2024 or date_obj < (today - timedelta(days=365)):
                    continue
                validated_dates.append(date_str)
            except ValueError:
                continue
        
        if not validated_dates:
            tomorrow = (today + timedelta(days=1)).strftime("%Y-%m-%d")
            dates = [tomorrow]
        else:
            dates = validated_dates
    
    # Build entity map and field combinations
    entity_map = {}
    field_combinations = []
    
    if final_transport_option_uuids:
        entity_map["TRANSPORT_OPTION_UUID"] = final_transport_option_uuids
        field_combinations.append(["TRANSPORT_OPTION_UUID"])
        logger.info(f"Mapped transport options to UUIDs: {final_transport_option_uuids}")
    elif transport_option_names:
        logger.warning(f"Transport option names provided ({transport_option_names}) but no UUIDs were mapped. entity_map will be empty!")
    
    if final_advisor_uuids:
        entity_map["DEALER_ASSOCIATE_UUID"] = final_advisor_uuids
        if ["DEALER_ASSOCIATE_UUID"] not in field_combinations:
            field_combinations.append(["DEALER_ASSOCIATE_UUID"])
        logger.info(f"Mapped advisors to UUIDs: {final_advisor_uuids}")
    elif advisor_names:
        logger.warning(f"Advisor names provided ({advisor_names}) but no UUIDs were mapped. entity_map will be empty!")
    
    if final_team_uuids:
        entity_map["TEAM_UUID"] = final_team_uuids
        if ["TEAM_UUID"] not in field_combinations:
            field_combinations.append(["TEAM_UUID"])
        logger.info(f"Using team UUIDs: {final_team_uuids}")
    
    # Handle opcodes (these are already UUIDs, no mapping needed)
    if opcodes:
        entity_map["OPERATION_UUID"] = opcodes
        if ["OPERATION_UUID"] not in field_combinations:
            field_combinations.append(["OPERATION_UUID"])
        logger.info(f"Using opcode UUIDs: {opcodes}")
    
    if not entity_map:
        logger.warning("entity_map is empty! This will cause EMPTY_ENTITY_MAP error. Check if transport_option_names/advisor_names/opcodes were provided and mapped correctly.")
    
    try:
        result = await get_capacity_tool_impl(
            department_uuid=department_uuid,
            applicability_rule_field=ApplicabilityRuleField.DATE,
            applicability_field_values=dates,
            capacity_type_set=[CapacityType.APPOINTMENT_COUNT],
            entity_map=entity_map if entity_map else None,
            field_combinations=field_combinations if field_combinations else None,
            rule_matching_criteria=RuleMatchingCriteria.EXACTLY_MATCHES,
            mkid=mkid,
            cached_data=cached_data,
        )
        
        # Return formatted summary
        if isinstance(result, dict) and "formatted_summary" in result:
            return result["formatted_summary"]
        else:
            return str(result)
    except Exception as e:
        logger.error(f"Error in get_capacity_tool: {e}", exc_info=True)
        return f"Error fetching capacity: {str(e)}"


@tool
async def get_first_available_slot_tool(
    advisor_names: Optional[List[str]] = None,
    team_names: Optional[List[str]] = None,
    transport_option_names: Optional[List[str]] = None,
    dates: Optional[List[str]] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    opcodes: Optional[List[str]] = None,
    config: RunnableConfig = None,  # Automatically provided by ReAct agent
) -> str:
    """Find the first available appointment slot based on selected criteria.
    
    Use this tool when the user asks:
    - "When is the first available appointment?"
    - "Find me the next available slot"
    - "What's the earliest I can book?"
    
    IMPORTANT:
    - At least one advisor is REQUIRED by the API
    - If user only specifies transport option or team, the tool will automatically use ALL available advisors
    - Use advisor_names, team_names, transport_option_names (not UUIDs) - they will be auto-mapped
    
    Args:
        advisor_names: List of advisor names (e.g., ['Vishal', 'Art'])
        team_names: List of team names (e.g., ['Express Shop'])
        transport_option_names: List of transport option names (e.g., ['loaner'])
        dates: List of start dates in YYYY-MM-DD format
        start_time: Start time in HH:mm:ss format (optional)
        end_time: End time in HH:mm:ss format (optional)
        opcodes: List of opcode UUIDs (optional)
        config: RunnableConfig containing state (automatically provided by ReAct agent)
    
    Returns:
        Human-readable formatted summary with first available slot
    """
    if not config:
        return "Error: Config not available"
    
    state: CapacityChatbotState = config.get("configurable", {}).get("state")
    
    if not state:
        return "Error: State not available"
    
    # Get department_uuid and mkid from state
    department_uuid = state.department_uuid or os.getenv("DEFAULT_DEPARTMENT_UUID")
    if not department_uuid:
        return "Error: Department UUID is required"
    
    mkid = state.mkid or os.getenv("MYKAARMA_MKID")
    basic_auth_username = os.getenv("KAPPOINTMENT_API_USERNAME", "1")
    basic_auth_password = os.getenv("KAPPOINTMENT_API_PASSWORD", "1")
    cached_data = state.cached_data or {}
    
    try:
        result = await get_first_available_slot_tool_impl(
            department_uuid=department_uuid,
            advisor_names=advisor_names,
            team_names=team_names,
            transport_option_names=transport_option_names,
            dates=dates,
            start_time=start_time,
            end_time=end_time,
            opcodes=opcodes,
            mkid=mkid,
            basic_auth_username=basic_auth_username,
            basic_auth_password=basic_auth_password,
            cached_data=cached_data,
        )
        
        # Return formatted summary
        if isinstance(result, dict) and "formatted_summary" in result:
            return result["formatted_summary"]
        else:
            return str(result)
    except Exception as e:
        logger.error(f"Error in get_first_available_slot_tool: {e}", exc_info=True)
        return f"Error finding first available slot: {str(e)}"


@tool
async def search_opcode_tool(
    concern_text: str,
    config: RunnableConfig = None,  # Automatically provided by ReAct agent
) -> str:
    """Search for opcodes/services using RAG (Retrieval Augmented Generation).
    
    Use this tool FIRST when:
    - User mentions a service/opcode by name (e.g., "oil change", "tire rotation")
    - User asks "Why can't I book for [service]?" and you need to find the opcode UUID
    
    IMPORTANT WORKFLOW:
    1. When user mentions a service by name → Call search_opcode FIRST
    2. Extract opcode UUIDs from the response
    3. Use those UUIDs in get_capacity or other tools that need opcode UUIDs
    
    Args:
        concern_text: User's concern or query text (e.g., "oil change", "Why can't I book for oil change?")
        config: RunnableConfig containing state (automatically provided by ReAct agent)
    
    Returns:
        Human-readable formatted summary with opcode UUIDs and names
    """
    if not config:
        return "Error: Config not available"
    
    state: CapacityChatbotState = config.get("configurable", {}).get("state")
    
    if not state:
        return "Error: State not available"
    
    # Get dealer_uuid and mkid from state
    dealer_uuid = state.dealer_uuid or os.getenv("DEFAULT_DEALER_UUID")
    if not dealer_uuid:
        return "Error: Dealer UUID is required for opcode search"
    
    mkid = state.mkid or os.getenv("MYKAARMA_MKID")
    
    try:
        result = await search_opcode_tool_impl(
            concern_text=concern_text,
            dealer_uuid=dealer_uuid,
            mkid=mkid,
        )
        
        # Return formatted summary
        if isinstance(result, dict) and "formatted_summary" in result:
            return result["formatted_summary"]
        else:
            return str(result)
    except Exception as e:
        logger.error(f"Error in search_opcode_tool: {e}", exc_info=True)
        return f"Error searching opcode: {str(e)}"


# List of all tools for ReAct agent
# Knowledge base tools come first for query routing priority
CAPACITY_TOOLS = [
    *KNOWLEDGE_BASE_TOOLS,  # get_knowledge_answer, get_available_entities
    get_rules_tool,
    get_capacity_tool,
    get_first_available_slot_tool,
    search_opcode_tool,
]


