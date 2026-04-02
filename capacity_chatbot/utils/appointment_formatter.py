"""Formatting utilities for appointment data output.

Handles both summary mode (counts, breakdowns) and list mode (paginated records).
Supports both MongoDB AppointmentViewData and Aurora AppointmentInfoLite formats.
"""

import math
from collections import Counter
from typing import Any

from capacity_chatbot.utils.uuid_mapper import UUIDMapper

MAX_BREAKDOWN_ITEMS = 10
MAX_LIST_PAGE_SIZE = 50


def _get_advisor_name(appt: dict[str, Any], uuid_mapper: UUIDMapper) -> str:
    """Get advisor display name from either Mongo or Aurora format."""
    # Mongo: assignedDealerAssociateDetail has fname/lname embedded
    detail = appt.get("assignedDealerAssociateDetail")
    if detail:
        fname = detail.get("fname", "")
        lname = detail.get("lname", "")
        name = ("%s %s" % (fname, lname)).strip()
        if name:
            return name
    # Aurora: assignedAdvisorUuid → resolve via UUIDMapper
    uuid = appt.get("assignedAdvisorUuid", "")
    return uuid_mapper.get_advisor_name(uuid) if uuid else "Unassigned"


def _get_team_name(appt: dict[str, Any], uuid_mapper: UUIDMapper) -> str:
    """Get team display name from either Mongo or Aurora format."""
    # Mongo: teamInfo.name embedded
    team_info = appt.get("teamInfo")
    if team_info and team_info.get("name"):
        return team_info["name"]
    # Aurora: teamUuid → resolve via UUIDMapper
    uuid = appt.get("teamUuid", "")
    return uuid_mapper.get_team_name(uuid) if uuid else "No Team"


def _get_transport_name(appt: dict[str, Any]) -> str:
    """Get transport option display name from either Mongo or Aurora format."""
    transport = appt.get("transportOption")
    if not transport:
        return "None"
    return transport.get("optionName") or transport.get("customName") or transport.get("transportation") or "N/A"


def _get_services(appt: dict[str, Any]) -> list[dict[str, Any]]:
    """Get service list from either Mongo or Aurora format."""
    return appt.get("sarQuickOpDetails") or appt.get("serviceList") or []


def _get_service_names(appt: dict[str, Any]) -> list[str]:
    """Get human-readable service names."""
    services = _get_services(appt)
    names = []
    for s in services:
        name = s.get("concernText") or s.get("opcodeName") or s.get("description") or s.get("laborOpcode") or ""
        if name:
            names.append(name)
    return names[:3]


def format_summary(
    appointments: list[dict[str, Any]],
    date_range_label: str,
    uuid_mapper: UUIDMapper,
) -> str:
    """Format appointment data as a summary with counts."""
    total = len(appointments)

    if total == 0:
        return "Appointments (%s): 0 total — no appointments found matching your filters." % date_range_label

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
    """Format appointments as a paginated list."""
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
    preferred_date = appt.get("preferredDate", "N/A")
    start_time = appt.get("startTime", "")
    # Handle both "HH:MM" (Mongo) and "YYYY-MM-DD HH:MM:SS" (Aurora) formats
    if start_time and len(start_time) > 16:
        date_str = start_time[:10]
        time_str = start_time[11:16]
    else:
        date_str = preferred_date
        time_str = start_time[:5] if start_time else ""

    advisor_name = _get_advisor_name(appt, uuid_mapper)
    service_names = _get_service_names(appt)
    service_str = ", ".join(service_names) if service_names else "No services"
    transport_name = _get_transport_name(appt)

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
    """Format appointment data grouped by a specific dimension."""
    total = len(appointments)
    if total == 0:
        return "Appointments by %s (%s): 0 total — no appointments found." % (
            group_by.replace("_", " ").title(), date_range_label
        )

    groups: dict[str, list[dict[str, Any]]] = {}
    for appt in appointments:
        key = _get_group_key(appt, group_by, uuid_mapper)
        groups.setdefault(key, []).append(appt)

    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)

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
        return _get_advisor_name(appt, uuid_mapper)

    if group_by == "team":
        return _get_team_name(appt, uuid_mapper)

    if group_by == "status":
        if appt.get("isCancelled"):
            return "Cancelled"
        return appt.get("status", "Unknown")

    if group_by == "source":
        source = appt.get("appointmentSourceDetails")
        if source:
            return source.get("name", source.get("uuid", "Unknown"))
        created_by = appt.get("createdBy") or appt.get("appointmentSource")
        return created_by if created_by else "Unknown"

    if group_by == "transport_option":
        return _get_transport_name(appt)

    return "Unknown"
