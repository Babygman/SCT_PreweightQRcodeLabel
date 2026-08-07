from decimal import Decimal

from sqlalchemy import true
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    Formula,
    FormulaItem,
    Material,
    Product,
    ProductionOrder,
    Role,
    Station,
    User,
    WeighingTransaction,
)
from app.services.material_workflow import build_material_queue, save_material_queue_item
from app.services.station_capability import station_can_weigh_material
from app.services.workset import prepare_work_set_order

MATERIAL_A_TAG = "07/08/2026|PC-A|10|MAT-A|INV-A|LOT-A|SUP|UAT|MAT|1|1"
MATERIAL_B_TAG = "07/08/2026|PC-B|10|MAT-B|INV-B|LOT-B|SUP|UAT|MAT|1|1"


def seed_material_workflow(order_count=6):
    role = Role(code="OPERATOR", name="Operator")
    user = User(
        username="material_operator",
        password_hash=generate_password_hash("Material-Only!"),
        display_name="Material Operator",
        roles=[role],
    )
    station = Station(
        code="POWDER-ST",
        name="Powder and Liquid Station",
        material_classifications="POWDER,LIQUID",
    )
    unauthorized_station = Station(
        code="OTHER-ST", name="Other Station", material_classifications="OTHER"
    )
    material_a = Material(code="MAT-A", name="Material A", unit="kg", classification="POWDER")
    material_b = Material(code="MAT-B", name="Material B", unit="kg", classification="LIQUID")
    orders = []
    items_a = []
    items_b = []
    for number in range(1, order_count + 1):
        product = Product(code=f"FG-{number:02d}", name=f"Product {number:02d}")
        formula = Formula(code=f"FM-{number:02d}", name=f"Formula {number:02d}", product=product)
        item_a = FormulaItem(
            formula=formula,
            line_no=10,
            material=material_a,
            target_weight=Decimal("2.000" if number == 2 else "1.000"),
            unit="kg",
        )
        item_b = FormulaItem(
            formula=formula,
            line_no=20,
            material=material_b,
            target_weight=Decimal("0.500"),
            unit="kg",
        )
        order = ProductionOrder(
            po_no=f"PD{number:03d}",
            product=product,
            production_lot=f"LOT-{number:03d}",
            formula=formula,
            status="OPEN",
        )
        orders.append(order)
        items_a.append(item_a)
        items_b.append(item_b)
        db.session.add_all([product, formula, item_a, item_b, order])
    db.session.add_all([role, user, station, unauthorized_station, material_a, material_b])
    db.session.commit()
    return user, station, unauthorized_station, material_a, material_b, orders, items_a, items_b


def prepare_orders(user, station, orders):
    results = [
        prepare_work_set_order(order.po_no, order.formula.code, user.id, station.id)
        for order in orders
    ]
    assert all(result.success for result in results)


def login(client, station_id):
    client.post(
        "/auth/login",
        data={"username": "material_operator", "password": "Material-Only!"},
    )
    client.post("/auth/station", data={"station_id": station_id})


def test_station_permits_authorized_material_and_rejects_unauthorized(app):
    with app.app_context():
        _, station, unauthorized, material_a, _, _, _, _ = seed_material_workflow(1)
        assert station_can_weigh_material(station.id, material_a) is True
        assert station_can_weigh_material(unauthorized.id, material_a) is False


def test_multiple_pairs_prepare_and_duplicate_is_rejected(app):
    with app.app_context():
        user, station, _, _, _, orders, _, _ = seed_material_workflow(2)
        first = prepare_work_set_order("PD001", "FM-01", user.id, station.id)
        second = prepare_work_set_order("PD002", "FM-02", user.id, station.id)
        duplicate = prepare_work_set_order("PD001", "FM-01", user.id, station.id)
        mismatch = prepare_work_set_order("PD002", "FM-01", user.id, station.id)
        assert first.success and second.success
        assert (duplicate.success, duplicate.code) == (False, "DUPLICATE_PREPARATION")
        assert (mismatch.success, mismatch.code) == (False, "WRONG_FORMULA")
        assert all(order.work_set_active for order in orders)


def test_one_material_tag_builds_six_order_queue(app):
    with app.app_context():
        user, station, _, _, _, orders, _, _ = seed_material_workflow()
        prepare_orders(user, station, orders)
        queue = build_material_queue(station.id, MATERIAL_A_TAG)
        assert queue.success is True
        assert queue.code == "MATCH"
        assert [item.production_order.po_no for item in queue.items] == [
            "PD001",
            "PD002",
            "PD003",
            "PD004",
            "PD005",
            "PD006",
        ]
        assert queue.pending_count == 6


def test_material_queue_rejects_wrong_material_and_unauthorized_station(app):
    with app.app_context():
        user, station, unauthorized, _, _, orders, items_a, _ = seed_material_workflow(1)
        prepare_orders(user, station, orders)
        wrong_material = build_material_queue(station.id, "invalid")
        unauthorized_queue = build_material_queue(unauthorized.id, MATERIAL_A_TAG)
        bypass = save_material_queue_item(
            unauthorized.id,
            orders[0].id,
            items_a[0].id,
            MATERIAL_A_TAG,
            "1.000",
            user.id,
        )
        assert wrong_material.code == "INVALID_MATERIAL_TAG"
        assert unauthorized_queue.code == "STATION_NOT_AUTHORIZED"
        assert bypass.code == "STATION_NOT_AUTHORIZED"
        assert WeighingTransaction.query.count() == 0


def test_same_tag_completes_six_orders_without_rescan_and_then_material_b_queues(app):
    with app.app_context():
        user, station, _, _, _, orders, items_a, _ = seed_material_workflow()
        prepare_orders(user, station, orders)
        preweight_ids = []
        for order, item in zip(orders, items_a, strict=True):
            result = save_material_queue_item(
                station.id, order.id, item.id, MATERIAL_A_TAG, item.target_weight, user.id
            )
            assert result.success is True
            assert result.transaction.material_tag_raw_payload == MATERIAL_A_TAG
            preweight_ids.append(result.transaction.preweight_id)
        assert len(set(preweight_ids)) == 6
        assert WeighingTransaction.query.count() == 6
        completed = build_material_queue(station.id, MATERIAL_A_TAG, require_pending=False)
        assert completed.completed_count == 6
        assert completed.pending_count == 0
        material_b = build_material_queue(station.id, MATERIAL_B_TAG)
        assert material_b.success is True
        assert material_b.pending_count == 6


def test_duplicate_double_save_creates_only_one_transaction(app):
    with app.app_context():
        user, station, _, _, _, orders, items_a, _ = seed_material_workflow(1)
        prepare_orders(user, station, orders)
        first = save_material_queue_item(
            station.id, orders[0].id, items_a[0].id, MATERIAL_A_TAG, "1.000", user.id
        )
        second = save_material_queue_item(
            station.id, orders[0].id, items_a[0].id, MATERIAL_A_TAG, "1.100", user.id
        )
        assert first.success is True
        assert second.code == "FORMULA_LINE_ALREADY_WEIGHED"
        assert WeighingTransaction.query.count() == 1


def test_material_mode_ui_gates_weight_and_keeps_active_tag_in_session(app, client):
    with app.app_context():
        user, station, _, _, _, orders, _, _ = seed_material_workflow(2)
        prepare_orders(user, station, orders)
        station_id = station.id
    login(client, station_id)
    before = client.get("/weighing/material")
    assert before.status_code == 200
    assert b"Material-centric Weighing" in before.data
    assert (
        b"Scan a material and record its weight for the prepared Production Orders."
        in before.data
    )
    assert b"2. Weigh Materials" in before.data
    assert b'aria-current="step"' in before.data
    assert b"Production Orders for This Weighing Session" in before.data
    assert b"2 Production Order(s)" in before.data
    assert b"PD001" in before.data and b"PD002" in before.data
    assert b"FG-01" in before.data and b"LOT-001" in before.data
    assert b"FM-01" in before.data
    assert b"Overall progress 0 / 4" in before.data
    assert b"Materials to Weigh" in before.data
    assert b"MAT-A" in before.data and b"Material A" in before.data
    assert b"0 / 2" in before.data
    assert b"Ready to scan" in before.data
    assert b"Scan the QR code on the physical material container." in before.data
    assert b"Back to Production Order Preparation" in before.data
    assert b"PRIMARY" not in before.data
    assert b"Active Work Set" not in before.data
    assert b"Actual Weight" in before.data
    assert b"disabled" in before.data
    with app.app_context():
        assert WeighingTransaction.query.count() == 0
        statuses = db.session.scalars(
            db.select(ProductionOrder.status).where(
                ProductionOrder.po_no.in_(("PD001", "PD002"))
            )
        ).all()
        assert statuses == ["READY", "READY"]

    match = client.post("/weighing/material/validate", json={"material_tag": MATERIAL_A_TAG})
    assert match.get_json()["result"] == "MATCH"
    assert match.get_json()["queue_count"] == 2
    queue = client.get("/weighing/material")
    assert b"0 / 2 Production Order requirement(s) completed" in queue.data
    assert b"PD001" in queue.data and b"PD002" in queue.data


def test_continuous_preparation_keeps_prior_orders_and_failed_values(app, client):
    with app.app_context():
        _, station, _, _, _, orders, _, _ = seed_material_workflow(2)
        station_id = station.id
    login(client, station_id)

    first = client.post(
        "/preparation/", data={"po_no": "PD001", "formula_code": "FM-01"}
    )
    second = client.post(
        "/preparation/", data={"po_no": "PD002", "formula_code": "FM-02"}
    )
    failed = client.post(
        "/preparation/", data={"po_no": "PD999", "formula_code": "FM-99"}
    )

    assert b'value="PD001"' not in first.data
    assert b'document.getElementById("po_no").focus()' in first.data
    assert b"PD001" in second.data and b"PD002" in second.data
    assert b'value="PD002"' not in second.data
    assert b'value="PD999"' in failed.data and b'value="FM-99"' in failed.data
    assert b"PD001" in failed.data and b"PD002" in failed.data
    with app.app_context():
        active_count = db.session.scalar(
            db.select(db.func.count())
            .select_from(ProductionOrder)
            .where(ProductionOrder.work_set_active == true())
        )
        assert active_count == 2
        assert WeighingTransaction.query.count() == 0


def test_formula_centric_mode_remains_available(app, client):
    with app.app_context():
        _, station, _, _, _, orders, _, _ = seed_material_workflow(1)
        order = orders[0]
        order.status = "READY"
        db.session.commit()
        station_id = station.id
        order_id = order.id
    login(client, station_id)
    response = client.get(f"/weighing/order/{order_id}")
    assert response.status_code == 200
    assert b"Weighing" in response.data
