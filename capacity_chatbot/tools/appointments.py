"""Appointment data query tool for fetching and filtering appointment records.

Uses the same MongoDB-backed endpoint as appointment-ui-client for data consistency.
Endpoint: POST /webservice/dealers/{dealerUuid}/appointments
Data source: MongoDB AppointmentViewData collection (denormalized, names embedded)
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.utils.appointment_filters import AppointmentFilters, apply_filters
from capacity_chatbot.utils.appointment_formatter import (
    format_grouped_summary,
    format_list,
    format_summary,
)
from capacity_chatbot.utils.date_parser import format_date, parse_date_range
from capacity_chatbot.utils.state_extractor import extract_state
from capacity_chatbot.utils.uuid_mapper import UUIDMapper
from capacity_chatbot.utils.validation import (
    validate_advisor_names,
    validate_team_names,
    validate_transport_option_names,
)

logger = logging.getLogger(__name__)


@tool
async def get_appointments_tool(
    mode: str = "summary",
    start_date: str | None = None,
    end_date: str | None = None,
    start_created_date: str | None = None,
    end_created_date: str | None = None,
    team_names: list[str] | None = None,
    created_by_platform: str | None = None,
    advisor_names: list[str] | None = None,
    creator_advisor_names: list[str] | None = None,
    status: list[str] | None = None,
    transport_option_names: list[str] | None = None,
    repair_concerns: list[str] | None = None,
    has_recall: bool | None = None,
    prediag_status: list[str] | None = None,
    page: int = 1,
    page_size: int = 50,
    group_by: str | None = None,
    config: RunnableConfig = None,
) -> str:
    """Query appointment data with filters. Returns summary stats or paginated list.

    This tool queries the same data source as the appointment UI (MongoDB AppointmentViewData).
    Results are consistent with what the user sees in the appointment-ui-client.

    MODE:
    - "summary" (default): Returns total count and status breakdown.
      Add group_by to break down by: "advisor", "created_by", "team", "status", "source", "transport_option"
    - "list": Returns paginated appointment records with details.

    DATE FILTERS (at least one date filter is required):
    - start_date/end_date: Filter by appointment scheduled date (preferredDate)
    - start_created_date/end_created_date: Filter by when appointment was created
    - Accepts: "today", "yesterday", "this week", "last week", "this month",
      "last month", "last 7 days", "last 30 days", or "YYYY-MM-DD"

    ENTITY FILTERS:
    - advisor_names: Filter by assigned advisor (e.g., ["Diego"])
    - creator_advisor_names: Filter by who created the appointment (e.g., ["Maria"])
    - team_names: Filter by team (e.g., ["Express Shop"])
    - transport_option_names: Filter by transport (e.g., ["Loaner"])
    - status: Filter by status (e.g., ["Scheduled", "Cancelled", "No Show"])
    - created_by_platform: Filter by booking source ("Web", "DealerApp", "DMS")
    - repair_concerns: Filter by service/opcode name (e.g., ["Oil Change"])
    - has_recall: True to show only recall appointments, False to exclude them
    - prediag_status: Filter by AI survey status

    EXAMPLES:
    - "How many appts last month?" → mode="summary", start_date="last month"
    - "Diego's appointments this month" → mode="list", start_date="this month", advisor_names=["Diego"]
    - "Break down by advisor" → mode="summary", start_date="this month", group_by="advisor"
    - "Cancelled appointments this week" → mode="summary", start_date="this week", status=["Cancelled"]
    - "Web scheduler appointments" → mode="summary", start_date="this month", created_by_platform="Web"
    - "Appointments created last week" → mode="summary", start_created_date="last week"

    Args:
        mode: "summary" or "list"
        start_date: Scheduled date range start (natural language or YYYY-MM-DD)
        end_date: Scheduled date range end
        start_created_date: Created date range start
        end_created_date: Created date range end
        team_names: Team names to filter by
        created_by_platform: Platform source filter
        advisor_names: Assigned advisor names
        creator_advisor_names: Creator advisor names
        status: Status values to filter by
        transport_option_names: Transport option names
        repair_concerns: Service/opcode names
        has_recall: Recall filter
        prediag_status: Pre-diag status filter
        page: Page number for list mode (1-based)
        page_size: Page size for list mode
        group_by: Grouping dimension for summary mode
        config: RunnableConfig (automatically provided)

    Returns:
        Formatted appointment data string
    """
    # Extract state
    state, error = extract_state(config)
    if error:
        return error

    cached_data = state.cached_data
    uuid_mapper = UUIDMapper(cached_data)
    dealer_uuid = state.dealer_uuid

    if not dealer_uuid:
        return "Error: Dealer UUID is required for appointment queries."

    # Build the API request and date label
    date_range_label, api_request = _build_api_request(
        start_date, end_date, start_created_date, end_created_date,
    )

    if api_request is None:
        return "Please specify a date range (e.g., 'this month', 'last week', 'today')."

    # Resolve entity names to UUIDs for client-side filtering
    filters = _build_filters(
        advisor_names, creator_advisor_names, status, transport_option_names,
        team_names, repair_concerns, has_recall, prediag_status, created_by_platform,
        cached_data, uuid_mapper,
    )

    # Get mkid from config (passed from request auth, not persisted in state)
    mkid = config.get("configurable", {}).get("mkid") if config else None

    # Fetch appointments from the same endpoint as appointment-ui-client
    try:
        all_appointments = await _fetch_appointments(dealer_uuid, api_request, mkid)
    except Exception as e:
        logger.error("Failed to fetch appointments: %s", e)
        return "Error fetching appointment data. Please try again."

    # Apply client-side filters (same approach as appointment-ui-client)
    filtered = apply_filters(all_appointments, filters)

    # Format output
    if mode == "list":
        return format_list(filtered, uuid_mapper, page=page, page_size=page_size)
    elif group_by:
        return format_grouped_summary(filtered, group_by, date_range_label, uuid_mapper)
    else:
        return format_summary(filtered, date_range_label, uuid_mapper)


def _build_api_request(
    start_date: str | None,
    end_date: str | None,
    start_created_date: str | None,
    end_created_date: str | None,
) -> tuple[str, dict[str, Any] | None]:
    """Build the AppointmentViewDataRequest for the Mongo-backed webservice endpoint.

    The endpoint accepts either:
    - scheduledForDates: list of individual dates (for preferredDate filtering)
    - scheduledOnFromDate + scheduledOnToDate: date range (for creationDateTime filtering)

    Returns:
        Tuple of (date_range_label, api_request_dict) or (label, None) if no date range.
    """
    request: dict[str, Any] = {}
    date_range_label = ""

    # Parse scheduled date range → scheduledForDates (list of individual dates)
    if start_date or end_date:
        if start_date and not end_date:
            parsed = parse_date_range(start_date)
            if parsed:
                dates, actual_s, actual_e = _generate_date_list(parsed[0], parsed[1])
                request["scheduledForDates"] = dates
                date_range_label = "%s - %s" % (format_date(actual_s), format_date(actual_e))
        elif not start_date and end_date:
            end_parsed = parse_date_range(end_date)
            if end_parsed:
                e = end_parsed[1]
                s_date = datetime.strptime(e, "%Y-%m-%d").date() - timedelta(days=MAX_DATE_RANGE_DAYS - 1)
                s = s_date.strftime("%Y-%m-%d")
                dates, actual_s, actual_e = _generate_date_list(s, e)
                request["scheduledForDates"] = dates
                date_range_label = "up to %s" % format_date(actual_e)
        elif start_date and end_date:
            start_parsed = parse_date_range(start_date)
            end_parsed = parse_date_range(end_date)
            s = start_parsed[0] if start_parsed else None
            e = end_parsed[1] if end_parsed else None
            if not s or not e:
                return "", None
            dates, actual_s, actual_e = _generate_date_list(s, e)
            request["scheduledForDates"] = dates
            date_range_label = "%s - %s" % (format_date(actual_s), format_date(actual_e))

    # Parse created date range → scheduledOnFromDate/scheduledOnToDate
    if start_created_date or end_created_date:
        if start_created_date and not end_created_date:
            parsed = parse_date_range(start_created_date)
            if parsed:
                s, e = _cap_date_range(parsed[0], parsed[1])
                request["scheduledOnFromDate"] = s
                request["scheduledOnToDate"] = e
                if not date_range_label:
                    date_range_label = "created %s - %s" % (format_date(s), format_date(e))
        elif not start_created_date and end_created_date:
            end_parsed = parse_date_range(end_created_date)
            if end_parsed:
                e = end_parsed[1]
                s_date = datetime.strptime(e, "%Y-%m-%d").date() - timedelta(days=MAX_DATE_RANGE_DAYS - 1)
                request["scheduledOnFromDate"] = s_date.strftime("%Y-%m-%d")
                request["scheduledOnToDate"] = e
                if not date_range_label:
                    date_range_label = "created up to %s" % format_date(e)
        elif start_created_date and end_created_date:
            start_parsed = parse_date_range(start_created_date)
            end_parsed = parse_date_range(end_created_date)
            s = start_parsed[0] if start_parsed else None
            e = end_parsed[1] if end_parsed else None
            if not s or not e:
                return "", None
            s, e = _cap_date_range(s, e)
            request["scheduledOnFromDate"] = s
            request["scheduledOnToDate"] = e
            if not date_range_label:
                date_range_label = "created %s - %s" % (format_date(s), format_date(e))

    # Must have at least one date filter
    if not request:
        return "", None

    return date_range_label, request


MAX_DATE_RANGE_DAYS = 90


def _cap_date_range(start_str: str, end_str: str) -> tuple[str, str]:
    """Cap a date range to MAX_DATE_RANGE_DAYS, keeping the most recent dates."""
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_str, "%Y-%m-%d").date()
    if (end - start).days >= MAX_DATE_RANGE_DAYS:
        start = end - timedelta(days=MAX_DATE_RANGE_DAYS - 1)
        logger.warning("Created-date range capped at %d days (keeping most recent)", MAX_DATE_RANGE_DAYS)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _generate_date_list(start_str: str, end_str: str) -> tuple[list[str], str, str]:
    """Generate a list of individual dates between start and end (inclusive).

    Same format as appointment-ui-client sends to the API.
    Capped at MAX_DATE_RANGE_DAYS to prevent oversized requests.

    Returns:
        Tuple of (date_list, actual_start, actual_end) — actual dates may differ
        from input if range was capped.
    """
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_str, "%Y-%m-%d").date()
    if (end - start).days >= MAX_DATE_RANGE_DAYS:
        # Keep the most recent dates — users care about the latest data
        start = end - timedelta(days=MAX_DATE_RANGE_DAYS - 1)
        logger.warning("Date range capped at %d days (keeping most recent)", MAX_DATE_RANGE_DAYS)
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return dates, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _build_filters(
    advisor_names: list[str] | None,
    creator_advisor_names: list[str] | None,
    status: list[str] | None,
    transport_option_names: list[str] | None,
    team_names: list[str] | None,
    repair_concerns: list[str] | None,
    has_recall: bool | None,
    prediag_status: list[str] | None,
    created_by_platform: str | None,
    cached_data: dict[str, Any],
    uuid_mapper: UUIDMapper,
) -> AppointmentFilters:
    """Resolve names to UUIDs and build the AppointmentFilters object.

    For the Mongo endpoint, AppointmentViewData documents have embedded names
    (assignedDealerAssociateDetail.uuid, teamInfo.uuid, etc.), so we resolve
    user-provided names to UUIDs for matching.
    """
    filters = AppointmentFilters()

    if advisor_names:
        result = validate_advisor_names(advisor_names, cached_data)
        uuids = [uuid for _, uuid in result.get("valid", [])]
        # Always set filter when user specified names — empty list means no matches, returns 0 results
        filters.advisor_uuids = uuids

    if creator_advisor_names:
        result = validate_advisor_names(creator_advisor_names, cached_data)
        uuids = [uuid for _, uuid in result.get("valid", [])]
        filters.creator_advisor_uuids = uuids

    if status:
        filters.statuses = status  # Keep original case — Mongo stores "Scheduled", "Cancelled", etc.

    if transport_option_names:
        result = validate_transport_option_names(transport_option_names, cached_data)
        uuids = [uuid for _, uuid in result.get("valid", [])]
        if any(n.lower() == "none" for n in transport_option_names):
            uuids.append("NONE")
        filters.transport_option_uuids = uuids

    if team_names:
        result = validate_team_names(team_names, cached_data)
        uuids = [uuid for _, uuid in result.get("valid", [])]
        filters.team_uuids = uuids

    if repair_concerns:
        filters.repair_opcodes = repair_concerns

    if has_recall is not None:
        filters.has_recall = has_recall

    if prediag_status:
        filters.prediag_statuses = prediag_status

    if created_by_platform:
        filters.source_uuids = [created_by_platform]

    return filters


async def _fetch_appointments(
    dealer_uuid: str, api_request: dict[str, Any], mkid: str | None = None
) -> list[dict[str, Any]]:
    """Fetch appointments from the Mongo-backed webservice endpoint.

    Uses POST /webservice/dealers/{dealerUuid}/appointments — same as appointment-ui-client.
    Requires mkid cookie for authentication.
    """
    async with KAppointmentAPIClient() as client:
        response = await client.get_appointment_view_data(dealer_uuid, api_request, mkid=mkid)

        appointments = response.get("appointmentViewDataDTOList", [])
        logger.info("Fetched %d appointments from AppointmentViewData", len(appointments))
        return appointments


APPOINTMENT_TOOLS = [get_appointments_tool]
