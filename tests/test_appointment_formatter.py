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
    assert "UPDATED" in result or "2" in result
    assert "CANCELLED" in result or "1" in result


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
    assert "Cancelled" in result


def test_format_grouped_summary_by_team():
    mapper = UUIDMapper(SAMPLE_CACHED_DATA)
    result = format_grouped_summary(SAMPLE_APPOINTMENTS, "team", "Mar 2026", mapper)
    assert "Express Shop" in result
    assert "Main Shop" in result
