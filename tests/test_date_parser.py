"""Tests for date range parsing."""

from datetime import date

from capacity_chatbot.utils.date_parser import parse_date_range


def test_parse_this_month():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("this month", reference_date=ref)
    assert start == "2026-03-01"
    assert end == "2026-03-31"


def test_parse_last_month():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("last month", reference_date=ref)
    assert start == "2026-02-01"
    assert end == "2026-02-28"


def test_parse_last_month_leap_year():
    ref = date(2028, 3, 15)
    start, end = parse_date_range("last month", reference_date=ref)
    assert start == "2028-02-01"
    assert end == "2028-02-29"


def test_parse_this_week():
    ref = date(2026, 3, 18)  # Wednesday
    start, end = parse_date_range("this week", reference_date=ref)
    assert start == "2026-03-16"  # Monday
    assert end == "2026-03-22"  # Sunday


def test_parse_last_week():
    ref = date(2026, 3, 18)  # Wednesday
    start, end = parse_date_range("last week", reference_date=ref)
    assert start == "2026-03-09"  # Previous Monday
    assert end == "2026-03-15"  # Previous Sunday


def test_parse_today():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("today", reference_date=ref)
    assert start == "2026-03-15"
    assert end == "2026-03-15"


def test_parse_yesterday():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("yesterday", reference_date=ref)
    assert start == "2026-03-14"
    assert end == "2026-03-14"


def test_parse_explicit_date():
    start, end = parse_date_range("2026-03-15")
    assert start == "2026-03-15"
    assert end == "2026-03-15"


def test_parse_last_n_days():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("last 7 days", reference_date=ref)
    assert start == "2026-03-09"  # 7 days: Mar 9-15 inclusive
    assert end == "2026-03-15"


def test_parse_last_30_days():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("last 30 days", reference_date=ref)
    assert start == "2026-02-14"  # 30 days: Feb 14-Mar 15 inclusive
    assert end == "2026-03-15"


def test_parse_tomorrow():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("tomorrow", reference_date=ref)
    assert start == "2026-03-16"
    assert end == "2026-03-16"


def test_parse_next_n_days():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("next 7 days", reference_date=ref)
    assert start == "2026-03-15"
    assert end == "2026-03-21"  # 7 days: Mar 15-21 inclusive


def test_parse_none_returns_none():
    result = parse_date_range(None)
    assert result is None


def test_parse_empty_returns_none():
    result = parse_date_range("")
    assert result is None


def test_parse_unrecognized_returns_none():
    result = parse_date_range("gobbledygook")
    assert result is None
