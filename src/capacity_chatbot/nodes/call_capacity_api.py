"""Node for calling getCapacity API endpoint."""

import logging
from datetime import datetime, timedelta

from capacity_chatbot.services.kappointment_client import KAppointmentAPIClient
from capacity_chatbot.state import CapacityChatbotState

logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> str:
    """Parse date string to YYYY-MM-DD format.
    
    Handles relative dates like "tomorrow", "today", etc.
    """
    date_str_lower = date_str.lower().strip()
    today = datetime.now().date()
    
    if date_str_lower == "today":
        return today.strftime("%Y-%m-%d")
    elif date_str_lower == "tomorrow":
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif date_str_lower == "yesterday":
        return (today - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        # Assume it's already in YYYY-MM-DD format or try to parse
        try:
            # Try parsing common formats
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                try:
                    parsed = datetime.strptime(date_str, fmt).date()
                    return parsed.strftime("%Y-%m-%d")
                except ValueError:
                    continue
            # If all parsing fails, return as-is (might be invalid)
            return date_str
        except Exception:
            return date_str


def call_capacity_api(state: CapacityChatbotState) -> CapacityChatbotState:
    """Call getCapacity endpoint based on extracted entities."""
    
    if not state.department_uuid:
        state.errors.append("Department UUID is required")
        return state
    
    entities = state.extracted_entities
    dates = entities.get("dates", [])
    
    # Parse dates
    parsed_dates = [parse_date(d) for d in dates] if dates else []
    
    # If no dates provided, default to tomorrow
    if not parsed_dates:
        tomorrow = (datetime.now() + timedelta(days=1)).date().strftime("%Y-%m-%d")
        parsed_dates = [tomorrow]
        state.reasoning.append(f"No date provided, defaulting to tomorrow: {tomorrow}")
    
    # Build CapacityRequest
    capacity_request = {
        "capacityTypeSet": ["APPOINTMENT_COUNT"],
        "applicabilityRuleField": "DATE",  # Can be DATE, DATE_AND_TIME, etc.
        "applicabilityFieldValues": parsed_dates,
        "fieldCombinations": [],
    }
    
    # Add transport option filter if specified
    transport_uuids = entities.get("transport_option_uuids", [])
    if transport_uuids:
        capacity_request["fieldCombinations"] = [["TRANSPORT_OPTION_UUID"]]
        capacity_request["entityMap"] = {
            "TRANSPORT_OPTION_UUID": transport_uuids
        }
    
    # Add advisor filter if specified
    advisor_uuids = entities.get("advisor_uuids", [])
    if advisor_uuids:
        if "fieldCombinations" not in capacity_request:
            capacity_request["fieldCombinations"] = []
        if ["DEALER_ASSOCIATE_UUID"] not in capacity_request["fieldCombinations"]:
            capacity_request["fieldCombinations"].append(["DEALER_ASSOCIATE_UUID"])
        if "entityMap" not in capacity_request:
            capacity_request["entityMap"] = {}
        capacity_request["entityMap"]["DEALER_ASSOCIATE_UUID"] = advisor_uuids
    
    try:
        # Initialize API client
        from capacity_chatbot.config.api_config import KAppointmentAPIConfig
        config = KAppointmentAPIConfig()
        client = KAppointmentAPIClient(config=config)
        
        # Call API (using sync wrapper for now - can be made async later)
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        response = loop.run_until_complete(client.get_capacity(state.department_uuid, capacity_request))
        
        # Store response
        state.capacity_data = response
        state.reasoning.append(f"Successfully called getCapacity API for dates: {parsed_dates}")
        logger.info(f"Capacity API response: {response}")
        
        loop.run_until_complete(client.close())
        
    except Exception as e:
        logger.error(f"Error calling getCapacity API: {e}")
        state.errors.append(f"Error calling getCapacity API: {str(e)}")
    
    return state

