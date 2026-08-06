from sqlalchemy import inspect

from app.extensions import db
from app.models import Formula, ProductionOrder, Role, User


def test_home_page_opens(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_error_page(client):
    response = client.get("/missing")
    assert response.status_code == 404
    assert b"Page not found" in response.data


def test_schema_contains_approved_tables(app):
    expected = {
        "audit_logs",
        "formula_items",
        "formulas",
        "label_print_logs",
        "materials",
        "production_orders",
        "products",
        "raw_material_lots",
        "roles",
        "stations",
        "user_roles",
        "users",
        "verification_logs",
        "weighing_transactions",
    }
    with app.app_context():
        assert set(inspect(db.engine).get_table_names()) == expected


def test_seed_command_is_idempotency_safe(app):
    runner = app.test_cli_runner()
    first = runner.invoke(args=["seed-uat"])
    second = runner.invoke(args=["seed-uat"])
    assert first.exit_code == 0
    assert second.exit_code != 0
    with app.app_context():
        assert Role.query.count() == 4
        assert User.query.count() == 4


def test_stage3_seed_supplement_is_idempotent(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["seed-uat"]).exit_code == 0
    assert runner.invoke(args=["seed-stage3"]).exit_code == 0
    assert runner.invoke(args=["seed-stage3"]).exit_code == 0
    with app.app_context():
        assert Formula.query.filter_by(code="UAT-FM-INACTIVE").count() == 1
        assert ProductionOrder.query.filter_by(po_no="UAT-PO-CANCELLED").count() == 1
        assert ProductionOrder.query.filter_by(po_no="UAT-PO-COMPLETED").count() == 1
