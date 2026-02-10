"""Test data utilities for development and testing."""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def load_test_data_from_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Load test data from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return None


def get_cached_data_from_env() -> Optional[Dict[str, Any]]:
    """Get cached data from TEST_DATA_PATH environment variable."""
    test_data_path = os.getenv("TEST_DATA_PATH")
    if test_data_path and Path(test_data_path).exists():
        return load_test_data_from_file(test_data_path)
    return None


def ensure_cached_data(state: Any) -> None:
    """Ensure cached_data is populated from frontend or TEST_DATA_PATH env var."""
    if state.cached_data:
        return
    
    env_data = get_cached_data_from_env()
    if env_data:
        state.cached_data = env_data
        logger.info("Loaded cached data from TEST_DATA_PATH")
        return
    
    logger.warning("No cached_data available. Entity tools may not work correctly.")


def ensure_state_uuids(state: Any) -> None:
    """Ensure dealer_uuid and department_uuid are populated from env vars for testing.

    This is ONLY for local testing/LangSmith. In production, these should come from the UI client.
    """
    # Only use env vars if state values are empty (not provided by UI client)
    if not state.dealer_uuid:
        env_dealer_uuid = os.getenv("TEST_DEALER_UUID")
        if env_dealer_uuid:
            state.dealer_uuid = env_dealer_uuid
            logger.info("Loaded dealer_uuid from TEST_DEALER_UUID env var (testing mode)")

    if not state.department_uuid:
        env_department_uuid = os.getenv("TEST_DEPARTMENT_UUID")
        if env_department_uuid:
            state.department_uuid = env_department_uuid
            logger.info("Loaded department_uuid from TEST_DEPARTMENT_UUID env var (testing mode)")
