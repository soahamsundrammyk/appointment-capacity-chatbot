# Appointment Data Query Tool — Design Document

**Date:** 2026-03-27
**Jira:** MYK-64517
**Author:** Soaham Sundram

## Problem

The capacity chatbot currently only answers capacity-related questions (available slots, rules, opcodes). Users need to query historical and current appointment data — "how many appointments last month?", "show me Diego's appointments this month", "break down by status." The backend API exists (`POST /v2/department/{uuid}/list`), but the chatbot has no tool to call it.

## Decision Summary

| Decision | Choice | Rationale |
|---|---|---|
| Architecture | Add tools to existing ReAct agent | One API call + post-processing = a tool, not a node. 9-10 tools is within Claude's comfort zone. |
| Backend | Use existing `/list` endpoint, post-process in Python | No kappointment-api changes needed. All 11 filters handled client-side. |
| Tool design | Single tool with `mode` parameter ("summary" / "list") | Simpler than two tools. Claude handles parameter selection well. |
| Filter coverage | All 11 filter types from appointment-ui-client | All are post-processing on same response. Minimal incremental effort. |
| Naming | Keep existing names (capacity_chatbot, etc.) | Rename to "scheduler bot" in a later phase. |

## Tool Interface

```python
@tool
async def get_appointments_tool(
    # Mode
    mode: str = "summary",                        # "summary" or "list"

    # Date filters (server-side → sent to API)
    start_date: str | None = None,                # Scheduled date from (yyyy-MM-dd or natural language)
    end_date: str | None = None,                  # Scheduled date to
    start_created_date: str | None = None,        # Created date from
    end_created_date: str | None = None,          # Created date to

    # Server-side filters (sent to API)
    team_names: list[str] | None = None,          # Resolved to UUIDs via UUIDMapper
    created_by_platform: str | None = None,       # "Web", "DealerApp", "DMS", etc.

    # Client-side filters (post-processed in Python)
    advisor_names: list[str] | None = None,       # Assigned advisor
    creator_advisor_names: list[str] | None = None, # Who created the appointment
    status: list[str] | None = None,              # e.g. ["UPDATED", "CANCELLED"]
    transport_option_names: list[str] | None = None,
    repair_concerns: list[str] | None = None,     # Opcode/service names
    has_recall: bool | None = None,
    prediag_status: list[str] | None = None,      # AI survey status

    # Pagination (list mode only)
    page: int = 1,
    page_size: int = 50,

    # Summary options
    group_by: str | None = None,                  # "advisor", "team", "status", "source", "transport_option"

    config: RunnableConfig = None,
) -> str:
```

## Data Flow

```
User query
  → Claude selects get_appointments_tool with parameters
  → Tool resolves names to UUIDs (advisor_names → advisor UUIDs via UUIDMapper)
  → Tool builds FilterServiceAppointmentRequest:
      - startDate/endDate or startCreatedDate/endCreatedDate (parsed from natural language)
      - teamUuids (resolved from team_names)
      - createdBy (created_by_platform)
      - pageSize=200, pageNumber=1
  → API call: POST /v2/department/{uuid}/list
  → If totalCount > 200: fetch remaining pages concurrently (asyncio.gather)
  → Safety cap: 10,000 records max (50 pages)
  → Apply client-side filter pipeline:
      advisor_names → match assignedAdvisorUuid
      creator_advisor_names → match creatorAdvisorUuid
      status → match status field
      transport_option_names → match transportOption.transportOptionUuid
      repair_concerns → match serviceList[].laborOpcode
      has_recall → check serviceList[].recallId
      prediag_status → match prediagStatus field
  → Format based on mode:
      summary → total count + breakdowns (by group_by if specified)
      list → paginated formatted records
  → Return formatted string to Claude
```

## Pagination Strategy

Fetch all pages for accurate post-filtered counts. The API's `totalCount` only reflects server-side filters — client-side filters (advisor, status, transport, etc.) require all records.

1. First call: `pageSize=200`, `pageNumber=1` → get `totalCount`
2. If `totalCount > 200`: fetch remaining pages concurrently with `asyncio.gather`
3. Cap at 10,000 records (50 pages). If more, return count with a note that results are capped.

## Response Formatting

### Summary mode (default)

```
Appointments (Feb 1 - Feb 28, 2026): 342 total

By Status: 280 Completed, 45 Cancelled, 17 Open
```

With `group_by="advisor"`:

```
Appointments by Advisor (Feb 2026): 342 total

| Advisor          | Total | Completed | Cancelled |
|------------------|-------|-----------|-----------|
| Diego Martinez   | 45    | 38        | 7         |
| Maria Lopez      | 62    | 55        | 7         |
```

### List mode

```
Appointments (Page 1 of 10, showing 50 of 342):

1. Mar 15 9:00 AM - Diego Martinez | Oil Change, Tire Rotation | Loaner | Completed
2. Mar 15 10:30 AM - Diego Martinez | Brake Inspection | Waiter | Cancelled

Page 1 of 10. Ask for next page or refine filters.
```

**Truncation:** List mode caps at 50 per page. Summary breakdowns show top 10, with "and X more..." if needed.

## System Prompt Addition

```
APPOINTMENT DATA QUERIES

When user asks about appointment data, history, or statistics:
- Use get_appointments_tool with mode="summary" for counts and breakdowns
- Use get_appointments_tool with mode="list" to show actual appointment records
- Use group_by to break down by: advisor, team, status, source, transport_option
- For "created by [person]" → use creator_advisor_names (who created it)
- For "[person]'s appointments" → use advisor_names (who it's assigned to)
- Always clarify date range if user is ambiguous
- Default to "this month" if no date specified and query is about historical data
```

## Files Changed

| File | Change |
|---|---|
| `tools/appointments.py` | **NEW** — get_appointments_tool with filter pipeline and formatting |
| `tools/__init__.py` | Add get_appointments_tool to CAPACITY_TOOLS |
| `clients/kappointment_client.py` | Add `list_appointments()` method |
| `prompts.py` | Add appointment data query section to system prompt |
| `utils/date_parser.py` | Extend to handle "last month", "this month", "this week" → date ranges |
| `enums/enums.py` | Add appointment status enum if needed |

**No changes to:** `graph.py`, `state.py`, `routes.py`, `middleware/`. Graph structure stays identical.

## Example Queries

| User question | Tool parameters |
|---|---|
| "How many appts last month?" | `mode="summary", start_created_date="last month"` |
| "Break that down by advisor" | `mode="summary", start_created_date="last month", group_by="advisor"` |
| "Show me Diego's appointments this month" | `mode="list", start_created_date="this month", advisor_names=["Diego"]` |
| "How many were cancelled?" | `mode="summary", start_created_date="this month", status=["CANCELLED"]` |
| "Web scheduler appointments today" | `mode="summary", start_date="today", created_by_platform="Web"` |
| "Appointments with recalls this week" | `mode="summary", start_date="this week", has_recall=True` |
