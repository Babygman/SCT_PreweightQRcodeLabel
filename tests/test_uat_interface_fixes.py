from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.presentation import format_local_date, format_local_datetime, parse_user_date


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("05/08/2026", date(2026, 8, 5)),
        ("29/02/2024", date(2024, 2, 29)),
        (date(2026, 8, 5), date(2026, 8, 5)),
    ],
)
def test_strict_operator_date_parser(raw, expected):
    assert parse_user_date(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "08/05/2026 extra",
        "2026-08-05",
        "29/02/2025",
        "31/04/2026",
        "00/12/2026",
        "05/13/2026",
        "5/8/2026",
    ],
)
def test_operator_date_parser_rejects_ambiguous_or_impossible_values(raw):
    with pytest.raises(ValueError, match="dd/mm/yyyy"):
        parse_user_date(raw)


def test_operator_date_parser_blank_required_and_optional():
    with pytest.raises(ValueError, match="required"):
        parse_user_date(" ")
    assert parse_user_date(" ", required=False) is None


def test_shared_date_and_datetime_output_are_unambiguous_and_timezone_once():
    naive = datetime(2026, 8, 19, 9, 46, 57, 999999)
    aware = naive.replace(tzinfo=UTC)
    expected = "19/08/2026 16:46:57 (Thailand Time)"
    assert format_local_date(date(2026, 8, 5)) == "05/08/2026"
    assert format_local_datetime(naive, "Asia/Bangkok") == expected
    assert format_local_datetime(aware, "Asia/Bangkok") == expected
    assert expected.count("Thailand Time") == 1


def test_owned_templates_have_no_native_or_us_date_placeholders():
    templates = Path("app/templates")
    content = "\n".join(path.read_text() for path in templates.rglob("*.html"))
    assert 'type="date"' not in content
    assert "mm/dd/yyyy" not in content.lower()


def test_home_template_has_responsive_semantic_card_groups():
    content = Path("app/templates/index.html").read_text()
    for expected in (
        "Production Weighing",
        "Material Tag Management",
        "Administration &amp; UAT Tools",
        "home-nav-grid",
        "home-nav-card",
        "@media (max-width:991.98px)",
        "@media (max-width:575.98px)",
        "aria-labelledby",
        "focus-visible",
    ):
        assert expected in content
    assert "d-flex gap-2 flex-wrap" not in content
