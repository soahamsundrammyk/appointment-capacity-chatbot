"""Search opcode tool for capacity chatbot."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.config.api_config import KAppointmentAPIConfig
from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.model.enums import DayName, MAX_LIMIT

logger = logging.getLogger(__name__)


# =============================================================================
# Main Tool
# =============================================================================


@tool
async def search_opcode_tool(
    concern_text: Optional[str] = None,
    list_all_with_limits: bool = False,
    config: RunnableConfig = None,
) -> str:
    """Search for opcodes or list all with daily limits.

    TWO MODES:
    1. SEARCH: Search by name → concern_text="oil change"
    2. LIST LIMITS: Get all opcodes with restrictions → list_all_with_limits=True

    For FULL opcode restrictions, also call get_rules(entity_type="opcode").

    Args:
        concern_text: Service name/keywords for search
        list_all_with_limits: If True, returns all opcodes with daily limits
        config: RunnableConfig (auto-provided)
    """
    state, error = _extract_state(config)
    if error:
        return error

    try:
        if list_all_with_limits:
            if not state.mkid:
                return "Error: Authentication required. Please ensure you're logged in with a valid session."
            result = await _fetch_operations_with_limits(state.department_uuid, state.mkid)
        else:
            result = await _search_opcode(concern_text, state.department_uuid)
        return result.get("formatted_summary", str(result))
    except Exception as e:
        logger.error(f"Error in search_opcode_tool: {e}", exc_info=True)
        return f"Error: {str(e)}"


# =============================================================================
# State Extraction
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


# =============================================================================
# API Calls
# =============================================================================


async def _search_opcode(
    search_token: str,
    department_uuid: str,
) -> Dict[str, Any]:
    """Search for opcodes by name."""
    if not search_token:
        return {"formatted_summary": "Error: Search term is required", "has_data": False}

    client = KAppointmentAPIClient(config=KAppointmentAPIConfig())

    try:
        result = await client.search_operations(department_uuid, search_token)
        formatted = _format_opcode_response(result)
        return {"formatted_summary": formatted, "raw_data": result}
    finally:
        await client.close()


async def _fetch_operations_with_limits(
    department_uuid: str,
    mkid: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch all opcodes with daily limits configured.
    
    Args:
        department_uuid: Department UUID
        mkid: Optional mkid cookie for authentication (required for webservice endpoint)
    """
    client = KAppointmentAPIClient(config=KAppointmentAPIConfig())

    try:
        result = await client.fetch_operations_with_limits(department_uuid, mkid=mkid)
        formatted = _format_operations_with_limits(result.get("operationList", []))
        return {"formatted_summary": formatted, "raw_data": result}
    finally:
        await client.close()


# =============================================================================
# Response Formatting
# =============================================================================


def _format_opcode_response(result: Dict[str, Any]) -> str:
    """Format opcode search response."""
    operations = result.get("operationList", [])
    if not operations:
        return "No opcodes found matching your query. Try different keywords."

    parts = [f"Found {len(operations)} matching opcode(s):\n"]

    for idx, op in enumerate(operations, 1):
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

        # Add daily limits if available
        limits = _format_daily_limits(op.get("dailyLimitConfigDTOList", []), full_names=True)
        if limits:
            text += f"   - Daily Limits: {limits}\n"

        parts.append(text)

    return "\n".join(parts)


def _format_operations_with_limits(operations: List[Dict[str, Any]]) -> str:
    """Format operations with limits response."""
    if not operations:
        return "No opcodes with daily limits configured."

    # Filter to only opcodes with actual limits (not unlimited)
    filtered = [op for op in operations if _has_actual_limit(op)]

    if not filtered:
        return "No opcodes with daily limits configured. All opcodes have unlimited capacity."

    parts = [f"📋 **Opcodes with Daily Limits** ({len(filtered)} total):\n"]

    for idx, op in enumerate(filtered, 1):
        name = op.get("opCodeName", "Unknown")
        labor = op.get("laborOpCode", "")
        desc = op.get("description", "")

        text = f"{idx}. **{name}**"
        if labor and labor != name:
            text += f" ({labor})"
        text += "\n"

        if desc:
            text += f"   {desc}\n"

        limits = _format_daily_limits(op.get("dailyLimitConfigList", []), full_names=False)
        if limits:
            text += f"   Limits: {limits}\n"

        parts.append(text)

    return "\n".join(parts)


# =============================================================================
# Utilities
# =============================================================================


def _has_actual_limit(op: Dict[str, Any]) -> bool:
    """Check if operation has at least one non-unlimited day."""
    for lc in op.get("dailyLimitConfigList", []):
        if lc.get("dayLimit", MAX_LIMIT) < MAX_LIMIT:
            return True
    return False


def _format_daily_limits(limits: List[Dict], full_names: bool = False) -> str:
    """Format daily limits into readable string."""
    if not limits:
        return ""

    # Build day number → limit mapping
    limits_by_day = {}
    for lc in limits:
        day_num = lc.get("dayNumber", -1)
        day_limit = lc.get("dayLimit", MAX_LIMIT)
        limits_by_day[day_num] = day_limit

    # Format each day
    parts = []
    day_labels = DayName.all_full() if full_names else DayName.all_short()

    for day_num in range(7):
        limit = limits_by_day.get(day_num, MAX_LIMIT)
        day_name = day_labels[day_num] if 0 <= day_num < 7 else f"Day {day_num}"

        if limit >= MAX_LIMIT:
            parts.append(f"{day_name}: ∞" if full_names else f"{day_name}=∞")
        elif limit == 0:
            parts.append(f"{day_name}: Blocked" if full_names else f"{day_name}=❌")
        else:
            parts.append(f"{day_name}: {limit}" if full_names else f"{day_name}={limit}")

    return ", ".join(parts)
