"""Test data for development and testing when cached_data is not available from UI.

This module provides mock cached data (transport options, advisors, teams) for testing
in LangGraph Studio or other environments where the appointment-ui-client is not available.
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path


def get_test_cached_data() -> Dict[str, Any]:
    """Get test cached data for development/testing.
    
    Returns:
        Dictionary with test transport options, advisors, and teams
    """
    # Check if there's a custom test data file
    test_data_path = os.getenv("TEST_DATA_PATH")
    if test_data_path and Path(test_data_path).exists():
        try:
            with open(test_data_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load test data from {test_data_path}: {e}")
    
    # Default test data with real UUIDs from your environment
    return {
        "transport_options": [
            {
                "transportOptionUuid": "-f_LNZEWiHQg4AbTH-b_qmDTO8CKwkSQXCtpYFHfWGw",
                "uuid": "-f_LNZEWiHQg4AbTH-b_qmDTO8CKwkSQXCtpYFHfWGw",
                "optionName": "Loaner",
                "customName": "Loaner",
                "description": "Loaner vehicle for customer use"
            },
            {
                "transportOptionUuid": "w5fkIJojY4v-pCn0VBtnCur1AsjPwkH2RHUpf89LiMU",
                "uuid": "w5fkIJojY4v-pCn0VBtnCur1AsjPwkH2RHUpf89LiMU",
                "optionName": "Shuttle",
                "customName": "Shuttle",
                "description": "Shuttle service"
            },
            {
                "transportOptionUuid": "qhLQ5MDZWWsZOwy_YEtuvPhz6ZliEkjcrHSqFYdI-o0",
                "uuid": "qhLQ5MDZWWsZOwy_YEtuvPhz6ZliEkjcrHSqFYdI-o0",
                "optionName": "Rental",
                "customName": "Rental",
                "description": "Rental car"
            },
            {
                "transportOptionUuid": "CjaK5wAvBDG7Di6XAt6RpllbGtz9SiHoBzM2vDiFa9Q",
                "uuid": "CjaK5wAvBDG7Di6XAt6RpllbGtz9SiHoBzM2vDiFa9Q",
                "optionName": "Will Wait",
                "customName": "Will Wait",
                "description": "Customer will wait"
            },
            {
                "transportOptionUuid": "recb8K8QYLpT0MQ2RcLZ88KvcIyTYbpi06jGC68FbG0",
                "uuid": "recb8K8QYLpT0MQ2RcLZ88KvcIyTYbpi06jGC68FbG0",
                "optionName": "Pickup and Delivery",
                "customName": "Pickup and Delivery",
                "description": "Pickup and delivery service"
            },
            {
                "transportOptionUuid": "GAdmMvUX28pIJDH50WjCST4s9LV9bY6NhTA0ZV0BPFw",
                "uuid": "GAdmMvUX28pIJDH50WjCST4s9LV9bY6NhTA0ZV0BPFw",
                "optionName": "custom1",
                "customName": "Uber",
                "description": "Uber service"
            },
            {
                "transportOptionUuid": "5x0UBZkDuwv1e2D5zC_6Wk2anUyUtGwAa4NiuCMUxpo",
                "uuid": "5x0UBZkDuwv1e2D5zC_6Wk2anUyUtGwAa4NiuCMUxpo",
                "optionName": "custom2",
                "customName": "custom2",
                "description": "Custom transport option"
            }
        ],
        "advisors": [
            {
                "uuid": "65fbbd1b95e323d5989d2177c84ec848518702e2693e5017bc57408649acdcf7",
                "firstName": "Art",
                "lastName": "TRQA",
                "nickname": "Art",
                "email": None
            },
            {
                "uuid": "48bc2873b73c50d58bea5f8dcd54e107921953912c7434dcfef5d305db803fe9",
                "firstName": "Leonardo",
                "lastName": "Dcaprio",
                "nickname": "",
                "email": None
            },
            {
                "uuid": "d0e128945f0265b3d79d26b50a035199210fa82636e43ef636d66fbc61b65301",
                "firstName": "Prakash",
                "lastName": "Tiwari",
                "nickname": "Prakash",
                "email": None
            },
            {
                "uuid": "24649b7efd4897dc5e06891e4d72aec438cc1f9ad7fbeb800f506f85eb41d134",
                "firstName": "Alice",
                "lastName": "Tester",
                "nickname": "Alice",
                "email": None
            },
            {
                "uuid": "80c9166f65eecad91e3855555198156470d9cd3e5d7a95841c3a2a7086d1c87a",
                "firstName": "Donald",
                "lastName": "Dunkin",
                "nickname": "Donald",
                "email": None
            },
            {
                "uuid": "66cebf68a172d747363089c55c0d4fab9b6f745d72f2cd239041bdae4550c59f",
                "firstName": "Main",
                "lastName": "Shop",
                "nickname": "Main",
                "email": None
            },
            {
                "uuid": "32fa246ef16c3095e548065f156c1d65c9f52483dc62e7592d8171d189abcd1e",
                "firstName": "Martin",
                "lastName": "Sales",
                "nickname": "Martin",
                "email": None
            },
            {
                "uuid": "c831a54657e6783de70a10f8f63fbf79d05018b44a06aa6305bed3c68560a3a5",
                "firstName": "Sri",
                "lastName": "Mouli",
                "nickname": "Sri",
                "email": None
            },
            {
                "uuid": "dca22399976b1ca1321835f3183d0c3ffca68faea388d5661c49d81e8db382de",
                "firstName": "Vishal",
                "lastName": "Rai",
                "nickname": "Vishal",
                "email": None
            },
            {
                "uuid": "c73f74f2b77918914c1cd8df98830dbda630b3eaa859ff594ba2fbc14de5227e",
                "firstName": "tech1",
                "lastName": "last1",
                "nickname": "tech1",
                "email": None
            }
        ],
        "teams": [
            {
                "uuid": "61bKUgRnHpwu0omhEtq-G_kgwuAphkm6mpa_Htx3sYg",
                "name": "Main Shop",
                "dealerAssociateUuids": [
                    "24649b7efd4897dc5e06891e4d72aec438cc1f9ad7fbeb800f506f85eb41d134",
                    "48bc2873b73c50d58bea5f8dcd54e107921953912c7434dcfef5d305db803fe9",
                    "65fbbd1b95e323d5989d2177c84ec848518702e2693e5017bc57408649acdcf7"
                ]
            },
            {
                "uuid": "BLcD5aDSn_1aB9ZVMqMUBm1-_ayGFhSgoOaKPL8fzO4",
                "name": "Express Shop",
                "dealerAssociateUuids": [
                    "65fbbd1b95e323d5989d2177c84ec848518702e2693e5017bc57408649acdcf7",
                    "32fa246ef16c3095e548065f156c1d65c9f52483dc62e7592d8171d189abcd1e",
                    "c831a54657e6783de70a10f8f63fbf79d05018b44a06aa6305bed3c68560a3a5",
                    "dca22399976b1ca1321835f3183d0c3ffca68faea388d5661c49d81e8db382de"
                ]
            },
            {
                "uuid": "ed99b7Q5xVUCHqyIymvJdL3OZB3xMqZxWIWpE3_D5ms",
                "name": "Rotation Shop",
                "dealerAssociateUuids": [
                    "c73f74f2b77918914c1cd8df98830dbda630b3eaa859ff594ba2fbc14de5227e",
                    "80c9166f65eecad91e3855555198156470d9cd3e5d7a95841c3a2a7086d1c87a"
                ]
            }
        ],
        "hours_of_operation": {
            "monday": {"start": "07:00", "end": "17:30"},
            "tuesday": {"start": "07:00", "end": "17:30"},
            "wednesday": {"start": "07:00", "end": "17:30"},
            "thursday": {"start": "07:00", "end": "17:30"},
            "friday": {"start": "07:00", "end": "17:30"},
            "saturday": {"start": "08:00", "end": "14:00"},
            "sunday": {"start": "09:00", "end": "12:00"}
        }
    }


def load_test_data_from_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Load test data from a JSON file.
    
    Args:
        file_path: Path to JSON file containing test cached data
        
    Returns:
        Dictionary with test data, or None if file doesn't exist or is invalid
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            # Validate structure
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        print(f"Test data file not found: {file_path}")
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in test data file: {e}")
    except Exception as e:
        print(f"Error loading test data: {e}")
    
    return None


def ensure_cached_data(state: Any) -> None:
    """Ensure cached_data is populated, using test data if needed.
    
    This function checks if cached_data is None or empty, and if so,
    loads test data for development/testing.
    
    Args:
        state: CapacityChatbotState instance to modify
    """
    # Only load test data if cached_data is None or empty
    if not state.cached_data:
        # Always load test data if cached_data is empty (for development/testing)
        # This ensures tools have access to transport options, advisors, etc.
        state.cached_data = get_test_cached_data()
        import logging
        logger = logging.getLogger(__name__)
        logger.info("Loaded test cached data for development/testing (cached_data was empty)")
        print("Loaded test cached data for development/testing")

