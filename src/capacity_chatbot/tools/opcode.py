"""Search opcode tool for capacity chatbot.

This module contains everything related to the search_opcode tool.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.clients.kopcode_client import KopcodeAPIClient
from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.config import KAppointmentAPIConfig

logger = logging.getLogger(__name__)


# =============================================================================
# Tool Wrapper
# =============================================================================

@tool
async def search_opcode_tool(
    concern_text: Optional[str] = None,
    list_all_with_limits: bool = False,
    config: RunnableConfig = None,
) -> str:
    """Search for opcodes/services OR list all opcodes with daily limits.
    
    TWO MODES:
    1. SEARCH MODE (concern_text provided): RAG search for specific service
       - "Oil change capacity" → search_opcode(concern_text="oil change")
       - Returns matching opcodes with UUIDs for use with get_capacity
    
    2. LIST LIMITS MODE (list_all_with_limits=True): Get ALL opcodes with restrictions
       - "What opcode restrictions are there?" → search_opcode(list_all_with_limits=True)
       - Returns only opcodes that have daily limits configured
    
    NOTE: For FULL opcode restrictions, also call get_rules(entity_type="opcode") 
    to get capacity/assignment rules. Show rules first, then daily limits.
    
    Args:
        concern_text: Service name/keywords for search mode (e.g., "oil change", "brake")
        list_all_with_limits: If True, returns ALL opcodes with daily limits configured
        config: RunnableConfig (automatically provided)
    
    Returns:
        Opcode details including UUID and daily limits
    """
    if not config:
        return "Error: Config not available"
    
    state: CapacityChatbotState = config.get("configurable", {}).get("state")
    if not state:
        return "Error: State not available"
    
    # UUIDs must come from UI client via state - no env var fallbacks
    dealer_uuid = state.dealer_uuid
    department_uuid = state.department_uuid
    mkid = state.mkid
    
    try:
        if list_all_with_limits:
            # MODE 2: Get all opcodes with daily limits
            if not department_uuid:
                return "Error: Department UUID is required for listing opcodes with limits"
            result = await _fetch_operations_with_limits_impl(department_uuid=department_uuid, mkid=mkid)
        else:
            # MODE 1: Search for specific opcode
            if not concern_text:
                return "Error: Either concern_text or list_all_with_limits=True is required"
            if not dealer_uuid:
                return "Error: Dealer UUID is required for opcode search"
            result = await _search_opcode_impl(concern_text=concern_text, dealer_uuid=dealer_uuid, mkid=mkid)
        
        if isinstance(result, dict) and "formatted_summary" in result:
            return result["formatted_summary"]
        return str(result)
    except Exception as e:
        logger.error(f"Error in search_opcode_tool: {e}", exc_info=True)
        return f"Error: {str(e)}"


# =============================================================================
# Implementation
# =============================================================================

async def _search_opcode_impl(
    concern_text: str,
    dealer_uuid: str,
    mkid: Optional[str] = None,
) -> Dict[str, Any]:
    """Search for opcodes using RAG endpoint."""
    config = KAppointmentAPIConfig(mkid=mkid) if mkid else None
    client = KopcodeAPIClient(config=config)
    
    try:
        result = await client.search_opcode(dealer_uuid, concern_text)
        
        matched_opcodes = result.get("matchedOpcodes", [])
        opcode_uuids = []
        opcode_names = []
        
        for match in matched_opcodes:
            op = match.get("operationDTO", {})
            if op.get("uuid"):
                opcode_uuids.append(op["uuid"])
            if op.get("opCodeName") or op.get("laborOpCode"):
                opcode_names.append(op.get("opCodeName") or op.get("laborOpCode"))
        
        formatted = _format_opcode_response(result)
        
        return {
            "formatted_summary": formatted,
            "raw_data": result,
            "opcode_uuids": opcode_uuids,
            "opcode_names": opcode_names,
            "has_data": len(opcode_uuids) > 0
        }
    except Exception as e:
        logger.error(f"Error in _search_opcode_impl: {e}")
        return {"formatted_summary": f"Error: {str(e)}", "raw_data": None, "opcode_uuids": [], "opcode_names": [], "has_data": False}
    finally:
        await client.close()


async def _fetch_operations_with_limits_impl(
    department_uuid: str,
    mkid: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch all opcodes with daily limits configured."""
    config = KAppointmentAPIConfig(mkid=mkid) if mkid else KAppointmentAPIConfig()
    client = KAppointmentAPIClient(config=config)
    
    try:
        result = await client.fetch_operations_with_limits(department_uuid)
        
        operation_list = result.get("operationList", [])
        
        formatted = _format_operations_with_limits(operation_list)
        
        return {
            "formatted_summary": formatted,
            "raw_data": result,
            "operation_count": len(operation_list),
            "has_data": len(operation_list) > 0
        }
    except Exception as e:
        logger.error(f"Error in _fetch_operations_with_limits_impl: {e}")
        return {"formatted_summary": f"Error: {str(e)}", "raw_data": None, "operation_count": 0, "has_data": False}
    finally:
        await client.close()


# =============================================================================
# Formatters
# =============================================================================

DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

def _format_opcode_response(result: Dict[str, Any]) -> str:
    """Format opcode search response."""
    if not result or "matchedOpcodes" not in result:
        return "No opcodes found matching your query."
    
    matched = result.get("matchedOpcodes", [])
    if not matched:
        return "No opcodes found matching your query. Try different keywords."
    
    parts = [f"Found {len(matched)} matching opcode(s):\n"]
    
    for idx, match in enumerate(matched, 1):
        op = match.get("operationDTO", {})
        score = match.get("score", 0.0)
        
        name = op.get("opCodeName", "Unknown")
        uuid = op.get("uuid", "Unknown")
        desc = op.get("description", "")
        labor = op.get("laborOpCode", "")
        duration = op.get("opCodeDurationInMinutes", "")
        
        text = f"{idx}. **{name}**"
        if labor and labor != name:
            text += f" ({labor})"
        text += f"\n   - UUID: {uuid}\n"
        if desc:
            text += f"   - Description: {desc}\n"
        if duration:
            text += f"   - Duration: {duration} minutes\n"
        text += f"   - Match Score: {score:.2%}\n"
        
        # Add daily limits if available
        daily_limits = op.get("dailyLimitConfigDTOList", [])
        if daily_limits:
            limit_parts = []
            for limit_config in daily_limits:
                day_num = limit_config.get("dayNumber", 0)
                day_limit = limit_config.get("dayLimit", 0)
                day_name = DAY_NAMES[day_num] if 0 <= day_num < 7 else f"Day {day_num}"
                
                if day_limit >= 2147483647:  # Max int = unlimited
                    limit_parts.append(f"{day_name}: Unlimited")
                elif day_limit == 0:
                    limit_parts.append(f"{day_name}: Blocked")
                else:
                    limit_parts.append(f"{day_name}: {day_limit}")
            
            text += f"   - Daily Limits: {', '.join(limit_parts)}\n"
        
        parts.append(text)
    
    return "\n".join(parts)


def _format_operations_with_limits(operation_list: List[Dict[str, Any]]) -> str:
    """Format operations with limits response."""
    if not operation_list:
        return "No opcodes with daily limits configured."
    
    # Filter to only opcodes that have at least one non-unlimited day
    MAX_INT = 2147483647
    filtered_ops = []
    for op in operation_list:
        daily_limits = op.get("dailyLimitConfigList", [])
        has_actual_limit = any(
            lc.get("dayLimit", MAX_INT) < MAX_INT 
            for lc in daily_limits
        )
        if has_actual_limit:
            filtered_ops.append(op)
    
    if not filtered_ops:
        return "No opcodes with daily limits configured. All opcodes have unlimited capacity."
    
    parts = [f"📋 **Opcodes with Daily Limits** ({len(filtered_ops)} total):\n"]
    
    for idx, op in enumerate(filtered_ops, 1):
        name = op.get("opCodeName", "Unknown")
        labor = op.get("laborOpCode", "")
        desc = op.get("description", "")
        
        # Build header
        text = f"{idx}. **{name}**"
        if labor and labor != name:
            text += f" ({labor})"
        text += "\n"
        
        if desc:
            text += f"   {desc}\n"
        
        # Format daily limits - order Sun→Sat (dayNumber: 0=Sun, 1=Mon...6=Sat)
        daily_limits = op.get("dailyLimitConfigList", [])
        if daily_limits:
            # Create a dict indexed by dayNumber
            limits_by_day_num = {}
            for limit_config in daily_limits:
                day_num = limit_config.get("dayNumber", -1)
                day_limit = limit_config.get("dayLimit", 2147483647)
                limits_by_day_num[day_num] = day_limit
            
            # Day names: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
            day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
            limit_parts = []
            for day_num in range(7):
                limit = limits_by_day_num.get(day_num, 2147483647)
                day_name = day_names[day_num]
                
                if limit >= 2147483647:  # Max int = unlimited
                    limit_parts.append(f"{day_name}=∞")
                elif limit == 0:
                    limit_parts.append(f"{day_name}=❌")
                else:
                    limit_parts.append(f"{day_name}={limit}")
            
            text += f"   Limits: {', '.join(limit_parts)}\n"
        
        parts.append(text)
    
    return "\n".join(parts)

