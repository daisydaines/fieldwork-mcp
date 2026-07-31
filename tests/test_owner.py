"""Tests for owner-facing helpers (no live API)."""

from __future__ import annotations

from datetime import date

import pytest

from fieldwork_mcp.owner import _date_range


def test_date_range_days() -> None:
    start, end = _date_range(days=7, start_date=None, end_date="2026-07-30")
    assert end == date(2026, 7, 30)
    assert start == date(2026, 7, 24)


def test_date_range_explicit() -> None:
    start, end = _date_range(days=None, start_date="2026-07-01", end_date="2026-07-15")
    assert start == date(2026, 7, 1)
    assert end == date(2026, 7, 15)


def test_date_range_invalid() -> None:
    with pytest.raises(ValueError):
        _date_range(days=None, start_date="2026-08-01", end_date="2026-07-01")