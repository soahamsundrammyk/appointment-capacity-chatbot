"""Utility to map UUIDs to human-readable names."""

from typing import Any, Dict, List, Optional


class UUIDMapper:
    """Maps UUIDs to names for advisors, teams, transport options, etc."""

    def __init__(self, cached_data: Optional[Dict[str, Any]] = None):
        """Initialize mapper with cached data from UI.

        Args:
            cached_data: Dictionary containing:
                - advisors: List of advisor objects
                - teams: List of team objects
                - transport_options: List of transport option objects
                - hours_of_operation: Hours of operation data
        """
        self.advisor_map: Dict[str, str] = {}  # uuid -> name
        self.team_map: Dict[str, str] = {}      # uuid -> name
        self.transport_map: Dict[str, str] = {} # uuid -> name

        if cached_data:
            self._build_maps(cached_data)

    def _build_maps(self, cached_data: Dict[str, Any]):
        """Build UUID-to-name mappings from cached data."""
        # Map advisors: uuid -> "FirstName LastName"
        advisors = cached_data.get("advisors", [])
        for advisor in advisors:
            uuid = advisor.get("uuid")
            if uuid:
                # Use firstName + lastName
                first_name = advisor.get("firstName", "")
                last_name = advisor.get("lastName", "")
                name = f"{first_name} {last_name}".strip()
                if name:
                    self.advisor_map[uuid] = name
                else:
                    # Fallback to associateName or name fields if firstName/lastName not available
                    fallback_name = advisor.get("associateName", "") or advisor.get("name", "")
                    if fallback_name:
                        self.advisor_map[uuid] = fallback_name

        # Map teams: uuid -> name
        teams = cached_data.get("teams", [])
        for team in teams:
            uuid = team.get("uuid")
            name = team.get("name")
            if uuid and name:
                self.team_map[uuid] = name

        # Map transport options: transportOptionUuid or uuid -> optionName or customName
        transport_options = cached_data.get("transport_options", [])
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Building transport_map from {len(transport_options)} transport options")

        for transport in transport_options:
            # Handle both "transportOptionUuid" (from API) and "uuid" (from test data)
            uuid = transport.get("transportOptionUuid") or transport.get("uuid")
            if uuid:
                # Prefer customName, fallback to optionName
                name = transport.get("customName") or transport.get("optionName")
                if name:
                    self.transport_map[uuid] = name
                    logger.debug(f"Mapped transport: {name} -> {uuid[:20]}...")
                else:
                    logger.warning(f"Transport option with UUID {uuid[:20]}... has no name (customName or optionName)")
            else:
                logger.warning(f"Transport option missing UUID: {transport}")

    def get_advisor_name(self, uuid: str) -> str:
        """Get advisor name from UUID."""
        return self.advisor_map.get(uuid, uuid)

    def get_team_name(self, uuid: str) -> str:
        """Get team name from UUID."""
        return self.team_map.get(uuid, uuid)

    def get_transport_name(self, uuid: str) -> str:
        """Get transport option name from UUID."""
        return self.transport_map.get(uuid, uuid)

    def replace_uuids_in_list(self, uuid_list: List[str], entity_type: str) -> List[str]:
        """Replace UUIDs in a list with names.

        Args:
            uuid_list: List of UUIDs
            entity_type: 'advisor', 'team', or 'transport'

        Returns:
            List of names (or UUIDs if not found)
        """
        if entity_type == "advisor":
            return [self.get_advisor_name(uuid) for uuid in uuid_list]
        elif entity_type == "team":
            return [self.get_team_name(uuid) for uuid in uuid_list]
        elif entity_type == "transport":
            return [self.get_transport_name(uuid) for uuid in uuid_list]
        return uuid_list

    def get_transport_uuid_by_name(self, name: str) -> Optional[str]:
        """Get transport option UUID by name (case-insensitive partial match).

        Args:
            name: Transport option name (e.g., "loaner", "Loaner", "Loaner Car")

        Returns:
            UUID if found, None otherwise
        """
        import logging
        logger = logging.getLogger(__name__)

        name_lower = name.lower().strip()
        logger.debug(f"Searching for transport option '{name}' (normalized: '{name_lower}') in {len(self.transport_map)} options")

        for uuid, transport_name in self.transport_map.items():
            transport_name_lower = transport_name.lower()
            if name_lower in transport_name_lower or transport_name_lower in name_lower:
                logger.info(f"Matched '{name}' -> '{transport_name}' (UUID: {uuid[:20]}...)")
                return uuid

        logger.warning(f"No match found for transport option '{name}'. Available options: {list(self.transport_map.values())}")
        return None

    def get_advisor_uuid_by_name(self, name: str) -> Optional[str]:
        """Get advisor UUID by name (case-insensitive partial match).

        Args:
            name: Advisor name (e.g., "vishal", "Vishal Rai")

        Returns:
            UUID if found, None otherwise
        """
        name_lower = name.lower().strip()
        for uuid, advisor_name in self.advisor_map.items():
            if name_lower in advisor_name.lower() or advisor_name.lower() in name_lower:
                return uuid
        return None

    def get_team_uuid_by_name(self, name: str) -> Optional[str]:
        """Get team UUID by name (case-insensitive partial match).

        Args:
            name: Team name (e.g., "express", "Express Shop")

        Returns:
            UUID if found, None otherwise
        """
        name_lower = name.lower().strip()
        for uuid, team_name in self.team_map.items():
            if name_lower in team_name.lower() or team_name.lower() in name_lower:
                return uuid
        return None

