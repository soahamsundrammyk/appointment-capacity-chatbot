"""Utility to map UUIDs to human-readable names."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
        self.team_map: Dict[str, str] = {}  # uuid -> name
        self.transport_map: Dict[str, str] = {}  # uuid -> name

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
        logger.debug("Building transport_map from %d transport options", len(transport_options))

        for transport in transport_options:
            # Handle both "transportOptionUuid" (from API) and "uuid" (from test data)
            uuid = transport.get("transportOptionUuid") or transport.get("uuid")
            if uuid:
                # Prefer customName, fallback to optionName
                name = transport.get("customName") or transport.get("optionName")
                if name:
                    self.transport_map[uuid] = name
                    logger.debug("Mapped transport: %s -> %s...", name, uuid[:20])
                else:
                    logger.warning("Transport option with UUID %s... has no name (customName or optionName)", uuid[:20])
            else:
                logger.warning("Transport option missing UUID: %s", transport)

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
        # Map entity types to their respective getter methods
        entity_getters = {
            "advisor": self.get_advisor_name,
            "team": self.get_team_name,
            "transport": self.get_transport_name,
        }
        getter = entity_getters.get(entity_type)
        if getter:
            return [getter(uuid) for uuid in uuid_list]
        return uuid_list

    def _get_uuid_by_name(self, name: str, entity_map: Dict[str, str], entity_type: str) -> Optional[str]:
        """Generic helper to get UUID by name (case-insensitive partial match).

        Args:
            name: Entity name to search for
            entity_map: Dictionary mapping UUID -> name
            entity_type: Type of entity (for logging)

        Returns:
            UUID if found, None otherwise
        """
        name_lower = name.lower().strip()
        logger.debug("Searching for %s '%s' (normalized: '%s') in %d options", entity_type, name, name_lower, len(entity_map))

        for uuid, entity_name in entity_map.items():
            entity_name_lower = entity_name.lower()
            if name_lower in entity_name_lower or entity_name_lower in name_lower:
                logger.debug("Matched %s '%s' -> '%s' (UUID: %s...)", entity_type, name, entity_name, uuid[:20])
                return uuid

        logger.warning("No match found for %s '%s'. Available options: %s", entity_type, name, list(entity_map.values()))
        return None

    def get_transport_uuid_by_name(self, name: str) -> Optional[str]:
        """Get transport option UUID by name (case-insensitive partial match).

        Args:
            name: Transport option name (e.g., "loaner", "Loaner", "Loaner Car")

        Returns:
            UUID if found, None otherwise
        """
        return self._get_uuid_by_name(name, self.transport_map, "transport option")

    def get_advisor_uuid_by_name(self, name: str) -> Optional[str]:
        """Get advisor UUID by name (case-insensitive partial match).

        Args:
            name: Advisor name (e.g., "vishal", "Vishal Rai")

        Returns:
            UUID if found, None otherwise
        """
        return self._get_uuid_by_name(name, self.advisor_map, "advisor")

    def get_team_uuid_by_name(self, name: str) -> Optional[str]:
        """Get team UUID by name (case-insensitive partial match).

        Args:
            name: Team name (e.g., "express", "Express Shop")

        Returns:
            UUID if found, None otherwise
        """
        return self._get_uuid_by_name(name, self.team_map, "team")


def resolve_uuids_by_field(field: str, values: List[Any], uuid_mapper: UUIDMapper) -> List[Any]:
    """Resolve UUIDs to names based on field type.
    
    Maps API field names to entity types and uses UUIDMapper to convert UUIDs to names.
    
    Args:
        field: API field name (e.g., "DEALER_ASSOCIATE_UUID", "TEAM_UUID", "TRANSPORT_OPTION_UUID")
        values: List of UUIDs or values to resolve
        uuid_mapper: UUIDMapper instance
        
    Returns:
        List of names (or original values if field doesn't match known types)
        
    Examples:
        resolve_uuids_by_field("DEALER_ASSOCIATE_UUID", ["uuid1", "uuid2"], mapper)
        # Returns: ["John Doe", "Jane Smith"]
        
        resolve_uuids_by_field("TEAM_UUID", ["team-uuid"], mapper)
        # Returns: ["Express Shop"]
    """
    # Map API field names to entity types
    field_to_entity_type = {
        "DEALER_ASSOCIATE_UUID": "advisor",
        "TEAM_UUID": "team",
        "TRANSPORT_OPTION_UUID": "transport",
    }
    
    entity_type = field_to_entity_type.get(field)
    if entity_type:
        return uuid_mapper.replace_uuids_in_list(values, entity_type)
    return values

