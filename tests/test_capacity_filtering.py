"""Regression tests for capacity combination filtering."""

from capacity_chatbot.tools.capacity import (
    _build_entity_display_name,
    _build_entity_map,
    _extract_capacity_entries,
    _entry_matches_filter,
)


def test_build_entity_map_adds_combined_field_combination() -> None:
    uuids = {"advisor": ["advisor-1"], "transport": ["transport-1"], "team": []}

    _, field_combinations = _build_entity_map(uuids=uuids, opcodes=None, source=None)

    assert ["TRANSPORT_OPTION_UUID", "DEALER_ASSOCIATE_UUID"] in field_combinations


def test_entry_matches_filter_requires_intersection_for_multi_entity_queries() -> None:
    entity_map = {
        "SOURCE": ["Web", "DealerApp"],
        "TRANSPORT_OPTION_UUID": ["transport-1"],
        "DEALER_ASSOCIATE_UUID": ["advisor-1"],
    }

    assert not _entry_matches_filter(
        "DEALER_ASSOCIATE_UUID=advisor-1",
        entity_map,
        has_non_source_filters=True,
    )
    assert not _entry_matches_filter(
        "TRANSPORT_OPTION_UUID=transport-1",
        entity_map,
        has_non_source_filters=True,
    )
    assert _entry_matches_filter(
        "DEALER_ASSOCIATE_UUID=advisor-1,TRANSPORT_OPTION_UUID=transport-1",
        entity_map,
        has_non_source_filters=True,
    )


def test_entry_matches_filter_keeps_single_filter_behavior() -> None:
    advisor_only_map = {
        "SOURCE": ["Web", "DealerApp"],
        "DEALER_ASSOCIATE_UUID": ["advisor-1"],
    }
    transport_only_map = {
        "SOURCE": ["Web", "DealerApp"],
        "TRANSPORT_OPTION_UUID": ["transport-1"],
    }

    assert _entry_matches_filter(
        "DEALER_ASSOCIATE_UUID=advisor-1",
        advisor_only_map,
        has_non_source_filters=True,
    )
    assert _entry_matches_filter(
        "TRANSPORT_OPTION_UUID=transport-1",
        transport_only_map,
        has_non_source_filters=True,
    )


def test_entry_matches_filter_source_only_behavior() -> None:
    source_only_map = {"SOURCE": ["Web"]}

    assert _entry_matches_filter(
        "SOURCE=Web",
        source_only_map,
        has_non_source_filters=False,
    )
    assert not _entry_matches_filter(
        "SOURCE=DealerApp",
        source_only_map,
        has_non_source_filters=False,
    )


def test_build_entity_display_name_for_combined_key() -> None:
    class _Mapper:
        advisor_map = {"advisor-1": "Main Advisor"}
        team_map = {}
        transport_map = {"transport-1": "Will Wait"}

    display = _build_entity_display_name(
        "DEALER_ASSOCIATE_UUID=advisor-1,TRANSPORT_OPTION_UUID=transport-1",
        _Mapper(),
    )

    assert display == "Main Advisor - Will Wait"


def test_extract_capacity_entries_multi_filter_includes_combined_and_separate() -> None:
    class _Mapper:
        advisor_map = {"advisor-1": "Main Advisor"}
        team_map = {}
        transport_map = {"transport-1": "Will Wait"}

    capacity_map = {
        "APPOINTMENT_COUNT": {
            "2026-03-23": {
                "combinationWiseCapacity": {
                    "SOURCE=Total": {"usedCount": 20.0, "totalCount": 45.0},
                    "DEALER_ASSOCIATE_UUID=advisor-1": {"usedCount": 10.0, "totalCount": 30.0},
                    "TRANSPORT_OPTION_UUID=transport-1": {"usedCount": 7.0, "totalCount": 19.0},
                    "DEALER_ASSOCIATE_UUID=advisor-1,TRANSPORT_OPTION_UUID=transport-1": {
                        "usedCount": 7.0,
                        "totalCount": 7.0,
                    },
                }
            }
        }
    }
    entity_map = {
        "SOURCE": ["Web", "DealerApp"],
        "TRANSPORT_OPTION_UUID": ["transport-1"],
        "DEALER_ASSOCIATE_UUID": ["advisor-1"],
    }

    entries, _ = _extract_capacity_entries(
        capacity_map=capacity_map,
        uuid_mapper=_Mapper(),
        entity_map=entity_map,
        has_entity_filters=True,
    )
    labels = [entry[1] for entry in entries]

    assert "Combined (Advisor + Transport Option): Main Advisor - Will Wait" in labels
    assert "Advisor Only: Main Advisor" in labels
    assert "Transport Option Only: Will Wait" in labels


def test_extract_capacity_entries_single_filter_unchanged() -> None:
    class _Mapper:
        advisor_map = {"advisor-1": "Main Advisor"}
        team_map = {}
        transport_map = {"transport-1": "Will Wait"}

    capacity_map = {
        "APPOINTMENT_COUNT": {
            "2026-03-23": {
                "combinationWiseCapacity": {
                    "SOURCE=Total": {"usedCount": 20.0, "totalCount": 45.0},
                    "DEALER_ASSOCIATE_UUID=advisor-1": {"usedCount": 10.0, "totalCount": 30.0},
                    "TRANSPORT_OPTION_UUID=transport-1": {"usedCount": 7.0, "totalCount": 19.0},
                }
            }
        }
    }
    entity_map = {
        "SOURCE": ["Web", "DealerApp"],
        "DEALER_ASSOCIATE_UUID": ["advisor-1"],
    }

    entries, _ = _extract_capacity_entries(
        capacity_map=capacity_map,
        uuid_mapper=_Mapper(),
        entity_map=entity_map,
        has_entity_filters=True,
    )
    labels = [entry[1] for entry in entries]

    assert labels == ["Main Advisor"]
