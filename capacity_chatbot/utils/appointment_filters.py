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
