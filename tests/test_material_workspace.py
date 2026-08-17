from datetime import UTC, datetime

from app.extensions import db
from app.models import ProductionOrder, WeighingTransaction
from app.presentation import format_local_datetime
from app.services.material_workflow import save_material_queue_item
from tests.test_material_workflow import (
    MATERIAL_A_TAG,
    MATERIAL_B_TAG,
    login,
    prepare_orders,
    seed_material_workflow,
)


def test_initial_workspace_has_no_selection_and_selection_is_read_only(app, client):
    with app.app_context():
        user, station, _, _, _, orders, _, _ = seed_material_workflow(2)
        prepare_orders(user, station, orders)
        station_id = station.id
    login(client, station_id)

    initial = client.get("/weighing/material")
    selected = client.get("/weighing/material?material=MAT-B")

    assert b"Select a Material to begin weighing." in initial.data
    assert b'data-selected="true"' not in initial.data
    assert "MAT-B — Material B".encode() in selected.data
    assert b"Scan the physical Material Tag" in selected.data
    with app.app_context():
        assert WeighingTransaction.query.count() == 0
        assert {order.status for order in ProductionOrder.query.all()} == {"READY"}
        assert all(order.work_set_active for order in ProductionOrder.query.all())


def test_unknown_outside_and_cross_station_selection_are_rejected(app, client):
    with app.app_context():
        user, station, other, _, _, orders, _, _ = seed_material_workflow(1)
        prepare_orders(user, station, orders)
        other_id = other.id
        station_id = station.id
    login(client, station_id)
    assert client.get("/weighing/material?material=UNKNOWN").status_code == 404

    login(client, other_id)
    assert client.get("/weighing/material?material=MAT-A").status_code == 404
    with app.app_context():
        assert WeighingTransaction.query.count() == 0


def test_selected_material_must_match_tag_and_mismatch_has_both_codes(app, client):
    with app.app_context():
        user, station, _, _, _, orders, _, _ = seed_material_workflow(1)
        prepare_orders(user, station, orders)
        station_id = station.id
    login(client, station_id)
    client.get("/weighing/material?material=MAT-A")

    mismatch = client.post(
        "/weighing/material/validate",
        json={"material_tag": MATERIAL_B_TAG, "selected_material_code": "MAT-A"},
    )
    payload = mismatch.get_json()
    assert payload["code"] == "WRONG_SELECTED_MATERIAL"
    assert payload["message"] == "Scanned Material does not match the selected Material."
    assert payload["selected_material_code"] == "MAT-A"
    assert payload["scanned_material_code"] == "MAT-B"
    with app.app_context():
        assert WeighingTransaction.query.count() == 0

    match = client.post(
        "/weighing/material/validate",
        json={"material_tag": MATERIAL_A_TAG, "selected_material_code": "MAT-A"},
    )
    assert match.get_json()["result"] == "MATCH"


def test_partial_material_resumes_and_completed_material_is_read_only(app, client):
    with app.app_context():
        user, station, _, _, _, orders, items_a, _ = seed_material_workflow(2)
        prepare_orders(user, station, orders)
        assert save_material_queue_item(
            station.id, orders[0].id, items_a[0].id, MATERIAL_A_TAG, "1.000", user.id
        ).success
        station_id = station.id
        user_id = user.id
    login(client, station_id)

    partial = client.get("/weighing/material?material=MAT-A")
    assert b"In progress" in partial.data
    assert b"1 of 2 Production Orders completed" in partial.data
    client.post(
        "/weighing/material/validate",
        json={"material_tag": MATERIAL_A_TAG, "selected_material_code": "MAT-A"},
    )
    partial = client.get("/weighing/material")
    assert b"Recorded Actual Weight" in partial.data
    assert "Save Weighing — PD002".encode() in partial.data
    with app.app_context():
        from app.models import User

        user = db.session.get(User, user_id)
        orders = ProductionOrder.query.order_by(ProductionOrder.id).all()
        items = [order.formula.items[0] for order in orders]
        assert save_material_queue_item(
            station_id, orders[1].id, items[1].id, MATERIAL_A_TAG, "1.000", user.id
        ).success

    completed = client.get("/weighing/material?material=MAT-A")
    assert b"2 of 2 Production Orders completed" in completed.data
    assert b"Pending tag scan" not in completed.data
    assert b'name="actual_weight"' not in completed.data
    assert b"Recorded Actual Weight" in completed.data
    assert b"Preweight ID:" in completed.data
    assert "Save Weighing —".encode() not in completed.data


def test_search_filter_ten_materials_and_unsaved_switch_warning_render(app, client):
    codes = tuple(f"MAT-{number:02d}" for number in range(10))
    with app.app_context():
        user, station, _, _, _, orders, _, _ = seed_material_workflow(1, codes[:2])
        # The fixture has two formula lines; add eight distinct material lines.
        formula = orders[0].formula
        from app.models import FormulaItem, Material

        for number, code in enumerate(codes[2:], start=30):
            material = Material(
                code=code,
                name=f"Search Material {code}",
                unit="kg",
                classification="POWDER",
            )
            db.session.add(
                FormulaItem(
                    formula=formula,
                    line_no=number,
                    material=material,
                    target_weight=1,
                    unit="kg",
                )
            )
        db.session.commit()
        prepare_orders(user, station, orders)
        station_id = station.id
    login(client, station_id)
    page = client.get("/weighing/material?material=MAT-00")
    assert sum(code.encode() in page.data for code in codes) == 10
    assert b"Search code or description" in page.data
    assert b"Filter by status" in page.data
    assert b"Changing Material will discard unsaved weight input" in page.data
    assert b"focus-visible" in page.data and b"@media (max-width: 991.98px)" in page.data
    assert b"material-list" in page.data and b"overflow-y: auto" in page.data
    assert b"queue-table" not in page.data


def test_local_datetime_formats_naive_and_aware_utc_without_mutation():
    naive = datetime(2026, 8, 17, 9, 30, 39, 853669)
    aware = naive.replace(tzinfo=UTC)
    assert format_local_datetime(naive, "Asia/Bangkok") == "17 Aug 2026 16:30:39 (Thailand Time)"
    assert format_local_datetime(aware, "Asia/Bangkok") == "17 Aug 2026 16:30:39 (Thailand Time)"
    assert naive == datetime(2026, 8, 17, 9, 30, 39, 853669)
