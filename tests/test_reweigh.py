from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import AuditLog, Role, Station, User, WeighingTransaction
from app.services.weighing import save_weighing
from tests.test_weighing import MATERIAL_TAG, _login_for_weighing, seed_weighing_data


def test_successful_reweigh_preserves_original_and_links_replacement(app):
    with app.app_context():
        user, station, order, items = seed_weighing_data()
        original = save_weighing(
            order.id, items[0].id, MATERIAL_TAG, "5.125", user.id, station.id
        ).transaction
        original_id = original.id
        original_preweight = original.preweight_id
        original_weight = original.actual_weight
        result = save_weighing(
            order.id,
            items[0].id,
            MATERIAL_TAG,
            "5.250",
            user.id,
            station.id,
            replaces_transaction_id=original.id,
            reweigh_reason="Container was changed for verification.",
        )

        assert result.success
        replacement = result.transaction
        original = db.session.get(WeighingTransaction, original_id)
        assert replacement.id != original.id
        assert replacement.preweight_id != original_preweight
        assert replacement.replaces_transaction_id == original.id
        assert original.preweight_id == original_preweight
        assert original.actual_weight == original_weight
        assert original.status == "COMPLETED"
        assert original.superseded_by_transaction_id == replacement.id
        assert original.superseded_at_utc is not None
        assert WeighingTransaction.query.count() == 2
        audit = AuditLog.query.filter_by(event_type="WEIGHING_REPLACED").one()
        assert audit.user_id == user.id
        assert audit.station_id == station.id
        assert str(original.id) in audit.detail
        assert str(replacement.id) in audit.detail


def test_duplicate_or_invalid_reweigh_leaves_no_partial_residue(app):
    with app.app_context():
        user, station, order, items = seed_weighing_data()
        original = save_weighing(
            order.id, items[0].id, MATERIAL_TAG, "5.125", user.id, station.id
        ).transaction
        first = save_weighing(
            order.id,
            items[0].id,
            MATERIAL_TAG,
            "5.250",
            user.id,
            station.id,
            replaces_transaction_id=original.id,
            reweigh_reason="First approved replacement weighing.",
        )
        duplicate = save_weighing(
            order.id,
            items[0].id,
            MATERIAL_TAG,
            "5.300",
            user.id,
            station.id,
            replaces_transaction_id=original.id,
            reweigh_reason="Duplicate replacement must be rejected.",
        )
        assert first.success
        assert (duplicate.success, duplicate.code) == (False, "REWEIGH_UNAVAILABLE")
        assert WeighingTransaction.query.count() == 2
        assert AuditLog.query.filter_by(event_type="WEIGHING_REPLACED").count() == 1


def test_database_failure_rolls_back_replacement_and_original_mutations(app, monkeypatch):
    with app.app_context():
        user, station, order, items = seed_weighing_data()
        original = save_weighing(
            order.id, items[0].id, MATERIAL_TAG, "5.125", user.id, station.id
        ).transaction
        original_id = original.id
        original_values = (
            original.preweight_id,
            original.actual_weight,
            original.status,
            original.erp_qr_payload,
        )
        real_flush = db.session.flush

        def fail_after_flush(*args, **kwargs):
            real_flush(*args, **kwargs)
            raise SQLAlchemyError("injected replacement failure")

        monkeypatch.setattr(db.session, "flush", fail_after_flush)
        result = save_weighing(
            order.id,
            items[0].id,
            MATERIAL_TAG,
            "5.250",
            user.id,
            station.id,
            replaces_transaction_id=original.id,
            reweigh_reason="Database failure must fully roll back.",
        )
        assert (result.success, result.code) == (False, "SAVE_FAILED")
        original = db.session.get(WeighingTransaction, original_id)
        assert (
            original.preweight_id,
            original.actual_weight,
            original.status,
            original.erp_qr_payload,
        ) == original_values
        assert original.superseded_at_utc is None
        assert original.superseded_by_transaction_id is None
        assert original.supersede_reason is None
        assert WeighingTransaction.query.count() == 1
        assert AuditLog.query.filter_by(event_type="WEIGHING_REPLACED").count() == 0


def test_reweigh_route_rejects_unauthorized_station_csrf_and_inaccessible_requests(
    app, client
):
    with app.app_context():
        user, station, order, items = seed_weighing_data()
        transaction = save_weighing(
            order.id, items[0].id, MATERIAL_TAG, "5.125", user.id, station.id
        ).transaction
        transaction_id = transaction.id
        order_id = order.id
        station_id = station.id
        wrong_station = Station(code="WRONG-ST", name="Wrong Station")
        unauthorized_role = Role(code="PRODUCTION", name="Production")
        unauthorized_user = User(
            username="production-only",
            password_hash=generate_password_hash("Production-Only!"),
            display_name="Production Only",
            roles=[unauthorized_role],
        )
        db.session.add_all([wrong_station, unauthorized_role, unauthorized_user])
        db.session.commit()
        wrong_station_id = wrong_station.id
    url = f"/weighing/transaction/{transaction_id}/reweigh"
    valid_data = {"reason": "Container was replaced for verification.", "confirm": "y"}

    assert client.post(url, data=valid_data).status_code == 302
    client.post("/auth/login", data={"username": "weigher", "password": "Weigh-Only!"})
    assert client.post(url, data=valid_data).status_code == 302
    client.post("/auth/station", data={"station_id": wrong_station_id})
    assert client.post(url, data=valid_data).status_code == 404
    client.post("/auth/logout")
    client.post(
        "/auth/login",
        data={"username": "production-only", "password": "Production-Only!"},
    )
    client.post("/auth/station", data={"station_id": station_id})
    assert client.post(url, data=valid_data).status_code == 403
    client.post("/auth/logout")
    _login_for_weighing(client, station_id)
    assert client.post("/weighing/transaction/999999/reweigh", data=valid_data).status_code == 404

    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post(url, data=valid_data).status_code == 400
    invalid_csrf = {**valid_data, "csrf_token": "invalid-token"}
    assert client.post(url, data=invalid_csrf).status_code == 400
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        assert WeighingTransaction.query.count() == 1
        assert AuditLog.query.filter_by(event_type="WEIGHING_REPLACED").count() == 0
        unchanged = db.session.get(WeighingTransaction, transaction_id)
        assert unchanged.superseded_by_transaction_id is None

    page = client.get(f"/weighing/order/{order_id}").get_data(as_text=True)
    assert "ชั่งใหม่ / Reweigh" in page
    assert "เหตุผลในการชั่งใหม่ / Reweigh reason" in page

    rejected = client.post(
        f"/weighing/transaction/{transaction_id}/reweigh",
        data={"reason": "too short"},
        follow_redirects=True,
    )
    assert rejected.status_code == 200
    with client.session_transaction() as session:
        assert "reweigh_original_transaction_id" not in session

    accepted = client.post(
        f"/weighing/transaction/{transaction_id}/reweigh",
        data={"reason": "Container was replaced for verification.", "confirm": "y"},
    )
    assert accepted.status_code == 302
    with client.session_transaction() as session:
        assert session["reweigh_original_transaction_id"] == transaction_id
        first_attempt = session["reweigh_workflow_attempt"]
    repeated = client.post(url, data=valid_data)
    assert repeated.status_code == 302
    with client.session_transaction() as session:
        assert session["reweigh_workflow_attempt"] != first_attempt
    cancelled = client.post("/weighing/reweigh/cancel")
    assert cancelled.status_code == 302
    with client.session_transaction() as session:
        assert "reweigh_original_transaction_id" not in session
        assert "reweigh_reason" not in session
        assert "reweigh_workflow_attempt" not in session
    with app.app_context():
        assert WeighingTransaction.query.count() == 1
        assert AuditLog.query.filter_by(event_type="WEIGHING_REPLACED").count() == 0


def test_superseded_transaction_cannot_start_another_reweigh(app, client):
    with app.app_context():
        user, station, order, items = seed_weighing_data()
        original = save_weighing(
            order.id, items[0].id, MATERIAL_TAG, "5.125", user.id, station.id
        ).transaction
        original_id = original.id
        save_weighing(
            order.id,
            items[0].id,
            MATERIAL_TAG,
            "5.250",
            user.id,
            station.id,
            replaces_transaction_id=original.id,
            reweigh_reason="First approved replacement weighing.",
        )
        station_id = station.id
    _login_for_weighing(client, station_id)
    response = client.post(
        f"/weighing/transaction/{original_id}/reweigh",
        data={"reason": "Duplicate replacement must be rejected.", "confirm": "y"},
    )
    assert response.status_code == 409
    with app.app_context():
        assert WeighingTransaction.query.count() == 2
        assert AuditLog.query.filter_by(event_type="WEIGHING_REPLACED").count() == 1


def test_superseded_label_is_void_and_not_reprintable(app, client):
    with app.app_context():
        user, station, order, items = seed_weighing_data()
        original = save_weighing(
            order.id, items[0].id, MATERIAL_TAG, "5.125", user.id, station.id
        ).transaction
        original_id = original.id
        replacement = save_weighing(
            order.id,
            items[0].id,
            MATERIAL_TAG,
            "5.250",
            user.id,
            station.id,
            replaces_transaction_id=original.id,
            reweigh_reason="Container was changed for verification.",
        ).transaction
        replacement_id = replacement.id
        station_id = station.id
    _login_for_weighing(client, station_id)

    old_label = client.get(f"/weighing/transaction/{original_id}/sticker")
    current_label = client.get(f"/weighing/transaction/{replacement_id}/sticker")
    assert "ยกเลิก / VOID" in old_label.get_data(as_text=True)
    assert 'onclick="window.print()"' not in old_label.get_data(as_text=True)
    assert "ลำดับการชั่งทดแทน / Replacement chain" in old_label.get_data(as_text=True)
    assert 'onclick="window.print()"' in current_label.get_data(as_text=True)


def test_scale_ui_has_cancel_tare_and_decimal_safe_deviation_logic():
    script = Path("app/static/weighing_scale_bridge.js").read_text(encoding="utf-8")
    template = Path("app/templates/weighing/_material_queue_table.html").read_text(
        encoding="utf-8"
    )
    assert 'bridgeRequest("/tare/clear", {method: "POST"' in script
    assert "BigInt" in script
    assert "data-scale-difference" in template
    assert "data-scale-percentage" in template
    assert "ยกเลิกน้ำหนักภาชนะ" not in template
    assert "Cancel Tare" in template
    assert ".write(" not in Path("scale_bridge/serial_source.py").read_text(encoding="utf-8")
