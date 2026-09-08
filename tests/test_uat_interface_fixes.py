from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import render_template

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


def test_shared_date_and_datetime_output_are_unambiguous_in_bangkok_time():
    naive = datetime(2026, 8, 19, 9, 46, 57, 999999)
    aware = naive.replace(tzinfo=UTC)
    expected = "19/08/2026 16:46"
    assert format_local_date(date(2026, 8, 5)) == "05/08/2026"
    assert format_local_datetime(naive, "Asia/Bangkok") == expected
    assert format_local_datetime(aware, "Asia/Bangkok") == expected
    assert ":57" not in expected


def test_owned_templates_have_no_us_date_placeholders():
    templates = Path("app/templates")
    content = "\n".join(path.read_text() for path in templates.rglob("*.html"))
    assert "mm/dd/yyyy" not in content.lower()


def test_all_editable_date_surfaces_use_the_shared_picker():
    templates = Path("app/templates")
    content = "\n".join(path.read_text() for path in templates.rglob("*.html"))
    assert 'inputmode="numeric"' not in content
    assert 'type="datetime-local"' not in content
    assert content.count('type="date"') == 1
    assert "date_picker(field)" in Path("app/templates/mock_erp/index.html").read_text()
    assert "date_picker(field)" in Path("app/templates/material_tags/new.html").read_text()
    history = Path("app/templates/material_tags/history.html").read_text()
    assert history.count("date_filter(") == 2
    mock_history = Path("app/templates/mock_erp/history.html").read_text()
    assert mock_history.count("date_filter(") == 2

    picker = Path("app/templates/_date_picker.html").read_text()
    assert 'readonly aria-readonly="true"' in picker
    assert picker.count("data-date-button") == 2
    script = Path("app/static/date-picker.js").read_text()
    assert "input.showPicker" in script
    assert "input.focus()" in script
    assert "input.click()" in script


def test_home_template_has_responsive_semantic_card_groups(app):
    content = Path("app/templates/index.html").read_text()
    for expected in (
        "Production Weighing",
        "Material Tag Management",
        "home-nav-grid",
        "home-nav-card",
        "@media (max-width:991.98px)",
        "@media (max-width:575.98px)",
        "aria-labelledby",
        "focus-visible",
    ):
        assert expected in content
    assert "d-flex gap-2 flex-wrap" not in content
    user = SimpleNamespace(
        display_name="Test Administrator",
        roles=[SimpleNamespace(code="ADMIN")],
    )
    station = SimpleNamespace(code="TEST-ST", name="Test Station")
    with app.test_request_context("/"):
        rendered = render_template(
            "index.html", current_user=user, selected_station=station
        )
    assert (
        "การดูแลระบบและเครื่องมือ UAT / Administration &amp; UAT Tools"
        in rendered
    )
