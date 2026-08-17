from app.extensions import db
from app.models import AuditLog, ProductionOrder, Role, WeighingTransaction
from app.services.material_workflow import save_material_queue_item
from app.services.workset import complete_work_set
from tests.test_material_workflow import (
    MATERIAL_A_TAG,
    MATERIAL_B_TAG,
    login,
    prepare_orders,
    seed_material_workflow,
)


def complete_required_weighings(user, station, orders, items_a, items_b):
    for order, item in zip(orders, items_a, strict=True):
        assert save_material_queue_item(
            station.id, order.id, item.id, MATERIAL_A_TAG, item.target_weight, user.id
        ).success
    for order, item in zip(orders, items_b, strict=True):
        assert save_material_queue_item(
            station.id, order.id, item.id, MATERIAL_B_TAG, item.target_weight, user.id
        ).success


def completion_fixture(order_count=2):
    user, station, other_station, _, _, orders, items_a, items_b = (
        seed_material_workflow(order_count)
    )
    prepare_orders(user, station, orders)
    session_code = orders[0].work_set_code
    return user, station, other_station, orders, items_a, items_b, session_code


def transaction_snapshot():
    return [
        (
            transaction.id,
            transaction.preweight_id,
            transaction.actual_weight,
            transaction.material_tag_raw_payload,
            transaction.erp_qr_payload,
        )
        for transaction in WeighingTransaction.query.order_by(WeighingTransaction.id)
    ]


def test_incomplete_session_cannot_be_completed_from_form_claim(app):
    with app.app_context():
        user, station, _, orders, _, _, session_code = completion_fixture()

        result = complete_work_set(session_code, user.id, station.id)

        assert (result.success, result.code) == (False, "SESSION_INCOMPLETE")
        assert all(order.status == "READY" and order.work_set_active for order in orders)
        assert AuditLog.query.filter_by(event_type="WEIGHING_SESSION_COMPLETED").count() == 0


def test_complete_session_is_transactional_audited_and_idempotent(app):
    with app.app_context():
        user, station, _, orders, items_a, items_b, session_code = completion_fixture()
        complete_required_weighings(user, station, orders, items_a, items_b)
        before = transaction_snapshot()

        first = complete_work_set(session_code, user.id, station.id)
        second = complete_work_set(session_code, user.id, station.id)

        assert (first.success, first.code) == (True, "SESSION_COMPLETED")
        assert (second.success, second.code) == (True, "ALREADY_COMPLETED")
        refreshed = ProductionOrder.query.order_by(ProductionOrder.id).all()
        assert all(order.status == "COMPLETED" for order in refreshed)
        assert all(not order.work_set_active for order in refreshed)
        assert transaction_snapshot() == before
        audits = AuditLog.query.filter_by(event_type="WEIGHING_SESSION_COMPLETED").all()
        assert len(audits) == 1
        assert audits[0].entity_id == session_code
        assert audits[0].user_id == user.id
        assert audits[0].station_id == station.id
        assert audits[0].occurred_at_utc is not None
        assert "completed_weighings=4" in audits[0].detail


def test_other_station_and_invalid_session_cannot_be_completed(app):
    with app.app_context():
        user, station, other_station, orders, items_a, items_b, session_code = (
            completion_fixture()
        )
        complete_required_weighings(user, station, orders, items_a, items_b)

        other_station_result = complete_work_set(
            session_code, user.id, other_station.id
        )
        orders[0].status = "CANCELLED"
        db.session.commit()
        invalid_result = complete_work_set(session_code, user.id, station.id)

        assert other_station_result.code == "SESSION_UNAVAILABLE"
        assert invalid_result.code == "SESSION_INVALID"
        assert AuditLog.query.filter_by(event_type="WEIGHING_SESSION_COMPLETED").count() == 0


def test_complete_route_requires_post_csrf_and_authorized_role(app, client):
    with app.app_context():
        user, station, _, orders, items_a, items_b, session_code = completion_fixture(1)
        complete_required_weighings(user, station, orders, items_a, items_b)
        user_id = user.id
        station_id = station.id
    login(client, station_id)

    assert client.get(f"/preparation/session/{session_code}/complete").status_code == 405
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post(f"/preparation/session/{session_code}/complete").status_code == 400
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        user = db.session.get(type(user), user_id)
        production_role = Role(code="PRODUCTION", name="Production")
        user.roles = [production_role]
        db.session.add(production_role)
        db.session.commit()
    assert client.post(f"/preparation/session/{session_code}/complete").status_code == 403


def test_complete_pages_replace_scan_loop_and_render_read_only_summary(app, client):
    with app.app_context():
        user, station, _, orders, items_a, items_b, session_code = completion_fixture()
        complete_required_weighings(user, station, orders, items_a, items_b)
        station_id = station.id
    login(client, station_id)

    weighing = client.get("/weighing/material")
    preparation = client.get("/preparation/")

    for response in (weighing, preparation):
        assert b"All required weighings are complete" in response.data
        assert b"Complete Weighing Session" in response.data
        assert session_code.encode() in response.data
        assert b"Confirm and Complete Session" in response.data
        assert b'aria-current="step"' in response.data
    assert b"Material Tag QR" not in weighing.data
    assert b"Actual Weight" not in weighing.data
    assert b"Scan Production Order + Formula Sheet" not in preparation.data
    assert b"Cancel This Weighing Session" not in preparation.data
    assert b"Continue to Material Weighing" not in preparation.data

    completed = client.post(
        f"/preparation/session/{session_code}/complete", follow_redirects=True
    )

    assert completed.status_code == 200
    assert b"Weighing Session Complete" in completed.data
    assert b"This session is finalized and read-only." in completed.data
    assert session_code.encode() in completed.data
    assert b"COMPLETED" in completed.data
    assert b"2 / 4" not in completed.data
    assert b"4 / 4" in completed.data
    assert b"PD001" in completed.data and b"PD002" in completed.data
    assert b"Return Home" in completed.data
    assert b"Thailand Time" in completed.data
    assert b"Cancel This Weighing Session" not in completed.data
    assert b"Actual Weight" not in completed.data


def test_completed_session_blocks_old_po_scan_material_and_cancel(app, client):
    with app.app_context():
        user, station, _, orders, items_a, items_b, session_code = completion_fixture(1)
        complete_required_weighings(user, station, orders, items_a, items_b)
        assert complete_work_set(session_code, user.id, station.id).success
        before = transaction_snapshot()
        station_id = station.id
        order_id = orders[0].id
        item_id = items_a[0].id
    login(client, station_id)

    prepare = client.post(
        "/preparation/", data={"po_no": "PD001", "formula_code": "FM-01"}
    )
    scan = client.post("/weighing/material/validate", json={"material_tag": MATERIAL_A_TAG})
    with client.session_transaction() as browser_session:
        browser_session["active_material_tag"] = MATERIAL_A_TAG
    save = client.post(
        f"/weighing/material/order/{order_id}/line/{item_id}",
        data={"actual_weight": "999.000"},
        follow_redirects=True,
    )
    cancel = client.post("/preparation/work-set/close", follow_redirects=True)

    assert b"Completed Production Order cannot start" in prepare.data
    assert scan.get_json()["result"] == "UN-MATCH"
    assert b"Scan and validate a Material Tag before weighing" in save.data
    assert b"No active weighing session is available" in cancel.data
    with app.app_context():
        assert transaction_snapshot() == before
        order = ProductionOrder.query.filter_by(po_no="PD001").one()
        assert order.status == "COMPLETED"
        assert order.work_set_active is False


def test_session_with_weighing_records_cannot_be_cancelled(app, client):
    with app.app_context():
        user, station, _, orders, items_a, _, _ = completion_fixture(1)
        result = save_material_queue_item(
            station.id,
            orders[0].id,
            items_a[0].id,
            MATERIAL_A_TAG,
            items_a[0].target_weight,
            user.id,
        )
        assert result.success
        station_id = station.id
    login(client, station_id)

    response = client.post("/preparation/work-set/close", follow_redirects=True)

    assert b"cannot be cancelled because weighing records already exist" in response.data
    with app.app_context():
        order = ProductionOrder.query.filter_by(po_no="PD001").one()
        assert order.status == "READY"
        assert order.work_set_active is True
        assert WeighingTransaction.query.count() == 1


def test_end_final_material_guides_operator_to_completion(app, client):
    with app.app_context():
        user, station, _, orders, items_a, items_b, _ = completion_fixture(1)
        complete_required_weighings(user, station, orders, items_a, items_b)
        station_id = station.id
    login(client, station_id)

    response = client.post("/weighing/material/end", follow_redirects=True)

    assert b"All required weighings are complete" in response.data
    assert b"Complete this weighing session" in response.data
    assert b"Material session ended. Scan the next Material Tag." not in response.data
    assert b"Material Tag QR" not in response.data
