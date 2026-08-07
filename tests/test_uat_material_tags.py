from pathlib import Path

import pytest

from app.models import ProductionOrder, WeighingTransaction
from app.services.material_workflow import build_material_queue
from app.services.weighing import parse_material_tag
from scripts.uat_material_tags import UAT_MATERIAL_TAGS, generate_uat_material_tag_sheet
from tests.test_material_workflow import prepare_orders, seed_material_workflow


def test_uat_tags_parse_and_map_to_the_intended_materials():
    assert len(UAT_MATERIAL_TAGS) == 2
    for definition in UAT_MATERIAL_TAGS:
        parsed = parse_material_tag(definition.payload)
        assert parsed.material_code == definition.material_code
        assert parsed.vendor_lot == definition.container_identity


def test_uat_sheet_generation_is_idempotent(tmp_path):
    first = generate_uat_material_tag_sheet(tmp_path, uat_enabled=True)
    first_contents = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    second = generate_uat_material_tag_sheet(tmp_path, uat_enabled=True)
    second_contents = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    assert first == second == tmp_path / "index.html"
    assert first_contents == second_contents
    assert set(first_contents) == {"index.html", "MOCK-RM001.png", "MOCK-RM002.png"}


def test_uat_sheet_generation_refuses_production(tmp_path):
    with pytest.raises(RuntimeError, match="disabled outside development/UAT"):
        generate_uat_material_tag_sheet(tmp_path, uat_enabled=False)
    assert list(tmp_path.iterdir()) == []


def test_cli_refuses_when_uat_configuration_is_disabled(app, tmp_path):
    result = app.test_cli_runner().invoke(
        args=["generate-uat-material-tags", "--output-directory", str(tmp_path)]
    )

    assert result.exit_code != 0
    assert "disabled outside development/UAT" in result.output
    assert list(tmp_path.iterdir()) == []


def test_uat_sheet_generation_does_not_change_orders_or_transactions(app, tmp_path):
    with app.app_context():
        _, _, _, _, _, orders, _, _ = seed_material_workflow(2)
        statuses_before = [order.status for order in orders]

        generate_uat_material_tag_sheet(tmp_path, uat_enabled=True)

        statuses_after = [
            db_order.status
            for db_order in ProductionOrder.query.order_by(ProductionOrder.id).all()
        ]
        assert statuses_after == statuses_before
        assert WeighingTransaction.query.count() == 0


def test_exact_uat_tags_build_six_order_queues_without_selecting_or_saving(app):
    with app.app_context():
        user, station, _, _, _, orders, _, _ = seed_material_workflow(
            6, material_codes=("MOCK-RM001", "MOCK-RM002")
        )
        prepare_orders(user, station, orders)

        first_queue = build_material_queue(station.id, UAT_MATERIAL_TAGS[0].payload)
        second_queue = build_material_queue(station.id, UAT_MATERIAL_TAGS[1].payload)

        assert [item.production_order.po_no for item in first_queue.items] == [
            f"PD{number:03d}" for number in range(1, 7)
        ]
        assert len(second_queue.items) == 6
        assert first_queue.pending_count == second_queue.pending_count == 6
        assert WeighingTransaction.query.count() == 0


def test_generated_sheet_contains_only_supplied_uat_tag_information(tmp_path):
    sheet = generate_uat_material_tag_sheet(tmp_path, uat_enabled=True)
    contents = Path(sheet).read_text(encoding="utf-8")
    for definition in UAT_MATERIAL_TAGS:
        assert definition.material_code in contents
        assert definition.material_name in contents
        assert definition.container_identity in contents
        assert definition.payload in contents
