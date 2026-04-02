# Appointment Data Query Tool — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Add a `get_appointments_tool` to the existing ReAct agent that queries and filters appointment data, supporting all 11 filter types from appointment-ui-client.

**Architecture:** Single new tool added to existing `CAPACITY_TOOLS` list. Calls `POST /v2/department/{uuid}/list` endpoint, fetches all pages concurrently, applies client-side filters in Python, formats as summary or list based on `mode` parameter.

**Tech Stack:** Python 3.11, LangGraph, LangChain, httpx (async), existing UUIDMapper/validation utilities.

**Jira:** MYK-64517

---

### Task 1: Extend date_parser.py with date range parsing

**Files:**
- Modify: `capacity_chatbot/utils/date_parser.py`
- Test: `tests/test_date_parser.py`

The existing `parse_date_query` returns a list of individual dates. We need a new function that returns `(start_date, end_date)` tuples for range-based queries like "last month", "this month", "this week".

**Step 1: Write the failing tests**

Create `tests/test_date_parser.py`:

```python
"""Tests for date range parsing."""

from datetime import date

from capacity_chatbot.utils.date_parser import parse_date_range


def test_parse_this_month():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("this month", reference_date=ref)
    assert start == "2026-03-01"
    assert end == "2026-03-31"


def test_parse_last_month():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("last month", reference_date=ref)
    assert start == "2026-02-01"
    assert end == "2026-02-28"


def test_parse_last_month_leap_year():
    ref = date(2028, 3, 15)
    start, end = parse_date_range("last month", reference_date=ref)
    assert start == "2028-02-01"
    assert end == "2028-02-29"


def test_parse_this_week():
    ref = date(2026, 3, 18)  # Wednesday
    start, end = parse_date_range("this week", reference_date=ref)
    assert start == "2026-03-16"  # Monday
    assert end == "2026-03-22"  # Sunday


def test_parse_last_week():
    ref = date(2026, 3, 18)  # Wednesday
    start, end = parse_date_range("last week", reference_date=ref)
    assert start == "2026-03-09"  # Previous Monday
    assert end == "2026-03-15"  # Previous Sunday


def test_parse_today():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("today", reference_date=ref)
    assert start == "2026-03-15"
    assert end == "2026-03-15"


def test_parse_yesterday():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("yesterday", reference_date=ref)
    assert start == "2026-03-14"
    assert end == "2026-03-14"


def test_parse_explicit_date():
    start, end = parse_date_range("2026-03-15")
    assert start == "2026-03-15"
    assert end == "2026-03-15"


def test_parse_last_n_days():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("last 7 days", reference_date=ref)
    assert start == "2026-03-08"
    assert end == "2026-03-15"


def test_parse_last_30_days():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("last 30 days", reference_date=ref)
    assert start == "2026-02-13"
    assert end == "2026-03-15"


def test_parse_none_returns_none():
    result = parse_date_range(None)
    assert result is None


def test_parse_empty_returns_none():
    result = parse_date_range("")
    assert result is None


def test_parse_unrecognized_returns_none():
    result = parse_date_range("gobbledygook")
    assert result is None
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/soahamsundram/Documents/GitHub/appointment-capacity-chatbot && python -m pytest tests/test_date_parser.py -v`
Expected: FAIL — `ImportError: cannot import name 'parse_date_range'`

**Step 3: Implement parse_date_range**

Add to `capacity_chatbot/utils/date_parser.py` (after the existing `parse_dates` function):

```python
import calendar


def parse_date_range(
    query: str | None, reference_date: date | None = None
) -> tuple[str, str] | None:
    """Parse natural language date expressions to a (start_date, end_date) tuple.

    Returns dates in YYYY-MM-DD format. For single-day queries like "today",
    start and end are the same date.

    Args:
        query: Natural language date expression (e.g., "last month", "this week")
        reference_date: Reference date for relative expressions (defaults to today)

    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format, or None if unparseable
    """
    if not query:
        return None

    if reference_date is None:
        reference_date = date.today()

    query_lower = query.lower().strip()

    # Explicit YYYY-MM-DD
    if DATE_PATTERN.match(query):
        return (query, query)

    # Single-day expressions
    if query_lower == "today":
        d = reference_date.strftime("%Y-%m-%d")
        return (d, d)

    if query_lower == "yesterday":
        d = (reference_date - timedelta(days=1)).strftime("%Y-%m-%d")
        return (d, d)

    if query_lower == "tomorrow":
        d = (reference_date + timedelta(days=1)).strftime("%Y-%m-%d")
        return (d, d)

    # This month
    if query_lower == "this month":
        first = reference_date.replace(day=1)
        last_day = calendar.monthrange(reference_date.year, reference_date.month)[1]
        last = reference_date.replace(day=last_day)
        return (first.strftime("%Y-%m-%d"), last.strftime("%Y-%m-%d"))

    # Last month
    if query_lower == "last month":
        first_of_current = reference_date.replace(day=1)
        last_of_prev = first_of_current - timedelta(days=1)
        first_of_prev = last_of_prev.replace(day=1)
        return (first_of_prev.strftime("%Y-%m-%d"), last_of_prev.strftime("%Y-%m-%d"))

    # This week (Monday-Sunday)
    if query_lower == "this week":
        monday = reference_date - timedelta(days=reference_date.weekday())
        sunday = monday + timedelta(days=6)
        return (monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d"))

    # Last week
    if query_lower == "last week":
        this_monday = reference_date - timedelta(days=reference_date.weekday())
        prev_monday = this_monday - timedelta(days=7)
        prev_sunday = prev_monday + timedelta(days=6)
        return (prev_monday.strftime("%Y-%m-%d"), prev_sunday.strftime("%Y-%m-%d"))

    # "last N days"
    last_n_match = re.match(r"last\s+(\d+)\s+days?", query_lower)
    if last_n_match:
        n = int(last_n_match.group(1))
        start = reference_date - timedelta(days=n)
        return (start.strftime("%Y-%m-%d"), reference_date.strftime("%Y-%m-%d"))

    # "next N days"
    next_n_match = re.match(r"next\s+(\d+)\s+days?", query_lower)
    if next_n_match:
        n = int(next_n_match.group(1))
        end = reference_date + timedelta(days=n)
        return (reference_date.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))

    return None
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/soahamsundram/Documents/GitHub/appointment-capacity-chatbot && python -m pytest tests/test_date_parser.py -v`
Expected: All 13 tests PASS

**Step 5: Commit**

```bash
git add tests/test_date_parser.py capacity_chatbot/utils/date_parser.py
git commit -m "feat(MYK-64517): add parse_date_range for date range queries"
```

---

### Task 2: Add list_appointments method to API client

**Files:**
- Modify: `capacity_chatbot/clients/kappointment_client.py`
- Test: `tests/test_kappointment_client.py`

**Step 1: Write the failing test**

Create `tests/test_kappointment_client.py`:

```python
"""Tests for KAppointmentAPIClient.list_appointments."""

import pytest
import httpx
from unittest.mock import AsyncMock, patch

from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient


@pytest.mark.asyncio
async def test_list_appointments_builds_correct_url():
    client = KAppointmentAPIClient()
    mock_response = httpx.Response(
        200,
        json={"appointmentInfo": [], "totalCount": 0},
        request=httpx.Request("POST", "http://test"),
    )
    with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await client.list_appointments(
            "dept-uuid-123",
            {
                "pageNumber": 1,
                "pageSize": 200,
                "startCreatedDate": "2026-03-01",
                "endCreatedDate": "2026-03-31",
            },
        )
    assert result["totalCount"] == 0
    assert result["appointmentInfo"] == []
    await client.close()


@pytest.mark.asyncio
async def test_list_appointments_returns_appointment_data():
    client = KAppointmentAPIClient()
    mock_data = {
        "appointmentInfo": [
            {
                "uuid": "appt-1",
                "assignedAdvisorUuid": "adv-1",
                "status": "UPDATED",
                "startTime": "2026-03-15 09:00:00",
            }
        ],
        "totalCount": 1,
    }
    mock_response = httpx.Response(
        200,
        json=mock_data,
        request=httpx.Request("POST", "http://test"),
    )
    with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await client.list_appointments("dept-uuid-123", {"pageNumber": 1, "pageSize": 200})
    assert result["totalCount"] == 1
    assert result["appointmentInfo"][0]["uuid"] == "appt-1"
    await client.close()
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/soahamsundram/Documents/GitHub/appointment-capacity-chatbot && python -m pytest tests/test_kappointment_client.py -v`
Expected: FAIL — `AttributeError: 'KAppointmentAPIClient' has no attribute 'list_appointments'`

**Step 3: Add list_appointments to client**

Add to `capacity_chatbot/clients/kappointment_client.py` (before `close` method):

```python
    async def list_appointments(
        self, department_uuid: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        """Call POST /department/{uuid}/list to filter and list appointments.

        Args:
            department_uuid: Department UUID
            request: FilterServiceAppointmentRequest with:
                - pageNumber (int, required): 1-based page number
                - pageSize (int, required): results per page
                - startDate/endDate: scheduled date range (yyyy-MM-dd)
                - startCreatedDate/endCreatedDate: creation date range (yyyy-MM-dd)
                - createdBy: platform source (Web, DealerApp, DMS, etc.)
                - teamUuids: list of team UUIDs
                - orderBy: sort field (e.g. "createdTimeStamp")
                - isSortAscending: sort direction

        Returns:
            FilterServiceAppointmentResponse with:
                - appointmentInfo: list of AppointmentInfoLite
                - totalCount: total matching records
        """
        url = self._build_url(f"department/{department_uuid}/list")
        return await self._make_post_request(url, request, "list_appointments")
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/soahamsundram/Documents/GitHub/appointment-capacity-chatbot && python -m pytest tests/test_kappointment_client.py -v`
Expected: All 2 tests PASS

**Step 5: Commit**

```bash
git add capacity_chatbot/clients/kappointment_client.py tests/test_kappointment_client.py
git commit -m "feat(MYK-64517): add list_appointments method to API client"
```

---

### Task 3: Create the appointment filter pipeline

**Files:**
- Create: `capacity_chatbot/utils/appointment_filters.py`
- Test: `tests/test_appointment_filters.py`

This is the core Python post-processing logic that mirrors appointment-ui-client's `applyFilterToAppointment`.

**Step 1: Write the failing tests**

Create `tests/test_appointment_filters.py`:

```python
"""Tests for appointment filter pipeline."""

import pytest

from capacity_chatbot.utils.appointment_filters import apply_filters, AppointmentFilters


# Sample appointment data matching AppointmentInfoLite structure
SAMPLE_APPOINTMENTS = [
    {
        "uuid": "appt-1",
        "assignedAdvisorUuid": "adv-diego",
        "creatorAdvisorUuid": "adv-maria",
        "status": "UPDATED",
        "isCancelled": False,
        "transportOption": {"transportOptionUuid": "tp-loaner", "optionName": "Loaner"},
        "serviceList": [{"laborOpcode": "OIL_CHANGE", "recallId": None}],
        "teamUuid": "team-express",
        "startTime": "2026-03-15 09:00:00",
        "createdTimeStamp": "2026-03-10 08:00:00",
        "preferredDate": "2026-03-15",
        "appointmentSourceDetails": {"uuid": "src-web"},
    },
    {
        "uuid": "appt-2",
        "assignedAdvisorUuid": "adv-maria",
        "creatorAdvisorUuid": "adv-diego",
        "status": "CANCELLED",
        "isCancelled": True,
        "transportOption": {"transportOptionUuid": "tp-waiter", "optionName": "Waiter"},
        "serviceList": [{"laborOpcode": "BRAKE_INSPECT", "recallId": "RCL-123"}],
        "teamUuid": "team-main",
        "startTime": "2026-03-16 10:30:00",
        "createdTimeStamp": "2026-03-11 09:00:00",
        "preferredDate": "2026-03-16",
        "appointmentSourceDetails": {"uuid": "src-dealer-app"},
    },
    {
        "uuid": "appt-3",
        "assignedAdvisorUuid": "adv-diego",
        "creatorAdvisorUuid": "adv-diego",
        "status": "UPDATED",
        "isCancelled": False,
        "transportOption": None,
        "serviceList": [
            {"laborOpcode": "OIL_CHANGE", "recallId": None},
            {"laborOpcode": "TIRE_ROTATION", "recallId": "RCL-456"},
        ],
        "teamUuid": "team-express",
        "startTime": "2026-03-17 14:00:00",
        "createdTimeStamp": "2026-03-12 10:00:00",
        "preferredDate": "2026-03-17",
        "appointmentSourceDetails": None,
    },
]


def test_filter_by_assigned_advisor_uuids():
    filters = AppointmentFilters(advisor_uuids=["adv-diego"])
    result = apply_filters(SAMPLE_APPOINTMENTS, filters)
    assert len(result) == 2
    assert all(a["assignedAdvisorUuid"] == "adv-diego" for a in result)


def test_filter_by_creator_advisor_uuids():
    filters = AppointmentFilters(creator_advisor_uuids=["adv-diego"])
    result = apply_filters(SAMPLE_APPOINTMENTS, filters)
    assert len(result) == 2
    assert result[0]["uuid"] == "appt-2"
    assert result[1]["uuid"] == "appt-3"


def test_filter_by_status():
    filters = AppointmentFilters(statuses=["CANCELLED"])
    result = apply_filters(SAMPLE_APPOINTMENTS, filters)
    assert len(result) == 1
    assert result[0]["uuid"] == "appt-2"


def test_filter_by_transport_option_uuids():
    filters = AppointmentFilters(transport_option_uuids=["tp-loaner"])
    result = apply_filters(SAMPLE_APPOINTMENTS, filters)
    assert len(result) == 1
    assert result[0]["uuid"] == "appt-1"


def test_filter_by_transport_option_none():
    """Appointments with no transport option should match 'NONE' filter."""
    filters = AppointmentFilters(transport_option_uuids=["NONE"])
    result = apply_filters(SAMPLE_APPOINTMENTS, filters)
    assert len(result) == 1
    assert result[0]["uuid"] == "appt-3"


def test_filter_by_team_uuids():
    filters = AppointmentFilters(team_uuids=["team-express"])
    result = apply_filters(SAMPLE_APPOINTMENTS, filters)
    assert len(result) == 2


def test_filter_by_repair_concern():
    filters = AppointmentFilters(repair_opcodes=["OIL_CHANGE"])
    result = apply_filters(SAMPLE_APPOINTMENTS, filters)
    assert len(result) == 2
    assert result[0]["uuid"] == "appt-1"
    assert result[1]["uuid"] == "appt-3"


def test_filter_by_has_recall_true():
    filters = AppointmentFilters(has_recall=True)
    result = apply_filters(SAMPLE_APPOINTMENTS, filters)
    assert len(result) == 2
    assert result[0]["uuid"] == "appt-2"
    assert result[1]["uuid"] == "appt-3"


def test_filter_by_has_recall_false():
    filters = AppointmentFilters(has_recall=False)
    result = apply_filters(SAMPLE_APPOINTMENTS, filters)
    assert len(result) == 1
    assert result[0]["uuid"] == "appt-1"


def test_filter_combined():
    """Multiple filters applied together (AND logic)."""
    filters = AppointmentFilters(
        advisor_uuids=["adv-diego"],
        statuses=["UPDATED"],
    )
    result = apply_filters(SAMPLE_APPOINTMENTS, filters)
    assert len(result) == 2
    assert all(a["assignedAdvisorUuid"] == "adv-diego" for a in result)
    assert all(a["status"] == "UPDATED" for a in result)


def test_no_filters_returns_all():
    filters = AppointmentFilters()
    result = apply_filters(SAMPLE_APPOINTMENTS, filters)
    assert len(result) == 3


def test_filter_by_source_uuids():
    filters = AppointmentFilters(source_uuids=["src-web"])
    result = apply_filters(SAMPLE_APPOINTMENTS, filters)
    assert len(result) == 1
    assert result[0]["uuid"] == "appt-1"
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/soahamsundram/Documents/GitHub/appointment-capacity-chatbot && python -m pytest tests/test_appointment_filters.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'capacity_chatbot.utils.appointment_filters'`

**Step 3: Implement the filter pipeline**

Create `capacity_chatbot/utils/appointment_filters.py`:

```python
"""Client-side appointment filter pipeline.

Mirrors the filter logic from appointment-ui-client's applyFilterToAppointment method.
All filters use AND logic — an appointment must match ALL specified filters.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppointmentFilters:
    """Filter criteria for post-processing appointments.

    All fields are optional. Only non-None filters are applied.
    UUIDs should be pre-resolved from names before constructing this object.
    """

    advisor_uuids: list[str] | None = None
    creator_advisor_uuids: list[str] | None = None
    statuses: list[str] | None = None
    transport_option_uuids: list[str] | None = None
    team_uuids: list[str] | None = None
    repair_opcodes: list[str] | None = None
    has_recall: bool | None = None
    prediag_statuses: list[str] | None = None
    source_uuids: list[str] | None = None


def _matches_advisor(appt: dict[str, Any], uuids: list[str]) -> bool:
    return appt.get("assignedAdvisorUuid") in uuids


def _matches_creator(appt: dict[str, Any], uuids: list[str]) -> bool:
    return appt.get("creatorAdvisorUuid") in uuids


def _matches_status(appt: dict[str, Any], statuses: list[str]) -> bool:
    return appt.get("status") in statuses


def _matches_transport(appt: dict[str, Any], uuids: list[str]) -> bool:
    transport = appt.get("transportOption")
    if transport is None:
        return "NONE" in uuids
    transport_uuid = transport.get("transportOptionUuid")
    return transport_uuid in uuids


def _matches_team(appt: dict[str, Any], uuids: list[str]) -> bool:
    return appt.get("teamUuid") in uuids


def _matches_repair_opcode(appt: dict[str, Any], opcodes: list[str]) -> bool:
    services = appt.get("serviceList") or []
    opcodes_lower = [o.lower() for o in opcodes]
    for service in services:
        labor_opcode = (service.get("laborOpcode") or "").lower()
        if labor_opcode in opcodes_lower:
            return True
    return False


def _matches_recall(appt: dict[str, Any], has_recall: bool) -> bool:
    services = appt.get("serviceList") or []
    appt_has_recall = any(s.get("recallId") for s in services)
    return appt_has_recall == has_recall


def _matches_prediag(appt: dict[str, Any], statuses: list[str]) -> bool:
    prediag = appt.get("prediagStatus")
    if "HAS_MEDIA" in statuses and appt.get("hasPrediagMedia"):
        return True
    return prediag in statuses


def _matches_source(appt: dict[str, Any], uuids: list[str]) -> bool:
    source_details = appt.get("appointmentSourceDetails")
    if not source_details:
        return False
    source_uuid = source_details.get("uuid", "")
    # Handle comma-separated UUIDs (appointment-ui-client pattern)
    for uid in uuids:
        if uid in source_uuid or source_uuid in uid:
            return True
    return False


def apply_filters(
    appointments: list[dict[str, Any]], filters: AppointmentFilters
) -> list[dict[str, Any]]:
    """Apply all specified filters to a list of appointments.

    Filters use AND logic — an appointment must match ALL non-None filters.

    Args:
        appointments: List of AppointmentInfoLite dicts from API
        filters: Filter criteria (only non-None fields are applied)

    Returns:
        Filtered list of appointments
    """
    result = appointments

    if filters.advisor_uuids is not None:
        result = [a for a in result if _matches_advisor(a, filters.advisor_uuids)]

    if filters.creator_advisor_uuids is not None:
        result = [a for a in result if _matches_creator(a, filters.creator_advisor_uuids)]

    if filters.statuses is not None:
        result = [a for a in result if _matches_status(a, filters.statuses)]

    if filters.transport_option_uuids is not None:
        result = [a for a in result if _matches_transport(a, filters.transport_option_uuids)]

    if filters.team_uuids is not None:
        result = [a for a in result if _matches_team(a, filters.team_uuids)]

    if filters.repair_opcodes is not None:
        result = [a for a in result if _matches_repair_opcode(a, filters.repair_opcodes)]

    if filters.has_recall is not None:
        result = [a for a in result if _matches_recall(a, filters.has_recall)]

    if filters.prediag_statuses is not None:
        result = [a for a in result if _matches_prediag(a, filters.prediag_statuses)]

    if filters.source_uuids is not None:
        result = [a for a in result if _matches_source(a, filters.source_uuids)]

    return result
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/soahamsundram/Documents/GitHub/appointment-capacity-chatbot && python -m pytest tests/test_appointment_filters.py -v`
Expected: All 13 tests PASS

**Step 5: Commit**

```bash
git add capacity_chatbot/utils/appointment_filters.py tests/test_appointment_filters.py
git commit -m "feat(MYK-64517): add appointment filter pipeline with all 11 filter types"
```

---

### Task 4: Create the appointment formatting utilities

**Files:**
- Create: `capacity_chatbot/utils/appointment_formatter.py`
- Test: `tests/test_appointment_formatter.py`

**Step 1: Write the failing tests**

Create `tests/test_appointment_formatter.py`:

```python
"""Tests for appointment formatting utilities."""

from capacity_chatbot.utils.appointment_formatter import (
    format_summary,
    format_list,
    format_grouped_summary,
)
from capacity_chatbot.utils.uuid_mapper import UUIDMapper


SAMPLE_CACHED_DATA = {
    "advisors": [
        {"uuid": "adv-diego", "firstName": "Diego", "lastName": "Martinez"},
        {"uuid": "adv-maria", "firstName": "Maria", "lastName": "Lopez"},
    ],
    "teams": [
        {"uuid": "team-express", "name": "Express Shop"},
        {"uuid": "team-main", "name": "Main Shop"},
    ],
    "transport_options": [
        {"transportOptionUuid": "tp-loaner", "optionName": "Loaner"},
        {"transportOptionUuid": "tp-waiter", "optionName": "Waiter"},
    ],
}

SAMPLE_APPOINTMENTS = [
    {
        "uuid": "appt-1",
        "assignedAdvisorUuid": "adv-diego",
        "status": "UPDATED",
        "startTime": "2026-03-15 09:00:00",
        "preferredDate": "2026-03-15",
        "transportOption": {"transportOptionUuid": "tp-loaner", "optionName": "Loaner"},
        "serviceList": [{"concernText": "Oil Change", "laborOpcode": "OIL"}],
        "teamUuid": "team-express",
        "isCancelled": False,
    },
    {
        "uuid": "appt-2",
        "assignedAdvisorUuid": "adv-maria",
        "status": "CANCELLED",
        "startTime": "2026-03-16 10:30:00",
        "preferredDate": "2026-03-16",
        "transportOption": {"transportOptionUuid": "tp-waiter", "optionName": "Waiter"},
        "serviceList": [{"concernText": "Brake Inspection", "laborOpcode": "BRK"}],
        "teamUuid": "team-main",
        "isCancelled": True,
    },
    {
        "uuid": "appt-3",
        "assignedAdvisorUuid": "adv-diego",
        "status": "UPDATED",
        "startTime": "2026-03-17 14:00:00",
        "preferredDate": "2026-03-17",
        "transportOption": None,
        "serviceList": [],
        "teamUuid": "team-express",
        "isCancelled": False,
    },
]


def test_format_summary_basic():
    mapper = UUIDMapper(SAMPLE_CACHED_DATA)
    result = format_summary(SAMPLE_APPOINTMENTS, "Mar 1 - Mar 31, 2026", mapper)
    assert "3 total" in result
    assert "UPDATED" in result or "Completed" in result.lower() or "2" in result
    assert "CANCELLED" in result or "Cancelled" in result or "1" in result


def test_format_summary_empty():
    mapper = UUIDMapper(SAMPLE_CACHED_DATA)
    result = format_summary([], "Mar 2026", mapper)
    assert "0" in result


def test_format_list_basic():
    mapper = UUIDMapper(SAMPLE_CACHED_DATA)
    result = format_list(SAMPLE_APPOINTMENTS, mapper, page=1, page_size=50)
    assert "Diego Martinez" in result
    assert "Maria Lopez" in result
    assert "Oil Change" in result


def test_format_list_pagination():
    mapper = UUIDMapper(SAMPLE_CACHED_DATA)
    result = format_list(SAMPLE_APPOINTMENTS, mapper, page=1, page_size=2)
    assert "Page 1 of 2" in result


def test_format_grouped_summary_by_advisor():
    mapper = UUIDMapper(SAMPLE_CACHED_DATA)
    result = format_grouped_summary(SAMPLE_APPOINTMENTS, "advisor", "Mar 2026", mapper)
    assert "Diego Martinez" in result
    assert "Maria Lopez" in result


def test_format_grouped_summary_by_status():
    mapper = UUIDMapper(SAMPLE_CACHED_DATA)
    result = format_grouped_summary(SAMPLE_APPOINTMENTS, "status", "Mar 2026", mapper)
    assert "UPDATED" in result
    assert "CANCELLED" in result


def test_format_grouped_summary_by_team():
    mapper = UUIDMapper(SAMPLE_CACHED_DATA)
    result = format_grouped_summary(SAMPLE_APPOINTMENTS, "team", "Mar 2026", mapper)
    assert "Express Shop" in result
    assert "Main Shop" in result
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/soahamsundram/Documents/GitHub/appointment-capacity-chatbot && python -m pytest tests/test_appointment_formatter.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement the formatter**

Create `capacity_chatbot/utils/appointment_formatter.py`:

```python
"""Formatting utilities for appointment data output.

Handles both summary mode (counts, breakdowns) and list mode (paginated records).
"""

import math
from collections import Counter
from typing import Any

from capacity_chatbot.utils.uuid_mapper import UUIDMapper

MAX_BREAKDOWN_ITEMS = 10
MAX_LIST_PAGE_SIZE = 50


def format_summary(
    appointments: list[dict[str, Any]],
    date_range_label: str,
    uuid_mapper: UUIDMapper,
) -> str:
    """Format appointment data as a summary with counts.

    Args:
        appointments: Filtered list of AppointmentInfoLite dicts
        date_range_label: Human-readable date range (e.g., "Mar 1 - Mar 31, 2026")
        uuid_mapper: UUIDMapper for resolving UUIDs to names

    Returns:
        Formatted summary string
    """
    total = len(appointments)

    if total == 0:
        return "Appointments (%s): 0 total — no appointments found matching your filters." % date_range_label

    # Status breakdown
    status_counts = Counter(a.get("status", "Unknown") for a in appointments)
    cancelled_count = sum(1 for a in appointments if a.get("isCancelled"))
    status_parts = ["%d %s" % (count, status) for status, count in status_counts.most_common()]

    lines = [
        "Appointments (%s): %d total" % (date_range_label, total),
        "",
        "By Status: %s" % ", ".join(status_parts),
    ]

    if cancelled_count > 0:
        lines.append("Cancelled: %d" % cancelled_count)

    return "\n".join(lines)


def format_list(
    appointments: list[dict[str, Any]],
    uuid_mapper: UUIDMapper,
    page: int = 1,
    page_size: int = 50,
) -> str:
    """Format appointments as a paginated list.

    Args:
        appointments: Filtered list of AppointmentInfoLite dicts
        uuid_mapper: UUIDMapper for resolving UUIDs to names
        page: 1-based page number
        page_size: Records per page (capped at MAX_LIST_PAGE_SIZE)

    Returns:
        Formatted paginated list string
    """
    total = len(appointments)
    if total == 0:
        return "No appointments found matching your filters."

    page_size = min(page_size, MAX_LIST_PAGE_SIZE)
    total_pages = math.ceil(total / page_size)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total)
    page_items = appointments[start_idx:end_idx]

    lines = ["Appointments (Page %d of %d, showing %d of %d):" % (page, total_pages, len(page_items), total), ""]

    for i, appt in enumerate(page_items, start=start_idx + 1):
        lines.append(_format_appointment_line(appt, i, uuid_mapper))

    if total_pages > 1:
        lines.append("")
        lines.append("Page %d of %d. Ask for next page or refine filters." % (page, total_pages))

    return "\n".join(lines)


def _format_appointment_line(appt: dict[str, Any], index: int, uuid_mapper: UUIDMapper) -> str:
    """Format a single appointment as a one-line summary."""
    # Date and time
    start_time = appt.get("startTime", "")
    date_str = start_time[:10] if start_time else appt.get("preferredDate", "N/A")
    time_str = start_time[11:16] if len(start_time) > 16 else ""

    # Advisor
    advisor_uuid = appt.get("assignedAdvisorUuid", "")
    advisor_name = uuid_mapper.get_advisor_name(advisor_uuid) if advisor_uuid else "Unassigned"

    # Services
    services = appt.get("serviceList") or []
    service_names = [s.get("concernText", s.get("laborOpcode", "")) for s in services if s]
    service_str = ", ".join(service_names[:3]) if service_names else "No services"

    # Transport
    transport = appt.get("transportOption")
    transport_name = transport.get("optionName", "N/A") if transport else "None"

    # Status
    status = appt.get("status", "Unknown")
    if appt.get("isCancelled"):
        status = "Cancelled"

    return "%d. %s %s - %s | %s | %s | %s" % (
        index, date_str, time_str, advisor_name, service_str, transport_name, status,
    )


def format_grouped_summary(
    appointments: list[dict[str, Any]],
    group_by: str,
    date_range_label: str,
    uuid_mapper: UUIDMapper,
) -> str:
    """Format appointment data grouped by a specific dimension.

    Args:
        appointments: Filtered list of AppointmentInfoLite dicts
        group_by: Grouping dimension ("advisor", "team", "status", "source", "transport_option")
        date_range_label: Human-readable date range
        uuid_mapper: UUIDMapper for resolving UUIDs to names

    Returns:
        Formatted grouped summary with markdown table
    """
    total = len(appointments)
    if total == 0:
        return "Appointments by %s (%s): 0 total — no appointments found." % (
            group_by.replace("_", " ").title(), date_range_label
        )

    # Group appointments
    groups: dict[str, list[dict[str, Any]]] = {}
    for appt in appointments:
        key = _get_group_key(appt, group_by, uuid_mapper)
        groups.setdefault(key, []).append(appt)

    # Sort by count descending
    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)

    # Build table
    label = group_by.replace("_", " ").title()
    lines = [
        "Appointments by %s (%s): %d total" % (label, date_range_label, total),
        "",
        "| %s | Total | Cancelled |" % label,
        "|%s|-------|-----------|" % ("-" * (len(label) + 2)),
    ]

    shown = 0
    for name, group_appts in sorted_groups:
        if shown >= MAX_BREAKDOWN_ITEMS:
            remaining = len(sorted_groups) - shown
            lines.append("| ... and %d more | | |" % remaining)
            break
        cancelled = sum(1 for a in group_appts if a.get("isCancelled"))
        lines.append("| %s | %d | %d |" % (name, len(group_appts), cancelled))
        shown += 1

    return "\n".join(lines)


def _get_group_key(appt: dict[str, Any], group_by: str, uuid_mapper: UUIDMapper) -> str:
    """Extract the grouping key from an appointment."""
    if group_by == "advisor":
        uuid = appt.get("assignedAdvisorUuid", "")
        return uuid_mapper.get_advisor_name(uuid) if uuid else "Unassigned"

    if group_by == "team":
        uuid = appt.get("teamUuid", "")
        return uuid_mapper.get_team_name(uuid) if uuid else "No Team"

    if group_by == "status":
        if appt.get("isCancelled"):
            return "CANCELLED"
        return appt.get("status", "Unknown")

    if group_by == "source":
        source = appt.get("appointmentSourceDetails")
        if source:
            return source.get("name", source.get("uuid", "Unknown"))
        return "Unknown"

    if group_by == "transport_option":
        transport = appt.get("transportOption")
        if transport:
            return transport.get("optionName", transport.get("customName", "Unknown"))
        return "None"

    return "Unknown"
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/soahamsundram/Documents/GitHub/appointment-capacity-chatbot && python -m pytest tests/test_appointment_formatter.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add capacity_chatbot/utils/appointment_formatter.py tests/test_appointment_formatter.py
git commit -m "feat(MYK-64517): add appointment summary and list formatters"
```

---

### Task 5: Create the get_appointments_tool

**Files:**
- Create: `capacity_chatbot/tools/appointments.py`
- Modify: `capacity_chatbot/tools/__init__.py`

This is the main tool that wires everything together: date parsing, API calls, concurrent page fetching, filtering, and formatting.

**Step 1: Create the tool**

Create `capacity_chatbot/tools/appointments.py`:

```python
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
    - "How many appts last month?" → mode="summary", start_created_date="last month"
    - "Diego's appointments this month" → mode="list", start_created_date="this month", advisor_names=["Diego"]
    - "Break down by advisor" → mode="summary", start_created_date="this month", group_by="advisor"
    - "Cancelled appointments this week" → mode="summary", start_date="this week", status=["CANCELLED"]

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
    """Build the FilterServiceAppointmentRequest for the API.

    Returns:
        Tuple of (date_range_label, api_request_dict) or (label, None) if no date range.
    """
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
        # Handle "None" transport option
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
    """Fetch all pages of appointment data concurrently.

    First page is fetched to get totalCount, then remaining pages
    are fetched in parallel using asyncio.gather.

    Args:
        department_uuid: Department UUID
        base_request: Base API request dict (pageNumber/pageSize will be set)

    Returns:
        Combined list of all AppointmentInfoLite dicts
    """
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
```

**Step 2: Register the tool in __init__.py**

Modify `capacity_chatbot/tools/__init__.py` — add imports and update CAPACITY_TOOLS:

```python
"""Tool exports for capacity chatbot."""

from capacity_chatbot.enums import (
    ApplicabilityRuleField,
    CapacityType,
    RuleField,
    RuleMatchingCriteria,
)
from capacity_chatbot.tools.appointments import APPOINTMENT_TOOLS
from capacity_chatbot.tools.capacity import get_capacity_tool
from capacity_chatbot.tools.entities import ENTITY_TOOLS
from capacity_chatbot.tools.first_available_slot import get_first_available_slot_tool
from capacity_chatbot.tools.knowledge import KNOWLEDGE_TOOLS
from capacity_chatbot.tools.opcode import search_opcode_tool
from capacity_chatbot.tools.rules import get_rules_tool

CAPACITY_TOOLS = [
    *KNOWLEDGE_TOOLS,
    *ENTITY_TOOLS,
    *APPOINTMENT_TOOLS,
    get_rules_tool,
    get_capacity_tool,
    get_first_available_slot_tool,
    search_opcode_tool,
]

__all__ = [
    "CapacityType",
    "ApplicabilityRuleField",
    "RuleMatchingCriteria",
    "RuleField",
    "KNOWLEDGE_TOOLS",
    "ENTITY_TOOLS",
    "APPOINTMENT_TOOLS",
    "CAPACITY_TOOLS",
    "get_rules_tool",
    "get_capacity_tool",
    "get_first_available_slot_tool",
    "search_opcode_tool",
]
```

**Step 3: Commit**

```bash
git add capacity_chatbot/tools/appointments.py capacity_chatbot/tools/__init__.py
git commit -m "feat(MYK-64517): add get_appointments_tool with concurrent page fetching"
```

---

### Task 6: Update system prompt

**Files:**
- Modify: `capacity_chatbot/prompts.py`

**Step 1: Add appointment data query section to the system prompt**

In `capacity_chatbot/prompts.py`, add the following section before the `LIMITATIONS` block (insert after the `RESPONSE GUIDELINES` section):

```python
═══════════════════════════════════════════════════════════════════════════════
APPOINTMENT DATA QUERIES
═══════════════════════════════════════════════════════════════════════════════

When user asks about appointment data, history, counts, or statistics:
• Use get_appointments_tool with mode="summary" for counts and breakdowns
• Use get_appointments_tool with mode="list" to show actual appointment records
• Use group_by to break down by: "advisor", "team", "status", "source", "transport_option"
• For "created by [person]" → use creator_advisor_names (who created the appointment)
• For "[person]'s appointments" → use advisor_names (who the appointment is assigned to)
• Always clarify date range if user is ambiguous
• Default to "this month" if no date specified and query is about historical data
• At least one date filter is REQUIRED — if user doesn't specify, ask or default to this month
• For follow-up breakdowns, reuse the same date filters from the previous query
"""
```

The full updated prompt function should look like:

```python
def get_capacity_agent_system_prompt(current_time: str | None = None) -> str:
    """System prompt for ReAct capacity agent."""
    return f"""You are a capacity chatbot assistant for an automotive service department.

Current time: {current_time or datetime.now().strftime("%A, %B %d, %Y %I:%M %p")}

═══════════════════════════════════════════════════════════════════════════════
⚠️ CRITICAL: VERIFY DATA BEFORE RESPONDING - NEVER TRUST USER ASSUMPTIONS
═══════════════════════════════════════════════════════════════════════════════

If user says "I can't do X" or "X isn't working" or "Why is X happening?":
1. FIRST call the relevant tool to get ACTUAL data
2. CHECK if the user's claim is actually true in the data
3. If data CONTRADICTS user's assumption → say "Actually, the data shows [ACTUAL DATA]"
4. NEVER agree with or explain a problem that may not exist

Example:
  User: "Why can't I book oil change on Thursday?"
  ✗ WRONG: "You can't book because..." (assumed their claim is true without checking)
  ✓ RIGHT: Call get_capacity, check actual data, THEN respond based on facts

═══════════════════════════════════════════════════════════════════════════════
HOW-TO QUESTIONS
═══════════════════════════════════════════════════════════════════════════════

When user asks how to increase capacity, change limits, modify settings:
1. Call get_knowledge_answer with the specific limiting factors type from capacity data
2. Provide EXACT step-by-step instructions from the knowledge base
3. NEVER generate vague advice like "optimize scheduling" or "adjust limits"

═══════════════════════════════════════════════════════════════════════════════
APPOINTMENT DATA QUERIES
═══════════════════════════════════════════════════════════════════════════════

When user asks about appointment data, history, counts, or statistics:
• Use get_appointments_tool with mode="summary" for counts and breakdowns
• Use get_appointments_tool with mode="list" to show actual appointment records
• Use group_by to break down by: "advisor", "team", "status", "source", "transport_option"
• For "created by [person]" → use creator_advisor_names (who created the appointment)
• For "[person]'s appointments" → use advisor_names (who the appointment is assigned to)
• Always clarify date range if user is ambiguous
• Default to "this month" if no date specified and query is about historical data
• At least one date filter is REQUIRED — if user doesn't specify, ask or default to this month
• For follow-up breakdowns, reuse the same date filters from the previous query

═══════════════════════════════════════════════════════════════════════════════
RESPONSE GUIDELINES
═══════════════════════════════════════════════════════════════════════════════

• Always use human-readable names, NEVER show UUIDs to users
• Combine multiple filters in ONE get_capacity call when possible
• After showing capacity data, ask: "Would you like me to explain how to increase this?"
• Do NOT provide how-to steps unless user explicitly asks

═══════════════════════════════════════════════════════════════════════════════
LIMITATIONS
═══════════════════════════════════════════════════════════════════════════════

You are a READ-ONLY assistant:
• CANNOT book appointments
• CANNOT modify rules, schedules, or capacity settings
• CAN only view/query data and explain how users can make changes themselves
• NEVER offer to book or modify - you cannot do these things
"""
```

**Step 2: Commit**

```bash
git add capacity_chatbot/prompts.py
git commit -m "feat(MYK-64517): add appointment data query section to system prompt"
```

---

### Task 7: Add import for calendar module in date_parser.py

**Files:**
- Modify: `capacity_chatbot/utils/date_parser.py`

The `parse_date_range` function uses `calendar.monthrange`. Ensure the `import calendar` is at the top of the file.

**Step 1: Add the import**

Add `import calendar` to the imports at the top of `capacity_chatbot/utils/date_parser.py` (after `from datetime import ...`):

```python
import calendar
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any
```

**Step 2: Run all tests**

Run: `cd /Users/soahamsundram/Documents/GitHub/appointment-capacity-chatbot && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add capacity_chatbot/utils/date_parser.py
git commit -m "fix(MYK-64517): add calendar import for date range parsing"
```

---

### Task 8: End-to-end verification

**Step 1: Verify imports work**

Run:
```bash
cd /Users/soahamsundram/Documents/GitHub/appointment-capacity-chatbot
python -c "from capacity_chatbot.tools import CAPACITY_TOOLS; print(f'{len(CAPACITY_TOOLS)} tools registered'); print([t.name for t in CAPACITY_TOOLS])"
```
Expected: `8 tools registered` (was 7, now includes `get_appointments_tool`)

**Step 2: Run full test suite**

Run: `cd /Users/soahamsundram/Documents/GitHub/appointment-capacity-chatbot && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 3: Verify tool docstring is correct for Claude**

Run:
```bash
cd /Users/soahamsundram/Documents/GitHub/appointment-capacity-chatbot
python -c "
from capacity_chatbot.tools.appointments import get_appointments_tool
print(get_appointments_tool.name)
print(get_appointments_tool.description[:200])
print('Args:', list(get_appointments_tool.args.keys()))
"
```
Expected: Tool name, description preview, and all parameter names printed correctly.

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(MYK-64517): complete appointment data query tool implementation"
```

---

## Summary of All Tasks

| Task | Description | Files | Tests |
|------|-------------|-------|-------|
| 1 | Date range parsing | `utils/date_parser.py` | `tests/test_date_parser.py` (13 tests) |
| 2 | API client method | `clients/kappointment_client.py` | `tests/test_kappointment_client.py` (2 tests) |
| 3 | Filter pipeline | `utils/appointment_filters.py` | `tests/test_appointment_filters.py` (13 tests) |
| 4 | Formatting utilities | `utils/appointment_formatter.py` | `tests/test_appointment_formatter.py` (7 tests) |
| 5 | Main tool + registration | `tools/appointments.py`, `tools/__init__.py` | — |
| 6 | System prompt update | `prompts.py` | — |
| 7 | Calendar import fix | `utils/date_parser.py` | — |
| 8 | End-to-end verification | — | All tests |

**Total: 8 tasks, 35 tests, 6 files changed/created**
