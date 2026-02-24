"""Search opcode tool for capacity chatbot."""

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.config.api_config import KAppointmentAPIConfig
from capacity_chatbot.enums import MAX_LIMIT, DayName
from capacity_chatbot.utils.state_extractor import extract_state

logger = logging.getLogger(__name__)

# Constants
DAYS_IN_WEEK = 7

@tool
async def search_opcode_tool(
    concern_text: str | None = None,
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
    # Validate mutually exclusive parameters
    if list_all_with_limits and concern_text:
        return "Error: Cannot use both 'concern_text' and 'list_all_with_limits'. Use one mode at a time."

    if not list_all_with_limits and not concern_text:
        return "Error: Either 'concern_text' or 'list_all_with_limits' must be provided."

    state, error = extract_state(config)
    if error:
        return error

    try:
        if list_all_with_limits:
            # Get mkid from config (passed from request, not persisted in state)
            mkid = config.get("configurable", {}).get("mkid") if config else None
            # Let client handle mkid validation and raise exception if missing
            result = await _fetch_operations_with_limits(state.department_uuid, mkid)
        else:
            # Validate concern_text is not None/empty
            if not concern_text or not concern_text.strip():
                return "Error: Search term is required when using search mode."
            result = await _search_opcode(concern_text.strip(), state.department_uuid)
        return result.get("formatted_summary", str(result))
    except ValueError as e:
        # Client raises ValueError for missing mkid
        logger.error("Error in search_opcode_tool: %s", e, exc_info=True)
        return "Error: %s" % str(e)
    except Exception as e:
        logger.error("Error in search_opcode_tool: %s", e, exc_info=True)
        return "Error: %s" % str(e)

async def _search_opcode(
    search_token: str,
    department_uuid: str,
) -> dict[str, Any]:
    """Search for opcodes by name."""
    async with KAppointmentAPIClient(config=KAppointmentAPIConfig()) as client:
        result = await client.search_operations(department_uuid, search_token)
        formatted = _format_opcode_response(result)
        return {"formatted_summary": formatted, "raw_data": result}


async def _fetch_operations_with_limits(
    department_uuid: str,
    mkid: str | None = None,
) -> dict[str, Any]:
    """Fetch all opcodes with daily limits configured.

    Args:
        department_uuid: Department UUID
        mkid: Optional mkid cookie for authentication (required for webservice endpoint)
    """
    async with KAppointmentAPIClient(config=KAppointmentAPIConfig()) as client:
        result = await client.fetch_operations_with_limits(department_uuid, mkid=mkid)
        formatted = _format_operations_with_limits(result.get("operationList", []))
        return {"formatted_summary": formatted, "raw_data": result}

def _get_daily_limits_from_opcode(op: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract daily limits from opcode, handling different field names.

    Different API endpoints return different field names:
    - search_operations returns: dailyLimitConfigDTOList
    - fetch_operations_with_limits returns: dailyLimitConfigList
    """
    return op.get("dailyLimitConfigDTOList") or op.get("dailyLimitConfigList") or []


def _format_opcode_entry(
    op: dict[str, Any],
    idx: int,
    show_uuid: bool = True,
    show_duration: bool = True,
    full_limit_names: bool = True,
) -> str:
    """Format a single opcode entry.

    Args:
        op: Opcode dictionary
        idx: Index number for display
        show_uuid: Whether to show UUID
        show_duration: Whether to show duration
        full_limit_names: Whether to use full day names in limits
    """
    name = op.get("opCodeName", "Unknown")
    uuid = op.get("uuid", "Unknown")
    desc = op.get("description", "")
    labor = op.get("laborOpCode", "")
    duration = op.get("opCodeDurationInMinutes", "")

    text = "%d. **%s**" % (idx, name)
    if labor and labor != name:
        text += " (%s)" % labor

    if show_uuid:
        text += "\n   - UUID: %s\n" % uuid
    else:
        text += "\n"

    if desc:
        if show_uuid:
            text += "   - Description: %s\n" % desc
        else:
            text += "   %s\n" % desc

    if show_duration and duration:
        text += "   - Duration: %s minutes\n" % duration

    # Add daily limits if available
    limits = _format_daily_limits(_get_daily_limits_from_opcode(op), full_names=full_limit_names)
    if limits:
        if show_uuid:
            text += "   - Daily Limits: %s\n" % limits
        else:
            text += "   Limits: %s\n" % limits

    return text


def _format_opcode_response(result: dict[str, Any]) -> str:
    """Format opcode search response."""
    operations = result.get("operationList", [])
    if not operations:
        return "No opcodes found matching your query. Try different keywords."

    parts = ["Found %d matching opcode(s):\n" % len(operations)]

    for idx, op in enumerate(operations, 1):
        parts.append(
            _format_opcode_entry(op, idx, show_uuid=True, show_duration=True, full_limit_names=True)
        )

    return "\n".join(parts)


def _format_operations_with_limits(operations: list[dict[str, Any]]) -> str:
    """Format operations with limits response."""
    if not operations:
        return "No opcodes with daily limits configured."

    # Filter to only opcodes with actual limits (not unlimited)
    filtered = [op for op in operations if _has_actual_limit(op)]

    if not filtered:
        return "No opcodes with daily limits configured. All opcodes have unlimited capacity."

    parts = ["📋 **Opcodes with Daily Limits** (%d total):\n" % len(filtered)]

    for idx, op in enumerate(filtered, 1):
        parts.append(
            _format_opcode_entry(
                op, idx, show_uuid=False, show_duration=False, full_limit_names=False
            )
        )

    return "\n".join(parts)

def _has_actual_limit(op: dict[str, Any]) -> bool:
    """Check if operation has at least one non-unlimited day."""
    limits = _get_daily_limits_from_opcode(op)
    for lc in limits:
        if lc.get("dayLimit", MAX_LIMIT) < MAX_LIMIT:
            return True
    return False


def _format_daily_limits(limits: list[dict[str, Any]], full_names: bool = False) -> str:
    """Format daily limits into readable string."""
    if not limits:
        return ""

    # Build day number → limit mapping
    limits_by_day = {}
    for lc in limits:
        day_num = lc.get("dayNumber")
        # Validate dayNumber is in valid range (0-6)
        if day_num is not None and 0 <= day_num < DAYS_IN_WEEK:
            day_limit = lc.get("dayLimit", MAX_LIMIT)
            limits_by_day[day_num] = day_limit

    # Format each day
    parts = []
    day_labels = DayName.all_full() if full_names else DayName.all_short()

    for day_num in range(DAYS_IN_WEEK):
        limit = limits_by_day.get(day_num, MAX_LIMIT)
        day_name = day_labels[day_num]

        if limit >= MAX_LIMIT:
            parts.append("%s: ∞" % day_name if full_names else "%s=∞" % day_name)
        elif limit == 0:
            parts.append("%s: Blocked" % day_name if full_names else "%s=❌" % day_name)
        else:
            parts.append(
                "%s: %d" % (day_name, limit) if full_names else "%s=%d" % (day_name, limit)
            )

    return ", ".join(parts)
