from pathlib import Path

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import AuditLog, Role, Station, User, WeighingTransaction
from app.services.weighing import save_weighing
from tests.test_weighing import MATERIAL_TAG, _login_for_weighing, seed_weighing_data


def _replacement_case(app):
    with app.app_context():
        user, station, order, items = seed_weighing_data()
        order.work_set_station_id = station.id
        order.work_set_active = True
        original = save_weighing(
            order.id, items[0].id, MATERIAL_TAG, "5.125", user.id, station.id
        ).transaction
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
        return {
            "station_id": station.id,
            "order_id": order.id,
            "original_id": original.id,
            "original_preweight": original.preweight_id,
            "replacement_id": replacement.id,
            "replacement_preweight": replacement.preweight_id,
            "user_name": user.display_name,
        }


def test_reweigh_badge_and_visible_provenance_on_order_and_material(app, client):
    case = _replacement_case(app)
    _login_for_weighing(client, case["station_id"])

    order_page = client.get(f"/weighing/order/{case['order_id']}").get_data(as_text=True)
    material_page = client.get("/weighing/material?material=R07047S1").get_data(
        as_text=True
    )
    for page in (order_page, material_page):
        assert "เสร็จสมบูรณ์ / Completed" in page
        assert "ชั่งใหม่ / Reweighed" in page
    for page in (order_page, material_page):
        assert f"แทนที่ / Replaces:</strong> {case['original_preweight']}" in page
        assert "Container was changed for verification." in page
        assert "ชั่งใหม่เมื่อ / Reweighed at" in page
        assert f"ชั่งใหม่โดย / Reweighed by:</strong> {case['user_name']}" in page
        assert "ดูประวัติการชั่ง / View Weighing History" in page


def test_history_is_authorized_station_scoped_newest_first_and_read_only(app, client):
    case = _replacement_case(app)
    url = f"/weighing/transaction/{case['original_id']}/history"
    assert client.get(url).status_code == 302

    with app.app_context():
        wrong_station = Station(code="WRONG-HISTORY", name="Wrong History Station")
        role = Role(code="PRODUCTION", name="Production")
        unauthorized = User(
            username="history-production",
            password_hash=generate_password_hash("History-Production!"),
            display_name="History Production",
            roles=[role],
        )
        db.session.add_all([wrong_station, role, unauthorized])
        db.session.commit()
        wrong_station_id = wrong_station.id

    client.post("/auth/login", data={"username": "weigher", "password": "Weigh-Only!"})
    assert client.get(url).status_code == 302
    client.post("/auth/station", data={"station_id": wrong_station_id})
    assert client.get(url).status_code == 404
    client.post("/auth/logout")
    client.post(
        "/auth/login",
        data={"username": "history-production", "password": "History-Production!"},
    )
    client.post("/auth/station", data={"station_id": case["station_id"]})
    assert client.get(url).status_code == 403
    client.post("/auth/logout")

    _login_for_weighing(client, case["station_id"])
    with app.app_context():
        before_transactions = WeighingTransaction.query.count()
        before_audits = AuditLog.query.count()
    response = client.get(url)
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "ประวัติการชั่ง / Weighing History" in page
    assert page.index(case["replacement_preweight"]) < page.index(
        case["original_preweight"]
    )
    assert "ใช้งานอยู่ / Current" in page
    assert "ยกเลิก / VOID" in page
    replaced_by = (
        "ถูกแทนที่โดย / Replaced by</dt><dd class=\"col-sm-8\">"
        f"{case['replacement_preweight']}"
    )
    assert replaced_by in page
    current_card = page.split(f'data-history-transaction="{case["replacement_id"]}"', 1)[1]
    void_card = page.split(f'data-history-transaction="{case["original_id"]}"', 1)[1]
    assert "พิมพ์ฉลากซ้ำ / Reprint Label" in current_card
    assert "ชั่งใหม่ / Reweigh" in current_card
    assert "พิมพ์ฉลากซ้ำ / Reprint Label" not in void_card
    assert ">ชั่งใหม่ / Reweigh</" not in void_card
    assert client.head(url).status_code == 200
    with app.app_context():
        assert WeighingTransaction.query.count() == before_transactions
        assert AuditLog.query.count() == before_audits


def test_operator_view_has_bounded_responsive_first_viewport_controls():
    template = Path("app/templates/weighing/material.html").read_text(encoding="utf-8")
    queue = Path("app/templates/weighing/_material_queue_table.html").read_text(
        encoding="utf-8"
    )

    assert "grid-template-columns: minmax(17rem, 1fr) minmax(0, 3fr)" in template
    assert "queue-disclosure" in template and "<details" in template
    assert "overflow-x: hidden" in template
    assert "clamp(4.5rem, 5vw, 6rem)" in template
    assert "@media (max-width: 1199.98px)" in template
    assert "@media (max-width: 991.98px)" in template
    assert "@media (max-width: 575.98px)" in template
    assert all(
        token in queue
        for token in (
            "data-scale-connection",
            "data-scale-stability",
            "data-scale-gross",
            "data-scale-tare",
            "data-scale-actual",
            "data-scale-difference",
            "data-scale-percentage",
            "capture-tare",
            "cancel-tare",
            "save-weighing",
        )
    )


def test_operator_state_text_shape_and_color_are_structurally_present():
    template = Path("app/templates/weighing/material.html").read_text(encoding="utf-8")
    script = Path("app/static/weighing_scale_bridge.js").read_text(encoding="utf-8")

    for state in ("UNDER", "ON_TARGET", "OVER", "OVERLOAD"):
        assert state in template or state in script
    for state in ("connected", "disconnected", "stable", "unstable", "stale"):
        assert f'data-state="{state}"' in template or f'"{state}"' in script
    assert '`${connected ? "●" : "✕"}' in script
    assert '`${state.stable ? "●" : "▲"}' in script
