"""End-to-end test script for get_appointments_tool.

Tests the tool against a live kappointment-api instance.
Set KAPPOINTMENT_API_BASE_URL to point to your GVM.

Usage:
    KAPPOINTMENT_API_BASE_URL=https://srishti244.mykaarma.dev \
    python3 scripts/test_appointments_e2e.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capacity_chatbot.clients.kappointment_client import KAppointmentAPIClient

DEPARTMENT_UUID = "8ec821aefe98664ab15df7c426c3c46f9c37d0b1aeda9ff58df3db89bb0a55a3"
DEALER_UUID = "cb731d36fd635ddd6ef8dd43500892b0c0249d1c01a46dbcc445a809c0a8e3b2"

# Advisor UUIDs from SchedulerUser table
DONALD_UUID = "80c9166f65eecad91e3855555198156470d9cd3e5d7a95841c3a2a7086d1c87a"
PRAKASH_UUID = "e8d9a1c6ed0a1b2e77a614cdbae4856f006f5e2020a4a8add6e286664257bbb1"


async def test_list_endpoint():
    """Test the raw /list endpoint against the GVM."""
    async with KAppointmentAPIClient() as client:
        # Test 1: Fetch March 2026 appointments
        print("=" * 60)
        print("TEST 1: Fetch appointments for March 2026")
        print("=" * 60)
        request = {
            "pageNumber": 1,
            "pageSize": 200,
            "startDate": "2026-03-01",
            "endDate": "2026-03-31",
            "orderBy": "createdTimeStamp",
            "isSortAscending": False,
        }
        response = await client.list_appointments(DEPARTMENT_UUID, request)
        total = response.get("totalCount", 0)
        appointments = response.get("appointmentInfo", [])
        print(f"Total count: {total}")
        print(f"Fetched: {len(appointments)}")

        if appointments:
            print("\nSample appointment:")
            print(json.dumps(appointments[0], indent=2, default=str))

            # Count by advisor
            from collections import Counter
            advisors = Counter(a.get("assignedAdvisorUuid", "unknown")[:12] for a in appointments)
            statuses = Counter(a.get("status", "unknown") for a in appointments)
            cancelled = sum(1 for a in appointments if a.get("isCancelled"))

            print(f"\nBy advisor (first 12 chars): {dict(advisors)}")
            print(f"By status: {dict(statuses)}")
            print(f"Cancelled: {cancelled}")

            # Check transport options
            with_transport = sum(1 for a in appointments if a.get("transportOption"))
            print(f"With transport option: {with_transport}/{len(appointments)}")

            # Check services
            with_services = sum(1 for a in appointments if a.get("serviceList"))
            print(f"With services: {with_services}/{len(appointments)}")
        else:
            print("WARNING: No appointments returned!")

        # Test 2: Filter by createdBy
        print("\n" + "=" * 60)
        print("TEST 2: Filter by createdBy=Web")
        print("=" * 60)
        request2 = {
            "pageNumber": 1,
            "pageSize": 200,
            "startDate": "2026-03-01",
            "endDate": "2026-03-31",
            "createdBy": "Web",
        }
        response2 = await client.list_appointments(DEPARTMENT_UUID, request2)
        print(f"Web appointments: {response2.get('totalCount', 0)}")

        # Test 3: Filter by created date range
        print("\n" + "=" * 60)
        print("TEST 3: Filter by startCreatedDate/endCreatedDate")
        print("=" * 60)
        request3 = {
            "pageNumber": 1,
            "pageSize": 200,
            "startCreatedDate": "2026-03-01",
            "endCreatedDate": "2026-03-31",
        }
        response3 = await client.list_appointments(DEPARTMENT_UUID, request3)
        print(f"Created in March: {response3.get('totalCount', 0)}")

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_list_endpoint())
