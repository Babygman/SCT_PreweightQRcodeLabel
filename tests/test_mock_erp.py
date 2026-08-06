from datetime import date
from decimal import Decimal

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import AuditLog, Formula, Product, ProductionOrder, Role, Station, User
from app.services.mock_erp import MockDocumentError, create_mock_order
from app.services.preparation import prepare_production_order


def seed_user(role_code="ADMIN"):
    role = Role(code=role_code, name=role_code.title())
    user = User(
        username="mock_user",
        password_hash=generate_password_hash("Mock-Only!"),
        display_name="Mock User",
        roles=[role],
    )
    station = Station(code="MOCK-ST", name="Mock Station")
    db.session.add_all([role, user, station])
    db.session.commit()
    return user, station


def authenticate(client, station_id):
    client.post("/auth/login", data={"username": "mock_user", "password": "Mock-Only!"})
    client.post("/auth/station", data={"station_id": station_id})


def build_order(po_no="PD001", formula_code="FS001", lot="LOT001", quantity="100.000"):
    return create_mock_order(
        po_no=po_no,
        product_code="FG001",
        product_name="Finished Good 001",
        production_lot=lot,
        quantity=Decimal(quantity),
        formula_code=formula_code,
        production_date=date(2026, 8, 10),
        expected_finish_date=date(2026, 8, 15),
    )


def test_mock_order_creates_one_to_one_documents_and_30_balanced_lines(app):
    with app.app_context():
        order = build_order()
        assert order.formula is not None
        assert order.formula.code == "FS001"
        assert order.formula.production_lot == "LOT001"
        assert order.formula.batch_quantity == Decimal("100.000")
        assert len(order.formula.items) == 30
        assert sum(item.target_weight for item in order.formula.items) == Decimal("100.000")
        assert order.quantity == Decimal("100.000")


def test_mock_identifiers_must_be_unique(app):
    with app.app_context():
        build_order()
        try:
            build_order()
        except MockDocumentError as exc:
            assert "Production Order" in str(exc)
        else:
            raise AssertionError("duplicate mock Production Order was accepted")


def test_scanned_qr_payloads_prepare_the_exact_pair(app):
    with app.app_context():
        user, station = seed_user("OPERATOR")
        order = build_order()
        result = prepare_production_order("SCTPO|PD001", "SCTFS|FS001", user.id, station.id)
        assert result.success is True
        assert order.status == "READY"


def test_wrong_formula_pair_is_blocked_and_logged(app):
    with app.app_context():
        user, station = seed_user("OPERATOR")
        order = build_order()
        product = db.session.get(Product, order.product_id)
        other = Formula(
            code="FS999",
            name="Other Sheet",
            product=product,
            production_lot=order.production_lot,
            batch_quantity=order.quantity,
        )
        db.session.add(other)
        db.session.commit()
        result = prepare_production_order("SCTPO|PD001", "SCTFS|FS999", user.id, station.id)
        assert (result.success, result.code) == (False, "WRONG_FORMULA")
        assert order.status == "OPEN"
        log = AuditLog.query.filter_by(event_type="PO_FORMULA_SCAN_FAIL").one()
        assert "reason=WRONG_FORMULA" in log.detail


def test_mock_erp_page_generates_printable_qr_documents(app, client):
    with app.app_context():
        _, station = seed_user("ADMIN")
        station_id = station.id
    authenticate(client, station_id)
    response = client.post(
        "/mock-erp/",
        data={
            "po_no": "PD100",
            "formula_code": "FS100",
            "product_code": "FG100",
            "product_name": "Finished Good 100",
            "production_lot": "LOT100",
            "quantity": "90.000",
            "production_date": "2026-08-10",
            "expected_finish_date": "2026-08-15",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Mock Documents Ready" in response.data
    with app.app_context():
        order = ProductionOrder.query.filter_by(po_no="PD100").one()
        po_id = order.id
        formula_id = order.formula_id
    po_document = client.get(f"/mock-erp/{po_id}/production-order")
    formula_document = client.get(f"/mock-erp/{po_id}/formula-sheet")
    po_qr = client.get(f"/mock-erp/qr/po/{po_id}.png")
    formula_qr = client.get(f"/mock-erp/qr/formula/{formula_id}.png")
    assert b"PRODUCTION ORDER" in po_document.data
    assert b"FORMULA SHEET" in formula_document.data
    assert b"MOCK-RM030" in formula_document.data
    assert po_qr.content_type == "image/png"
    assert formula_qr.content_type == "image/png"


def test_print_links_open_separate_windows_without_losing_session(app, client):
    with app.app_context():
        _, station = seed_user("ADMIN")
        order = build_order()
        station_id = station.id
        po_id = order.id
    authenticate(client, station_id)

    detail = client.get(f"/mock-erp/{po_id}")
    assert detail.status_code == 200
    assert b"openPrintWindow(this)" in detail.data
    assert f'target="mock-po-{po_id}"'.encode() in detail.data
    assert f'target="mock-formula-{po_id}"'.encode() in detail.data
    assert b"window.open" in detail.data

    po_document = client.get(f"/mock-erp/{po_id}/production-order")
    formula_document = client.get(f"/mock-erp/{po_id}/formula-sheet")
    assert b"Print A4" in po_document.data
    assert b"Print A4" in formula_document.data
    assert b"window.print()" in po_document.data
    assert b"window.print()" in formula_document.data

    home = client.get("/")
    assert home.status_code == 200
    assert b"MOCK-ST" in home.data


def test_operator_cannot_access_mock_erp(app, client):
    with app.app_context():
        _, station = seed_user("OPERATOR")
        station_id = station.id
    authenticate(client, station_id)
    assert client.get("/mock-erp/").status_code == 403
