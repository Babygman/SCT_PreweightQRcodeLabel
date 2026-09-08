from datetime import date, datetime, timedelta
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
    ProductionOrderProductSnapshot,
    Role,
    Station,
    User,
)
from app.services.mock_erp import create_mock_order

pytestmark = pytest.mark.usefixtures("approved_materials")


def identity(role_code):
    role = Role(code=role_code, name=role_code)
    user = User(
        username=f"history-{role_code.lower()}",
        password_hash=generate_password_hash("test"),
        display_name="History User",
        roles=[role],
    )
    station = Station(code=f"H-{role_code}", name="History Station")
    db.session.add_all([role, user, station])
    db.session.commit()
    return user.id, station.id


def authenticate(client, user_id, station_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
        session["station_id"] = station_id


def direct_order(number, product, material, *, origin="MOCK_ERP"):
    formula = Formula(
        code=f"HIST-FM-{number:02d}", name="History Formula", product=product,
        production_lot=f"HIST-LOT-{number:02d}", batch_quantity=Decimal("1.000"),
    )
    formula.items.append(
        FormulaItem(line_no=10, material=material, target_weight=Decimal("1.000"), unit="kg")
    )
    order = ProductionOrder(
        po_no=f"HIST-PO-{number:02d}", product=product,
        production_lot=f"HIST-LOT-{number:02d}", formula=formula, status="OPEN",
        quantity=Decimal("1.000"), production_date=date(2026, 9, min(number, 28)),
        expected_finish_date=date(2026, 9, min(number, 28)), document_origin=origin,
        created_at_utc=datetime(2026, 9, 1, 0, 0) + timedelta(hours=number),
    )
    db.session.add(order)
    return order


@pytest.mark.parametrize("role_code", ["SUPERVISOR", "ADMIN"])
def test_history_authorized_bilingual_filtered_and_newest_first(app, client, role_code):
    with app.app_context():
        user_id, station_id = identity(role_code)
        material = Material.query.filter_by(code="APPROVED-MAT-001").one()
        product = Product(code="HIST-FG", name="History Product")
        db.session.add(product)
        older = direct_order(1, product, material)
        newer = direct_order(2, product, material)
        direct_order(3, product, material, origin=None)
        db.session.commit()
        assert older.document_origin == newer.document_origin == "MOCK_ERP"
    authenticate(client, user_id, station_id)
    response = client.get("/mock-erp/history")
    assert response.status_code == 200
    assert "ประวัติเอกสารการผลิตจำลอง / Mock Production Document History".encode() in response.data
    assert response.data.index(b"HIST-PO-02") < response.data.index(b"HIST-PO-01")
    assert b"HIST-PO-03" not in response.data
    assert b"02/09/2026" in response.data
    assert b"01/09/2026 09:00" in response.data
    assert "พิมพ์ใบสั่งผลิตซ้ำ / Reprint Production Order".encode() in response.data
    filtered = client.get(
        "/mock-erp/history?po=PO-02&formula=FM-02&product=HIST-FG&lot=LOT-02"
        "&date_from=2026-09-02&date_to=2026-09-02"
    )
    assert filtered.status_code == 200
    assert b"HIST-PO-02" in filtered.data and b"HIST-PO-01" not in filtered.data


@pytest.mark.parametrize("role_code", ["OPERATOR", "PRODUCTION"])
def test_history_rejects_unauthorized_roles(app, client, role_code):
    with app.app_context():
        user_id, station_id = identity(role_code)
    authenticate(client, user_id, station_id)
    assert client.get("/mock-erp/history").status_code == 403


def test_history_requires_authentication_and_selected_station(app, client):
    assert client.get("/mock-erp/history").status_code == 302
    with app.app_context():
        user_id, _station_id = identity("ADMIN")
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    assert client.get("/mock-erp/history").status_code == 302


def test_history_date_validation_is_bilingual_and_redirect_safe(app, client):
    with app.app_context():
        user_id, station_id = identity("ADMIN")
    authenticate(client, user_id, station_id)
    invalid = client.get("/mock-erp/history?date_from=invalid")
    assert invalid.status_code == 302
    page = client.get(invalid.headers["Location"])
    assert "เลือกวันที่ประวัติที่ถูกต้อง / Select a valid history date.".encode() in page.data
    reversed_range = client.get(
        "/mock-erp/history?date_from=2026-09-09&date_to=2026-09-08"
    )
    assert reversed_range.status_code == 302


def test_history_paginates_25_mock_documents_and_excludes_unclassified(app, client):
    with app.app_context():
        user_id, station_id = identity("ADMIN")
        material = Material.query.filter_by(code="APPROVED-MAT-001").one()
        product = Product(code="PAGE-FG", name="Page Product")
        db.session.add(product)
        for number in range(1, 28):
            direct_order(number, product, material)
        direct_order(28, product, material, origin=None)
        db.session.commit()
    authenticate(client, user_id, station_id)
    first = client.get("/mock-erp/history")
    second = client.get("/mock-erp/history?page=2")
    assert first.status_code == second.status_code == 200
    assert first.data.count(b"HIST-PO-") == 25
    assert b"HIST-PO-28" not in first.data + second.data
    assert b"HIST-PO-01" in second.data


def test_new_mock_provenance_and_view_reprint_gets_are_read_only(app, client):
    with app.app_context():
        user_id, station_id = identity("ADMIN")
        unclassified = Product(code="LEGACY", name="Legacy")
        db.session.add(unclassified)
        legacy = ProductionOrder(
            po_no="LEGACY-PO", product=unclassified, production_lot="LEGACY-LOT", status="OPEN"
        )
        db.session.add(legacy)
        db.session.commit()
        order = create_mock_order(
            po_no="NEW-MOCK-PO", product_code="NEW-FG", product_name="New Product",
            production_lot="NEW-LOT", quantity=Decimal("30"), formula_code="NEW-MOCK-FM",
            production_date=date(2026, 9, 8), expected_finish_date=date(2026, 9, 9),
            material_sampler=lambda population, count: population[:count],
        )
        assert legacy.document_origin is None and legacy.created_at_utc is None
        assert order.document_origin == "MOCK_ERP" and order.created_at_utc is not None
        order_id = order.id
        tables = (
            ProductionOrder,
            Formula,
            FormulaItem,
            Material,
            Product,
            ProductionOrderProductSnapshot,
            AuditLog,
        )
        before = tuple(table.query.count() for table in tables)
    authenticate(client, user_id, station_id)
    paths = (
        f"/mock-erp/{order_id}/production-order",
        f"/mock-erp/{order_id}/formula-sheet",
        f"/mock-erp/{order_id}/production-order",
        f"/mock-erp/{order_id}/formula-sheet",
    )
    assert all(client.get(path).status_code == 200 for path in paths)
    with app.app_context():
        after = tuple(table.query.count() for table in tables)
        assert after == before
