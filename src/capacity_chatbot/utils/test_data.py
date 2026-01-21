"""Test data utilities for development and testing.

This module provides functions to load cached data from environment-specified
paths or from the frontend. No hardcoded test data is included.
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path


def load_test_data_from_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Load test data from a JSON file.
    
    Args:
        file_path: Path to JSON file containing cached data
        
    Returns:
        Dictionary with test data, or None if file doesn't exist or is invalid
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        pass
    except Exception:
        pass
    
    return None


def get_cached_data_from_env() -> Optional[Dict[str, Any]]:
    """Get cached data from environment-specified file path.
    
    Set TEST_DATA_PATH environment variable to a JSON file containing
    transport options, advisors, teams, and hours_of_operation.
    
    Returns:
        Dictionary with cached data, or None if not configured
    """
    test_data_path = os.getenv("TEST_DATA_PATH")
    if test_data_path and Path(test_data_path).exists():
        return load_test_data_from_file(test_data_path)
    return None


def ensure_cached_data(state: Any) -> None:
    """Ensure cached_data is populated from available sources.
    
    Priority:
    1. Frontend-provided cached_data (already in state)
    2. TEST_DATA_PATH environment variable
    3. Returns with warning if neither available
    
    Args:
        state: CapacityChatbotState instance to modify
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if state.cached_data:
        # Already have cached data from frontend
        return
    
    # Try loading from environment-specified path
    env_data = get_cached_data_from_env()
    if env_data:
        state.cached_data = env_data
        logger.info("Loaded cached data from TEST_DATA_PATH")
        return
    
    # No cached data available - tools will need to handle this gracefully
    logger.warning("No cached_data available. Entity tools may not work correctly.")
