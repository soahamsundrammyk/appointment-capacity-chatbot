"""Tests for appointment filter pipeline."""

import pytest

from capacity_chatbot.utils.appointment_filters import apply_filters, AppointmentFilters


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


def test_filter_by_source_legacy_created_by():
    """When appointmentSourceDetails is None, fall back to createdBy field."""
    appts_with_legacy = [
        {
            "uuid": "appt-legacy-1",
            "appointmentSourceDetails": None,
            "createdBy": "Web",
            "status": "UPDATED",
        },
        {
            "uuid": "appt-legacy-2",
            "appointmentSourceDetails": None,
            "createdBy": "dealerapp",
            "status": "UPDATED",
        },
        {
            "uuid": "appt-legacy-3",
            "appointmentSourceDetails": {"uuid": "src-web"},
            "createdBy": "Web",
            "status": "UPDATED",
        },
    ]
    # Match by legacy createdBy
    filters = AppointmentFilters(source_uuids=["Web"])
    result = apply_filters(appts_with_legacy, filters)
    assert len(result) == 2
    assert result[0]["uuid"] == "appt-legacy-1"
    assert result[1]["uuid"] == "appt-legacy-3"


def test_filter_by_source_legacy_case_insensitive():
    """Legacy createdBy matching should be case-insensitive."""
    appts = [
        {"uuid": "a1", "appointmentSourceDetails": None, "createdBy": "dealerapp", "status": "N"},
        {"uuid": "a2", "appointmentSourceDetails": None, "createdBy": "DealerApp", "status": "N"},
    ]
    filters = AppointmentFilters(source_uuids=["dealerapp"])
    result = apply_filters(appts, filters)
    assert len(result) == 2


def test_filter_by_transport_api_uuid_field():
    """API /list endpoint returns 'uuid' not 'transportOptionUuid'."""
    appts = [
        {
            "uuid": "appt-api-format",
            "transportOption": {"uuid": "tp-loaner", "transportation": "Loaner"},
            "status": "N",
        },
        {
            "uuid": "appt-cached-format",
            "transportOption": {"transportOptionUuid": "tp-loaner", "optionName": "Loaner"},
            "status": "N",
        },
    ]
    filters = AppointmentFilters(transport_option_uuids=["tp-loaner"])
    result = apply_filters(appts, filters)
    assert len(result) == 2


def test_filter_by_transport_null_uuid():
    """Transport option present but with null uuid should match NONE."""
    appts = [
        {
            "uuid": "appt-null-transport",
            "transportOption": {"uuid": None, "transportation": None},
            "status": "N",
        },
    ]
    filters = AppointmentFilters(transport_option_uuids=["NONE"])
    result = apply_filters(appts, filters)
    assert len(result) == 1
