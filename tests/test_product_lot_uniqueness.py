import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    AuditLog,
    FinishGoodsProfile,
    Formula,
    FormulaItem,
    Product,
    ProductionOrder,
    ProductionOrderProductSnapshot,
    Role,
    Station,
    User,
)
from app.production_lots import ProductionLotError, normalize_production_lot
from app.services.mock_erp import (
    MockDocumentError,
    _is_product_lot_constraint_error,
    create_mock_order,
)


def product(code):
    value = Product(code=code, name=code, is_active=True)
    value.finish_goods_profile = FinishGoodsProfile(source_category_no="F/G")
    db.session.add(value)
    db.session.commit()
    return value


def create(po, formula, selected_product, lot="L001"):
    return create_mock_order(
        po_no=po,
        product_id=selected_product.id,
        production_lot=lot,
        quantity=Decimal("30.000"),
        formula_code=formula,
        production_date=date(2026, 8, 25),
        expected_finish_date=date(2026, 8, 26),
    )


def test_normalization_contract():
    assert normalize_production_lot("  l001  ") == "L001"
    assert normalize_production_lot("Cafe\u0301") == "CAFÉ"
    assert normalize_production_lot("LOT  001") == "LOT  001"
    with pytest.raises(ProductionLotError, match="required"):
        normalize_production_lot("  ")
    with pytest.raises(ProductionLotError, match="control"):
        normalize_production_lot("LOT\n001")
    with pytest.raises(ProductionLotError, match="100"):
        normalize_production_lot("L" * 101)
    with pytest.raises(ProductionLotError, match="100"):
        normalize_production_lot("ß" * 100)
    with pytest.raises(ProductionLotError, match="text"):
        normalize_production_lot(1001)


def test_different_products_may_share_same_normalized_lot(app):
    with app.app_context():
        first, second = product("FG-A"), product("FG-B")
        create("PO-A", "FM-A", first, "L001")
        create("PO-B", "FM-B", second, " l001 ")
        assert ProductionOrder.query.filter_by(production_lot_normalized="L001").count() == 2


@pytest.mark.parametrize(
    ("original", "duplicate"),
    [("L001", "L001"), ("L001", " l001 "), ("CAFÉ", "Cafe\u0301")],
)
def test_same_product_and_normalized_lot_is_rejected_without_partial_rows(
    app, original, duplicate
):
    with app.app_context():
        selected = product("FG-A")
        create("PO-A", "FM-A", selected, original)
        before = (
            ProductionOrder.query.count(),
            Formula.query.count(),
            FormulaItem.query.count(),
            ProductionOrderProductSnapshot.query.count(),
            AuditLog.query.count(),
        )
        with pytest.raises(MockDocumentError, match="FG-A.*Production Lot"):
            create("PO-B", "FM-B", selected, duplicate)
        assert (
            ProductionOrder.query.count(),
            Formula.query.count(),
            FormulaItem.query.count(),
            ProductionOrderProductSnapshot.query.count(),
            AuditLog.query.count(),
        ) == before
        assert ProductionOrder.query.filter_by(po_no="PO-B").count() == 0
        assert Formula.query.filter_by(code="FM-B").count() == 0


def test_database_constraint_blocks_direct_duplicate_but_not_different_product(app):
    with app.app_context():
        first, second = product("FG-A"), product("FG-B")
        create("PO-A", "FM-A", first)
        db.session.add(
            ProductionOrder(po_no="PO-B", product=second, production_lot="l001", status="OPEN")
        )
        db.session.commit()
        db.session.add(
            ProductionOrder(
                po_no="PO-A2", product=first, production_lot=" l001 ", status="OPEN"
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        assert ProductionOrder.query.count() == 2


def test_race_constraint_is_translated_and_rolls_back_complete_document(app, monkeypatch):
    with app.app_context():
        selected = product("FG-A")
        create("PO-A", "FM-A", selected)
        before = (
            ProductionOrder.query.count(),
            Formula.query.count(),
            FormulaItem.query.count(),
            ProductionOrderProductSnapshot.query.count(),
        )
        monkeypatch.setattr("app.services.mock_erp._product_lot_exists", lambda *_args: False)
        with pytest.raises(MockDocumentError, match="FG-A.*Production Lot"):
            create("PO-RACE", "FM-RACE", selected, " l001 ")
        assert (
            ProductionOrder.query.count(),
            Formula.query.count(),
            FormulaItem.query.count(),
            ProductionOrderProductSnapshot.query.count(),
        ) == before


def test_duplicate_route_uses_prg_and_refresh_leaves_no_residue(app, client):
    app.config["FINISHED_GOODS_MASTER_ENABLED"] = True
    with app.app_context():
        selected = product("FG-A")
        create("PO-A", "FM-A", selected, "L001")
        role = Role(code="ADMIN", name="Admin")
        user = User(
            username="admin",
            password_hash=generate_password_hash("test"),
            display_name="Admin",
            roles=[role],
        )
        station = Station(code="ST-1", name="Station 1")
        db.session.add_all([role, user, station])
        db.session.commit()
        product_id, user_id, station_id = selected.id, user.id, station.id
        before = (
            ProductionOrder.query.count(),
            Formula.query.count(),
            FormulaItem.query.count(),
            ProductionOrderProductSnapshot.query.count(),
            AuditLog.query.count(),
        )
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
        session["station_id"] = station_id
    response = client.post(
        "/mock-erp/",
        data={
            "po_no": "PO-DUP",
            "formula_code": "FM-DUP",
            "product_id": str(product_id),
            "production_lot": "  l001  ",
            "quantity": "30.000",
            "production_date": "25/08/2026",
            "expected_finish_date": "26/08/2026",
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/mock-erp/")

    redirected = client.get(response.headers["Location"])
    assert redirected.status_code == 200
    assert b"Product FG-A already has Production Lot l001" in redirected.data
    prohibited = (
        b"uq_production_orders_product_lot_normalized",
        b"Traceback",
        b"sqlalchemy",
        b"pyodbc",
        b"/Users/rachin/Projects",
        b"password",
    )
    assert not any(value in redirected.data for value in prohibited)

    refreshed = client.get(response.headers["Location"])
    assert refreshed.status_code == 200
    with app.app_context():
        assert (
            ProductionOrder.query.count(),
            Formula.query.count(),
            FormulaItem.query.count(),
            ProductionOrderProductSnapshot.query.count(),
            AuditLog.query.count(),
        ) == before
        assert ProductionOrder.query.filter_by(po_no="PO-DUP").count() == 0
        assert Formula.query.filter_by(code="FM-DUP").count() == 0


def test_constraint_specific_integrity_error_detection_does_not_mask_other_errors():
    intended = IntegrityError(
        "insert", {}, Exception("uq_production_orders_product_lot_normalized")
    )
    sqlite_intended = IntegrityError(
        "insert",
        {},
        Exception(
            "UNIQUE constraint failed: production_orders.product_id, "
            "production_orders.production_lot_normalized"
        ),
    )
    unrelated = IntegrityError("insert", {}, Exception("uq_production_orders_po_no"))
    assert _is_product_lot_constraint_error(intended)
    assert _is_product_lot_constraint_error(sqlite_intended)
    assert not _is_product_lot_constraint_error(unrelated)


def test_model_has_composite_constraint_and_no_global_lot_uniqueness(app):
    with app.app_context():
        constraints = inspect(db.engine).get_unique_constraints("production_orders")
    columns = {tuple(item["column_names"]) for item in constraints}
    assert ("product_id", "production_lot_normalized") in columns
    assert ("production_lot",) not in columns


def test_migration_normalizer_matches_application_contract():
    path = Path("migrations/versions/f3a6c9e2b7d1_add_product_lot_business_key.py")
    spec = importlib.util.spec_from_file_location("product_lot_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for value in (" L001 ", "l001", "Cafe\u0301", "LOT  001"):
        assert module._normalize(value) == normalize_production_lot(value)
