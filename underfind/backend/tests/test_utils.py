from __future__ import annotations

import pytest
from underfind.backend.core.utils import parse_iso8601_duration, clean_transcript_text


def test_parse_iso8601_duration_seconds_only():
    assert parse_iso8601_duration("PT45S") == 45


def test_parse_iso8601_duration_minutes_and_seconds():
    # 1 minute + 30 seconds = 90 seconds
    assert parse_iso8601_duration("PT1M30S") == 90


def test_parse_iso8601_duration_hours_minutes_seconds():
    # 1 hour + 2 minutes + 3 seconds = 3600 + 120 + 3 = 3723
    assert parse_iso8601_duration("PT1H2M3S") == 3723


def test_parse_iso8601_duration_invalid_or_empty():
    assert parse_iso8601_duration("") == 0
    assert parse_iso8601_duration(None) == 0
    assert parse_iso8601_duration("invalid") == 0


def test_clean_transcript_text():
    raw = "  Hello   world!\nThis is a\n\ntest.  "
    cleaned = clean_transcript_text(raw)
    assert cleaned == "Hello world! This is a test."
