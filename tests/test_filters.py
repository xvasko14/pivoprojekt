import pytest
from main import format_date


def test_format_date_basic():
    assert format_date("2026-03-28") == "Sobota 28. marca"


def test_format_date_months():
    assert format_date("2026-01-01") == "Štvrtok 1. januára"
    assert format_date("2026-12-31") == "Štvrtok 31. decembra"


def test_format_date_invalid():
    assert format_date("not-a-date") == "not-a-date"
