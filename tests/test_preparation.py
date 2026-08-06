from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import Formula, Product, ProductionOrder, Role, Station, User
from app.services.preparation import prepare_production_order


def seed_preparation_data(role_code="OPERATOR"):
    role = Role(code=role_code, name=role_code.title())
    user = User(
        username="preparer",
        password_hash=generate_password_hash("Prepare-Only!"),
        display_name="Preparation User",
        roles=[role],
    )
    station = Station(code="PREP-ST", name="Preparation Station")
    product_a = Product(code="FG-A", name="Product A")
    product_b = Product(code="FG-B", name="Product B")
    formula_a = Formula(code="FM-A", name="Formula A", product=product_a)
    formula_b = Formula(code="FM-B", name="Formula B", product=product_b)
    inactive_formula = Formula(
        code="FM-INACTIVE", name="Inactive Formula", product=product_a, is_active=False
    )
    orders = {
        status: ProductionOrder(
            po_no=f"PO-{status}",
            product=product_a,
            production_lot=f"LOT-{status}",
            status=status,
        )
        for status in ("OPEN", "CANCELLED", "COMPLETED")
    }
    db.session.add_all(
        [
            role,
            user,
            station,
            product_a,
            product_b,
            formula_a,
            formula_b,
            inactive_formula,
            *orders.values(),
        ]
    )
    db.session.commit()
    return user, station, orders, formula_a


def authenticate(client, station_id):
    client.post("/auth/login", data={"username": "preparer", "password": "Prepare-Only!"})
    client.post("/auth/station", data={"station_id": station_id})


def test_valid_po_formula_becomes_ready(app):
    with app.app_context():
        user, _, orders, formula = seed_preparation_data()
        result = prepare_production_order("PO-OPEN", "FM-A", user.id)
        assert result.success is True
        assert result.code == "READY"
        assert orders["OPEN"].status == "READY"
        assert orders["OPEN"].formula_id == formula.id
        assert orders["OPEN"].prepared_by_user_id == user.id
        assert orders["OPEN"].prepared_at_utc is not None


def test_missing_po_is_blocked(app):
    with app.app_context():
        user, _, _, _ = seed_preparation_data()
        result = prepare_production_order("MISSING", "FM-A", user.id)
        assert (result.success, result.code) == (False, "PO_NOT_FOUND")


def test_cancelled_and_completed_po_are_blocked(app):
    with app.app_context():
        user, _, _, _ = seed_preparation_data()
        cancelled = prepare_production_order("PO-CANCELLED", "FM-A", user.id)
        completed = prepare_production_order("PO-COMPLETED", "FM-A", user.id)
        assert cancelled.code == "PO_CANCELLED"
        assert completed.code == "PO_COMPLETED"


def test_wrong_missing_and_unavailable_formula_are_blocked(app):
    with app.app_context():
        user, _, orders, _ = seed_preparation_data()
        wrong = prepare_production_order("PO-OPEN", "FM-B", user.id)
        missing = prepare_production_order("PO-OPEN", "MISSING", user.id)
        unavailable = prepare_production_order("PO-OPEN", "FM-INACTIVE", user.id)
        assert wrong.code == "WRONG_FORMULA"
        assert missing.code == "FORMULA_NOT_FOUND"
        assert unavailable.code == "FORMULA_UNAVAILABLE"
        assert orders["OPEN"].status == "OPEN"


def test_ready_po_is_idempotent_only_for_its_formula(app):
    with app.app_context():
        user, _, orders, formula = seed_preparation_data()
        first = prepare_production_order("PO-OPEN", "FM-A", user.id)
        original_time = orders["OPEN"].prepared_at_utc
        second = prepare_production_order("PO-OPEN", "FM-A", user.id)
        assert first.success and second.success
        assert orders["OPEN"].formula_id == formula.id
        assert orders["OPEN"].prepared_at_utc == original_time


def test_preparation_page_workflow(app, client):
    with app.app_context():
        _, station, _, _ = seed_preparation_data()
        station_id = station.id
    authenticate(client, station_id)
    response = client.post("/preparation/", data={"po_no": "PO-OPEN", "formula_code": "FM-A"})
    assert response.status_code == 200
    assert b"ready for weighing" in response.data
    assert b"READY" in response.data


def test_production_role_cannot_prepare(app, client):
    with app.app_context():
        _, station, _, _ = seed_preparation_data(role_code="PRODUCTION")
        station_id = station.id
    authenticate(client, station_id)
    assert client.get("/preparation/").status_code == 403


def test_master_data_is_admin_only(app, client):
    with app.app_context():
        _, station, _, _ = seed_preparation_data(role_code="OPERATOR")
        station_id = station.id
    authenticate(client, station_id)
    assert client.get("/master-data/").status_code == 403


def test_admin_can_view_basic_master_data(app, client):
    with app.app_context():
        _, station, _, _ = seed_preparation_data(role_code="ADMIN")
        station_id = station.id
    authenticate(client, station_id)
    response = client.get("/master-data/")
    assert response.status_code == 200
    assert b"Master Data" in response.data
    assert b"FG-A" in response.data
    assert b"FM-A" in response.data
