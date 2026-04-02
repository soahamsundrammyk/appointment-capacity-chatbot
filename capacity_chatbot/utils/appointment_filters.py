"""Client-side appointment filter pipeline.

Mirrors the filter logic from appointment-ui-client's applyFilterToAppointment method.
All filters use AND logic — an appointment must match ALL specified filters.

Supports both data formats:
- MongoDB AppointmentViewData (from /webservice/dealers/{uuid}/appointments)
- Aurora AppointmentInfoLite (from /department/{uuid}/list)
"""

from dataclasses import dataclass
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


def _get_advisor_uuid(appt: dict[str, Any]) -> str | None:
    """Get assigned advisor UUID from either Mongo or Aurora format."""
    # Mongo: assignedDealerAssociateDetail.uuid
    detail = appt.get("assignedDealerAssociateDetail")
    if detail and detail.get("uuid"):
        return detail["uuid"]
    # Aurora: assignedAdvisorUuid
    return appt.get("assignedAdvisorUuid")


def _get_creator_uuid(appt: dict[str, Any]) -> str | None:
    """Get creator advisor UUID from either Mongo or Aurora format."""
    # Mongo: creatorDealerAssociateDetail.uuid
    detail = appt.get("creatorDealerAssociateDetail")
    if detail and detail.get("uuid"):
        return detail["uuid"]
    # Aurora: creatorAdvisorUuid
    return appt.get("creatorAdvisorUuid")


def _get_team_uuid(appt: dict[str, Any]) -> str | None:
    """Get team UUID from either Mongo or Aurora format."""
    # Mongo: teamInfo.uuid
    team_info = appt.get("teamInfo")
    if team_info and team_info.get("uuid"):
        return team_info["uuid"]
    # Aurora: teamUuid
    return appt.get("teamUuid")


def _get_transport_uuid(appt: dict[str, Any]) -> str | None:
    """Get transport option UUID from either Mongo or Aurora format."""
    transport = appt.get("transportOption")
    if transport is None:
        return None
    # Mongo: transportOption.transportOptionUuid
    # Aurora /list: transportOption.uuid
    return transport.get("transportOptionUuid") or transport.get("uuid") or None


def _get_services(appt: dict[str, Any]) -> list[dict[str, Any]]:
    """Get service list from either Mongo or Aurora format."""
    # Mongo: sarQuickOpDetails
    # Aurora: serviceList
    return appt.get("sarQuickOpDetails") or appt.get("serviceList") or []


def _matches_advisor(appt: dict[str, Any], uuids: list[str]) -> bool:
    return _get_advisor_uuid(appt) in uuids


def _matches_creator(appt: dict[str, Any], uuids: list[str]) -> bool:
    return _get_creator_uuid(appt) in uuids


def _matches_status(appt: dict[str, Any], statuses: list[str]) -> bool:
    appt_status = appt.get("status") or ""
    # Case-insensitive comparison
    statuses_lower = [s.lower() for s in statuses]
    return appt_status.lower() in statuses_lower


def _matches_transport(appt: dict[str, Any], uuids: list[str]) -> bool:
    transport_uuid = _get_transport_uuid(appt)
    if not transport_uuid:
        return "NONE" in uuids
    return transport_uuid in uuids


def _matches_team(appt: dict[str, Any], uuids: list[str]) -> bool:
    return _get_team_uuid(appt) in uuids


def _matches_repair_opcode(appt: dict[str, Any], opcodes: list[str]) -> bool:
    services = _get_services(appt)
    opcodes_lower = [o.lower() for o in opcodes]
    for service in services:
        labor_opcode = (service.get("laborOpcode") or service.get("laborOpcode") or "").lower()
        concern_text = (service.get("concernText") or service.get("opcodeName") or "").lower()
        if labor_opcode in opcodes_lower or concern_text in opcodes_lower:
            return True
    return False


def _matches_recall(appt: dict[str, Any], has_recall: bool) -> bool:
    services = _get_services(appt)
    appt_has_recall = any(s.get("recallId") for s in services)
    return appt_has_recall == has_recall


def _matches_prediag(appt: dict[str, Any], statuses: list[str]) -> bool:
    prediag = appt.get("prediagStatus")
    if "HAS_MEDIA" in statuses and appt.get("hasPrediagMedia"):
        return True
    if prediag is None:
        return False
    # Handle enum-style prediag status (e.g., "IN_PROGRESS", "COMPLETED")
    prediag_str = str(prediag) if not isinstance(prediag, str) else prediag
    return prediag_str in statuses


def _matches_source(appt: dict[str, Any], source_values: list[str]) -> bool:
    """Match appointment source against filter values.

    Checks appointmentSourceDetails first (redesigned sources),
    then falls back to createdBy field (legacy platform source like "Web", "DMS").
    This mirrors appointment-ui-client's dual-mode source filtering.
    """
    # Try redesigned source (appointmentSourceDetails.uuid or .name)
    source_details = appt.get("appointmentSourceDetails")
    if source_details:
        source_uuid = source_details.get("uuid", "")
        source_name = source_details.get("name", "")
        for val in source_values:
            val_lower = val.lower()
            if (source_uuid and (val in source_uuid or source_uuid in val)) or \
               (source_name and val_lower == source_name.lower()):
                return True

    # Fall back to legacy createdBy field (e.g., "Web", "DMS", "dealerapp")
    created_by = appt.get("createdBy") or appt.get("appointmentSource") or ""
    if created_by:
        created_by_lower = created_by.lower()
        for val in source_values:
            if val.lower() == created_by_lower:
                return True
    return False


def apply_filters(
    appointments: list[dict[str, Any]], filters: AppointmentFilters
) -> list[dict[str, Any]]:
    """Apply all specified filters to a list of appointments.

    Filters use AND logic — an appointment must match ALL non-None filters.
    Supports both MongoDB AppointmentViewData and Aurora AppointmentInfoLite formats.

    Args:
        appointments: List of appointment dicts from API
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
