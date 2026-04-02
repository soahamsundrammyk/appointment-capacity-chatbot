"""Appointment data query tool for fetching and filtering appointment records."""

import asyncio
import logging
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

PAGE_SIZE = 200
MAX_PAGES = 50
MAX_RECORDS = PAGE_SIZE * MAX_PAGES  # 10,000


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

    MODE:
    - "summary" (default): Returns total count and status breakdown.
      Add group_by to break down by: "advisor", "team", "status", "source", "transport_option"
    - "list": Returns paginated appointment records with details.

    DATE FILTERS (at least one date filter is required):
    - start_date/end_date: Filter by appointment scheduled date
    - start_created_date/end_created_date: Filter by when appointment was created
    - Accepts: "today", "yesterday", "this week", "last week", "this month",
      "last month", "last 7 days", "last 30 days", or "YYYY-MM-DD"

    ENTITY FILTERS:
    - advisor_names: Filter by assigned advisor (e.g., ["Diego"])
    - creator_advisor_names: Filter by who created the appointment (e.g., ["Maria"])
    - team_names: Filter by team (e.g., ["Express Shop"])
    - transport_option_names: Filter by transport (e.g., ["Loaner"])
    - status: Filter by status (e.g., ["UPDATED", "CANCELLED"])
    - created_by_platform: Filter by booking source ("Web", "DealerApp", "DMS")
    - repair_concerns: Filter by service/opcode name (e.g., ["Oil Change"])
    - has_recall: True to show only recall appointments, False to exclude them
    - prediag_status: Filter by AI survey status

    EXAMPLES:
    - "How many appts last month?" → mode="summary", start_date="last month"
    - "Diego's appointments this month" → mode="list", start_date="this month", advisor_names=["Diego"]
    - "Break down by advisor" → mode="summary", start_date="this month", group_by="advisor"
    - "Cancelled appointments this week" → mode="summary", start_date="this week", status=["CANCELLED"]
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
    department_uuid = state.department_uuid

    # Parse date ranges
    date_range_label, api_request = _build_api_request(
        start_date, end_date, start_created_date, end_created_date,
        team_names, created_by_platform, cached_data, uuid_mapper,
    )

    if api_request is None:
        return "Please specify a date range (e.g., 'this month', 'last week', 'today')."

    # Resolve entity names to UUIDs for client-side filtering
    filters = _build_filters(
        advisor_names, creator_advisor_names, status, transport_option_names,
        repair_concerns, has_recall, prediag_status, cached_data, uuid_mapper,
    )

    # Fetch all appointment pages
    try:
        all_appointments = await _fetch_all_pages(department_uuid, api_request)
    except Exception as e:
        logger.error("Failed to fetch appointments: %s", e)
        return "Error fetching appointment data. Please try again."

    # Apply client-side filters
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
    team_names: list[str] | None,
    created_by_platform: str | None,
    cached_data: dict[str, Any],
    uuid_mapper: UUIDMapper,
) -> tuple[str, dict[str, Any] | None]:
    """Build the FilterServiceAppointmentRequest for the API."""
    request: dict[str, Any] = {
        "pageNumber": 1,
        "pageSize": PAGE_SIZE,
        "orderBy": "createdTimeStamp",
        "isSortAscending": False,
    }

    date_range_label = ""

    # Parse scheduled date range
    if start_date or end_date:
        if start_date and not end_date:
            parsed = parse_date_range(start_date)
            if parsed:
                request["startDate"] = parsed[0]
                request["endDate"] = parsed[1]
                date_range_label = "%s - %s" % (format_date(parsed[0]), format_date(parsed[1]))
        elif start_date and end_date:
            start_parsed = parse_date_range(start_date)
            end_parsed = parse_date_range(end_date)
            s = start_parsed[0] if start_parsed else start_date
            e = end_parsed[1] if end_parsed else end_date
            request["startDate"] = s
            request["endDate"] = e
            date_range_label = "%s - %s" % (format_date(s), format_date(e))

    # Parse created date range
    if start_created_date or end_created_date:
        if start_created_date and not end_created_date:
            parsed = parse_date_range(start_created_date)
            if parsed:
                request["startCreatedDate"] = parsed[0]
                request["endCreatedDate"] = parsed[1]
                if not date_range_label:
                    date_range_label = "created %s - %s" % (
                        format_date(parsed[0]), format_date(parsed[1])
                    )
        elif start_created_date and end_created_date:
            start_parsed = parse_date_range(start_created_date)
            end_parsed = parse_date_range(end_created_date)
            s = start_parsed[0] if start_parsed else start_created_date
            e = end_parsed[1] if end_parsed else end_created_date
            request["startCreatedDate"] = s
            request["endCreatedDate"] = e
            if not date_range_label:
                date_range_label = "created %s - %s" % (format_date(s), format_date(e))

    # Must have at least one date filter (API requirement)
    if not any(k in request for k in ("startDate", "endDate", "startCreatedDate", "endCreatedDate")):
        return "", None

    # Team filter (server-side)
    if team_names:
        team_result = validate_team_names(team_names, cached_data)
        team_uuids = [uuid for _, uuid in team_result.get("valid", [])]
        if team_uuids:
            request["teamUuids"] = team_uuids

    # Platform source filter (server-side)
    if created_by_platform:
        request["createdBy"] = created_by_platform

    return date_range_label, request


def _build_filters(
    advisor_names: list[str] | None,
    creator_advisor_names: list[str] | None,
    status: list[str] | None,
    transport_option_names: list[str] | None,
    repair_concerns: list[str] | None,
    has_recall: bool | None,
    prediag_status: list[str] | None,
    cached_data: dict[str, Any],
    uuid_mapper: UUIDMapper,
) -> AppointmentFilters:
    """Resolve names to UUIDs and build the AppointmentFilters object."""
    filters = AppointmentFilters()

    if advisor_names:
        result = validate_advisor_names(advisor_names, cached_data)
        uuids = [uuid for _, uuid in result.get("valid", [])]
        if uuids:
            filters.advisor_uuids = uuids

    if creator_advisor_names:
        result = validate_advisor_names(creator_advisor_names, cached_data)
        uuids = [uuid for _, uuid in result.get("valid", [])]
        if uuids:
            filters.creator_advisor_uuids = uuids

    if status:
        filters.statuses = [s.upper() for s in status]

    if transport_option_names:
        result = validate_transport_option_names(transport_option_names, cached_data)
        uuids = [uuid for _, uuid in result.get("valid", [])]
        if any(n.lower() == "none" for n in transport_option_names):
            uuids.append("NONE")
        if uuids:
            filters.transport_option_uuids = uuids

    if repair_concerns:
        filters.repair_opcodes = repair_concerns

    if has_recall is not None:
        filters.has_recall = has_recall

    if prediag_status:
        filters.prediag_statuses = prediag_status

    return filters


async def _fetch_all_pages(
    department_uuid: str, base_request: dict[str, Any]
) -> list[dict[str, Any]]:
    """Fetch all pages of appointment data concurrently."""
    async with KAppointmentAPIClient() as client:
        # Fetch first page
        first_request = {**base_request, "pageNumber": 1, "pageSize": PAGE_SIZE}
        first_response = await client.list_appointments(department_uuid, first_request)

        all_appointments = first_response.get("appointmentInfo", [])
        total_count = first_response.get("totalCount", 0)

        if total_count <= PAGE_SIZE:
            return all_appointments

        # Cap at MAX_RECORDS
        effective_total = min(total_count, MAX_RECORDS)
        total_pages = min((effective_total + PAGE_SIZE - 1) // PAGE_SIZE, MAX_PAGES)

        if total_pages <= 1:
            return all_appointments

        # Fetch remaining pages concurrently
        async def fetch_page(page_num: int) -> list[dict[str, Any]]:
            req = {**base_request, "pageNumber": page_num, "pageSize": PAGE_SIZE}
            resp = await client.list_appointments(department_uuid, req)
            return resp.get("appointmentInfo", [])

        tasks = [fetch_page(p) for p in range(2, total_pages + 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error("Failed to fetch page: %s", result)
                continue
            all_appointments.extend(result)

        logger.info(
            "Fetched %d appointments (%d pages, totalCount=%d)",
            len(all_appointments), total_pages, total_count,
        )

        if total_count > MAX_RECORDS:
            logger.warning(
                "Results capped at %d records (total: %d)", MAX_RECORDS, total_count
            )

        return all_appointments


APPOINTMENT_TOOLS = [get_appointments_tool]
