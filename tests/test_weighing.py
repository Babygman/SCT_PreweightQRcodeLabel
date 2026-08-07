import json
from datetime import date
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    AuditLog,
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
from app.services.weighing import (
    MaterialTagError,
    parse_material_tag,
    save_weighing,
    validate_material_tag,
)

MATERIAL_TAG = "05/08/2026|PC26/07-0137|10|R07047S1|1370009994|0508-P12675|5250|06|MAT|1|1"


def seed_weighing_data():
    role = Role(code="OPERATOR", name="Operator")
    user = User(
        username="weigher",
        password_hash=generate_password_hash("Weigh-Only!"),
        display_name="Weighing User",
        roles=[role],
    )
    station = Station(code="WEIGH-ST", name="Weighing Station")
    product = Product(code="FG-W", name="Weighing Product")
    material = Material(code="R07047S1", name="Required Material", unit="kg")
    other_material = Material(code="OTHER-MAT", name="Other Material", unit="kg")
    formula = Formula(code="FM-W", name="Weighing Formula", product=product)
    items = [
        FormulaItem(
            formula=formula,
            line_no=10,
            material=material,
            target_weight=Decimal("5.000"),
            unit="kg",
        ),
        FormulaItem(
            formula=formula,
            line_no=20,
            material=material,
            target_weight=Decimal("3.000"),
            unit="kg",
        ),
        FormulaItem(
            formula=formula,
            line_no=30,
            material=other_material,
            target_weight=Decimal("2.000"),
            unit="kg",
        ),
    ]
    order = ProductionOrder(
        po_no="PO-WEIGH",
        product=product,
        production_lot="LOT-W",
        formula=formula,
        status="READY",
        prepared_by_user_id=None,
    )
    db.session.add_all(
        [role, user, station, product, material, other_material, formula, *items, order]
    )
    db.session.commit()
    return user, station, order, items


def test_valid_material_tag_parses_all_11_fields():
    tag = parse_material_tag(MATERIAL_TAG)
    assert tag.receiving_date.date() == date(2026, 8, 5)
    assert tag.purchase_order == "PC26/07-0137"
    assert tag.purchase_order_line == "10"
    assert tag.material_code == "R07047S1"
    assert tag.delivery_invoice == "1370009994"
    assert tag.vendor_lot == "0508-P12675"
    assert tag.supplier == "5250"
    assert tag.comment == "06"
    assert tag.warehouse == "MAT"
    assert tag.location == "1"
    assert tag.shelf == "1"


@pytest.mark.parametrize(
    "payload",
    [
        "too|few|fields",
        "05/08/2026|PC|10|MAT|INV|LOT|SUP|COMMENT|WH|LOC|SHELF|EXTRA",
        "2026-08-05|PC|10|MAT|INV|LOT|SUP|COMMENT|WH|LOC|SHELF",
    ],
)
def test_invalid_material_tag_is_rejected(payload):
    with pytest.raises(MaterialTagError):
        parse_material_tag(payload)


def test_successful_weighing_stores_completed_transaction_and_traceability(app):
    with app.app_context():
        user, station, order, items = seed_weighing_data()
        result = save_weighing(order.id, items[0].id, MATERIAL_TAG, "5.125", user.id, station.id)
        assert result.success is True
        assert result.code == "COMPLETED"
        transaction = db.session.get(WeighingTransaction, result.transaction.id)
        assert transaction.status == "COMPLETED"
        assert transaction.preweight_id.startswith("PW-")
        assert transaction.preweight_id.endswith("-000001")
        assert transaction.raw_material_lot_id is None
        assert transaction.actual_weight == Decimal("5.125")
        assert transaction.target_weight_snapshot == Decimal("5.000")
        assert transaction.material_tag_raw_payload == MATERIAL_TAG
        assert transaction.receiving_date_snapshot == date(2026, 8, 5)
        assert transaction.purchase_order_snapshot == "PC26/07-0137"
        assert transaction.purchase_order_line_snapshot == "10"
        assert transaction.material_code_snapshot == "R07047S1"
        assert transaction.delivery_invoice_snapshot == "1370009994"
        assert transaction.vendor_lot_snapshot == "0508-P12675"
        assert transaction.supplier_snapshot == "5250"
        assert transaction.comment_snapshot == "06"
        assert transaction.warehouse_snapshot == "MAT"
        assert transaction.location_snapshot == "1"
        assert transaction.shelf_snapshot == "1"
        payload = json.loads(transaction.erp_qr_payload)
        assert payload == {
            "type": "SCT_PREWEIGHT",
            "version": 1,
            "preweight_id": transaction.preweight_id,
            "production_order": "PO-WEIGH",
            "production_lot": "LOT-W",
            "formula_sheet": "FM-W",
            "item_code": "R07047S1",
            "item_name": "Required Material",
            "actual_weight": "5.125",
            "unit": "kg",
        }


def test_wrong_material_is_blocked_and_audited(app):
    with app.app_context():
        user, station, order, items = seed_weighing_data()
        result = save_weighing(order.id, items[2].id, MATERIAL_TAG, "2.000", user.id, station.id)
        assert (result.success, result.code) == (False, "WRONG_MATERIAL")
        assert WeighingTransaction.query.count() == 0
        audit = AuditLog.query.filter_by(event_type="WEIGHING_MATERIAL_MISMATCH").one()
        assert "expected=OTHER-MAT" in audit.detail
        assert "scanned=R07047S1" in audit.detail


@pytest.mark.parametrize("weight", ["0", "-1", "0.0004", "not-a-number"])
def test_non_positive_or_non_numeric_actual_weight_is_rejected(app, weight):
    with app.app_context():
        user, station, order, items = seed_weighing_data()
        result = save_weighing(order.id, items[0].id, MATERIAL_TAG, weight, user.id, station.id)
        assert (result.success, result.code) == (False, "INVALID_WEIGHT")
        assert WeighingTransaction.query.count() == 0


def test_duplicate_formula_line_weighing_is_blocked(app):
    with app.app_context():
        user, station, order, items = seed_weighing_data()
        first = save_weighing(order.id, items[0].id, MATERIAL_TAG, "5.000", user.id, station.id)
        second = save_weighing(order.id, items[0].id, MATERIAL_TAG, "5.100", user.id, station.id)
        assert first.success is True
        assert (second.success, second.code) == (False, "FORMULA_LINE_ALREADY_WEIGHED")
        assert WeighingTransaction.query.count() == 1


def test_same_material_tag_can_be_reused_for_another_formula_line(app):
    with app.app_context():
        user, station, order, items = seed_weighing_data()
        first = save_weighing(order.id, items[0].id, MATERIAL_TAG, "5.000", user.id, station.id)
        second = save_weighing(order.id, items[1].id, MATERIAL_TAG, "3.000", user.id, station.id)
        assert first.success and second.success
        assert (
            first.transaction.material_tag_raw_payload
            == second.transaction.material_tag_raw_payload
        )
        assert first.transaction.preweight_id.endswith("-000001")
        assert second.transaction.preweight_id.endswith("-000002")
        assert WeighingTransaction.query.count() == 2


def test_vendor_lot_does_not_require_master_record(app):
    with app.app_context():
        user, station, order, items = seed_weighing_data()
        result = save_weighing(order.id, items[0].id, MATERIAL_TAG, "5.000", user.id, station.id)
        assert result.success is True
        assert result.transaction.vendor_lot_snapshot == "0508-P12675"
        assert result.transaction.raw_material_lot_id is None


def test_weighing_page_saves_line_and_displays_preweight_id(app, client):
    with app.app_context():
        _, station, order, items = seed_weighing_data()
        station_id = station.id
        order_id = order.id
        item_id = items[0].id
    client.post("/auth/login", data={"username": "weigher", "password": "Weigh-Only!"})
    client.post("/auth/station", data={"station_id": station_id})
    response = client.post(
        f"/weighing/order/{order_id}/line/{item_id}",
        data={"material_tag": MATERIAL_TAG, "actual_weight": "5.125"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Weighing completed as PW-" in response.data
    assert b"COMPLETED" in response.data
    assert b"SCT PREWEIGHT" in response.data
    assert b"window.print()" in response.data


def _login_for_weighing(client, station_id):
    client.post("/auth/login", data={"username": "weigher", "password": "Weigh-Only!"})
    client.post("/auth/station", data={"station_id": station_id})


def test_actual_weight_and_save_are_disabled_before_material_validation(app, client):
    with app.app_context():
        _, station, order, items = seed_weighing_data()
        station_id = station.id
        order_id = order.id
        item_id = items[0].id
    _login_for_weighing(client, station_id)
    response = client.get(f"/weighing/order/{order_id}")
    assert response.status_code == 200
    assert f'id="actual-weight-{item_id}"'.encode() in response.data
    assert b'name="actual_weight" type="number"' in response.data
    assert b'required disabled' in response.data
    assert b'class="btn btn-primary btn-sm save-weighing" type="submit" disabled' in response.data


def test_immediate_material_validation_returns_match_and_unmatch(app, client):
    with app.app_context():
        _, station, order, items = seed_weighing_data()
        station_id = station.id
        order_id = order.id
        correct_item_id = items[0].id
        wrong_item_id = items[2].id
    _login_for_weighing(client, station_id)

    match = client.post(
        f"/weighing/order/{order_id}/line/{correct_item_id}/validate-material",
        json={"material_tag": MATERIAL_TAG},
    )
    assert match.status_code == 200
    assert match.get_json() == {
        "result": "MATCH",
        "code": "MATCH",
        "message": "MATCH — R07047S1",
    }

    unmatch = client.post(
        f"/weighing/order/{order_id}/line/{wrong_item_id}/validate-material",
        json={"material_tag": MATERIAL_TAG},
    )
    assert unmatch.status_code == 200
    assert unmatch.get_json()["result"] == "UN-MATCH"
    assert unmatch.get_json()["code"] == "WRONG_MATERIAL"
    with app.app_context():
        assert WeighingTransaction.query.count() == 0


def test_save_revalidates_material_when_client_validation_is_bypassed(app, client):
    with app.app_context():
        _, station, order, items = seed_weighing_data()
        station_id = station.id
        order_id = order.id
        wrong_item_id = items[2].id
    _login_for_weighing(client, station_id)
    response = client.post(
        f"/weighing/order/{order_id}/line/{wrong_item_id}",
        data={"material_tag": MATERIAL_TAG, "actual_weight": "2.000"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Wrong Material" in response.data
    with app.app_context():
        assert WeighingTransaction.query.count() == 0


def test_validation_service_rejects_invalid_tag_without_database_write(app):
    with app.app_context():
        _, _, order, items = seed_weighing_data()
        result = validate_material_tag(order.id, items[0].id, "invalid")
        assert (result.success, result.code) == (False, "INVALID_MATERIAL_TAG")
        assert WeighingTransaction.query.count() == 0
        assert AuditLog.query.count() == 0


def test_sticker_and_reprint_use_the_stored_immutable_payload(app, client):
    with app.app_context():
        _, station, order, items = seed_weighing_data()
        result = save_weighing(
            order.id, items[0].id, MATERIAL_TAG, "5.125", 1, station.id
        )
        transaction_id = result.transaction.id
        original_payload = result.transaction.erp_qr_payload
        items[0].material.name = "Changed Master Name"
        db.session.commit()
        station_id = station.id
    _login_for_weighing(client, station_id)

    sticker = client.get(f"/weighing/transaction/{transaction_id}/sticker")
    first_qr = client.get(f"/weighing/transaction/{transaction_id}/qr.png")
    reprint_qr = client.get(f"/weighing/transaction/{transaction_id}/qr.png")

    assert sticker.status_code == 200
    for expected in (
        b"PO-WEIGH",
        b"LOT-W",
        b"FM-W",
        b"R07047S1",
        b"Required Material",
        b"5.125 kg",
        b"Reprint",
        b"window.print()",
    ):
        assert expected in sticker.data
    assert b"Changed Master Name" not in sticker.data
    assert first_qr.status_code == 200
    assert first_qr.mimetype == "image/png"
    assert first_qr.data == reprint_qr.data
    with app.app_context():
        transaction = db.session.get(WeighingTransaction, transaction_id)
        assert transaction.erp_qr_payload == original_payload
