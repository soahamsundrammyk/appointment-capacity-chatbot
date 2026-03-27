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
