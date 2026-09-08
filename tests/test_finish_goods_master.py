from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy.dialects import mssql
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    AuditLog,
    FinishGoodsImportBatch,
    FinishGoodsImportRow,
    FinishGoodsProfile,
    Product,
    ProductionOrder,
    Role,
    Station,
    User,
)
from app.services.finish_goods_import import (
    FinishGoodsImportError,
    _batch_statement,
    apply_finish_goods_import,
    create_finish_goods_import_preview,
    parse_finish_goods_workbook,
)
from app.services.mock_erp import MockDocumentError, create_mock_order

REAL_WORKBOOK = Path("/Users/rachin/Downloads/Finish good code 1.xlsx")


def identity(app, role="ADMIN"):
    with app.app_context():
        role_record = Role(code=role, name=role)
        user = User(
            username=f"fg-{role.lower()}",
            password_hash=generate_password_hash("test"),
            display_name="FG User",
            roles=[role_record],
        )
        station = Station(code=f"FG-{role[:3]}", name="FG Station")
        db.session.add_all([role_record, user, station])
        db.session.commit()
        return user.id, station.id


def authenticate(client, user_id, station_id):
    with client.session_transaction() as session:
        session["_user_id"], session["_fresh"], session["station_id"] = (
            str(user_id),
            True,
            station_id,
        )


def workbook_bytes(rows, headers=("FINISH GOODS_CODE", "CATEGORY_NO", "NAME")):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def preview(app, data, *, key="11111111-1111-4111-8111-111111111111"):
    user_id, station_id = identity(app)
    with app.app_context():
        batch = create_finish_goods_import_preview(
            file_bytes=data,
            filename="finish-goods.xlsx",
            idempotency_key=key,
            user_id=user_id,
            station_id=station_id,
            maximum_bytes=5 * 1024 * 1024,
            maximum_rows=5000,
            maximum_uncompressed_bytes=50 * 1024 * 1024,
        )
        return batch.id, user_id, station_id


def test_feature_disabled_before_new_table_queries(app, client):
    user_id, station_id = identity(app)
    authenticate(client, user_id, station_id)
    with app.app_context():
        FinishGoodsImportRow.__table__.drop(db.engine)
        FinishGoodsImportBatch.__table__.drop(db.engine)
    assert client.get("/master-data/finish-goods/import").status_code == 404
    assert client.get("/mock-erp/").status_code == 200


def test_import_requires_authentication_station_and_csrf(app, client):
    app.config["FINISHED_GOODS_MASTER_ENABLED"] = True
    assert client.get("/master-data/finish-goods/import").status_code == 302
    identity(app)
    client.post("/auth/login", data={"username": "fg-admin", "password": "test"})
    assert "/auth/station" in client.get("/master-data/finish-goods/import").headers["Location"]
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/master-data/finish-goods/import/1/apply").status_code == 400


@pytest.mark.parametrize("role", ["OPERATOR", "PRODUCTION", "SUPERVISOR"])
def test_import_is_admin_only(app, client, role):
    app.config["FINISHED_GOODS_MASTER_ENABLED"] = True
    user_id, station_id = identity(app, role)
    authenticate(client, user_id, station_id)
    assert client.get("/master-data/finish-goods/import").status_code == 403


def test_validation_normalization_duplicates_and_special_values(app):
    rows = parse_finish_goods_workbook(
        workbook_bytes(
            [
                (" fg-1 ", " f/g ", " Name "),
                ("TEST", "F/G", "NULL"),
                ("NO USE 1", "F/G", "NO USE item"),
            ]
        ),
        maximum_bytes=100000,
        maximum_rows=5000,
        maximum_uncompressed_bytes=1000000,
    )
    assert [(r.code, r.category, r.name, r.reason_code) for r in rows] == [
        ("FG-1", "F/G", "Name", None),
        ("TEST", "F/G", "NULL", None),
        ("NO USE 1", "F/G", "NO USE item", None),
    ]
    duplicates = parse_finish_goods_workbook(
        workbook_bytes([("fg-1", "F/G", "A"), (" FG-1 ", "F/G", "B")]),
        maximum_bytes=100000,
        maximum_rows=5000,
        maximum_uncompressed_bytes=1000000,
    )
    assert all(r.reason_code == "DUPLICATE_FINISH_GOODS_CODE" for r in duplicates)
    assert "2, 3" in duplicates[0].reason_detail


def test_upload_route_persists_preview_and_renders_counts(app, client):
    app.config["FINISHED_GOODS_MASTER_ENABLED"] = True
    user_id, station_id = identity(app)
    authenticate(client, user_id, station_id)
    response = client.post(
        "/master-data/finish-goods/import",
        data={
            "idempotency_key": "33333333-3333-4333-8333-333333333333",
            "workbook": (
                BytesIO(workbook_bytes([("FG-1", "F/G", "Duplicate Name")])),
                "finish-goods.xlsx",
            ),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 302
    preview_page = client.get(response.headers["Location"])
    assert b"Preview only" in preview_page.data
    assert b"FG-1" in preview_page.data
    assert "เพิ่ม / Insert" in preview_page.get_data(as_text=True)
    with app.app_context():
        assert Product.query.count() == 0
        row = FinishGoodsImportRow.query.one()
        assert row.result == "INSERT"


@pytest.mark.parametrize(
    "rows,message", [([("FG", "MAT", "Name")], "F/G"), ([("FG", "F/G", "")], "required")]
)
def test_invalid_rows_are_rejected_and_block_apply(app, rows, message):
    batch_id, user_id, station_id = preview(app, workbook_bytes(rows))
    with app.app_context():
        batch = db.session.get(FinishGoodsImportBatch, batch_id)
        assert batch.rejected_count == 1
        assert message.lower() in batch.rows[0].reason_detail.lower()
        with pytest.raises(FinishGoodsImportError):
            apply_finish_goods_import(batch_id=batch_id, user_id=user_id, station_id=station_id)


def test_preview_apply_idempotency_audit_and_preservation(app):
    batch_id, user_id, station_id = preview(
        app,
        workbook_bytes(
            [("FG-1", "F/G", "Name"), ("TEST", "F/G", "NULL"), ("NO USE", "F/G", "NO USE")]
        ),
    )
    with app.app_context():
        assert Product.query.count() == 0
        batch = apply_finish_goods_import(batch_id=batch_id, user_id=user_id, station_id=station_id)
        assert (batch.inserted_count, batch.updated_count, batch.unchanged_count) == (3, 0, 0)
        assert Product.query.count() == 3
        assert Product.query.filter_by(code="TEST").one().name == "NULL"
        assert all(product.is_active for product in Product.query.all())
        applied_at = batch.applied_at_utc
        apply_finish_goods_import(batch_id=batch_id, user_id=user_id, station_id=station_id)
        assert Product.query.count() == 3 and batch.applied_at_utc == applied_at
        assert AuditLog.query.filter_by(event_type="FINISHED_GOODS_IMPORT_APPLIED").count() == 1
        sql = str(_batch_statement(batch_id).compile(dialect=mssql.dialect()))
        assert "WITH (UPDLOCK, HOLDLOCK)" in sql


def test_apply_rejects_a_different_user(app):
    batch_id, user_id, station_id = preview(
        app, workbook_bytes([("FG-1", "F/G", "Name")])
    )
    with app.app_context():
        with pytest.raises(FinishGoodsImportError, match="preview uploader"):
            apply_finish_goods_import(
                batch_id=batch_id,
                user_id=user_id + 1,
                station_id=station_id,
            )
        assert Product.query.count() == 0


@pytest.mark.skipif(not REAL_WORKBOOK.exists(), reason="Approved workbook unavailable")
def test_real_workbook_first_and_second_import(app):
    data = REAL_WORKBOOK.read_bytes()
    batch_id, user_id, station_id = preview(app, data)
    with app.app_context():
        first = db.session.get(FinishGoodsImportBatch, batch_id)
        assert (
            first.total_rows,
            first.inserted_count,
            first.updated_count,
            first.unchanged_count,
            first.rejected_count,
        ) == (458, 458, 0, 0, 0)
        apply_finish_goods_import(batch_id=batch_id, user_id=user_id, station_id=station_id)
        assert (
            Product.query.filter(
                Product.code.in_([row.code_normalized for row in first.rows])
            ).count()
            == 458
        )
        assert Product.query.filter_by(code="TEST").one().name == "NULL"
        assert all(product.is_active for product in Product.query.all())
        second = create_finish_goods_import_preview(
            file_bytes=data,
            filename="second.xlsx",
            idempotency_key="22222222-2222-4222-8222-222222222222",
            user_id=user_id,
            station_id=station_id,
            maximum_bytes=5 * 1024 * 1024,
            maximum_rows=5000,
            maximum_uncompressed_bytes=50 * 1024 * 1024,
        )
        assert (
            second.inserted_count,
            second.updated_count,
            second.unchanged_count,
            second.rejected_count,
        ) == (0, 0, 458, 0)
        apply_finish_goods_import(batch_id=second.id, user_id=user_id, station_id=station_id)
        assert Product.query.count() == 458


def test_mock_erp_requires_active_master_selection_and_snapshots(app, client):
    app.config["FINISHED_GOODS_MASTER_ENABLED"] = True
    user_id, station_id = identity(app)
    with app.app_context():
        product = Product(code="FG-SELECT", name="Selected Name", is_active=True)
        product.finish_goods_profile = FinishGoodsProfile(source_category_no="F/G")
        inactive = Product(code="FG-OFF", name="Inactive", is_active=False)
        inactive.finish_goods_profile = FinishGoodsProfile(source_category_no="F/G")
        db.session.add_all([product, inactive])
        db.session.commit()
        product_id, inactive_id = product.id, inactive.id
    authenticate(client, user_id, station_id)
    page = client.get("/mock-erp/?finish_goods_q=select")
    assert (
        page.status_code == 200
        and b"FG-SELECT" in page.data
        and b"Search and Select Finish Good" in page.data
    )
    before = ProductionOrder.query.count() if False else 0
    with app.app_context():
        assert ProductionOrder.query.count() == before
    with app.app_context(), pytest.raises(MockDocumentError):
        create_mock_order(
            po_no="PO-OFF",
            product_id=inactive_id,
            production_lot="LOT",
            quantity=Decimal("1"),
            formula_code="FM-OFF",
            production_date=date(2026, 8, 1),
            expected_finish_date=date(2026, 8, 2),
        )
    with app.app_context():
        order = create_mock_order(
            po_no="PO-1",
            product_id=product_id,
            production_lot="LOT",
            quantity=Decimal("30"),
            formula_code="FM-1",
            production_date=date(2026, 8, 1),
            expected_finish_date=date(2026, 8, 2),
        )
        product = db.session.get(Product, product_id)
        product.name = "Changed Later"
        db.session.commit()
        order_id = order.id
    po = client.get(f"/mock-erp/{order_id}/production-order")
    formula = client.get(f"/mock-erp/{order_id}/formula-sheet")
    assert (
        b"FG-SELECT" in po.data and b"Selected Name" in po.data and b"Changed Later" not in po.data
    )
    assert b"Selected Name" in formula.data


def test_mock_erp_post_rejects_forged_selection_and_uses_master_values(app, client):
    app.config["FINISHED_GOODS_MASTER_ENABLED"] = True
    user_id, station_id = identity(app)
    with app.app_context():
        product = Product(code="FG-AUTH", name="Authorized Name", is_active=True)
        product.finish_goods_profile = FinishGoodsProfile(source_category_no="F/G")
        db.session.add(product)
        db.session.commit()
        product_id = product.id
    authenticate(client, user_id, station_id)
    payload = {
        "po_no": "FG-PO",
        "formula_code": "FG-FM",
        "product_id": str(product_id),
        "product_code": "FORGED",
        "product_name": "Forged Name",
        "production_lot": "LOT",
        "quantity": "30.000",
        "production_date": "2026-08-21",
        "expected_finish_date": "2026-08-22",
    }
    response = client.post("/mock-erp/", data=payload, follow_redirects=True)
    assert response.status_code == 200 and b"Mock Documents Ready" in response.data
    with app.app_context():
        order = ProductionOrder.query.filter_by(po_no="FG-PO").one()
        assert (order.product_snapshot.product_code, order.product_snapshot.product_name) == (
            "FG-AUTH",
            "Authorized Name",
        )
    payload["po_no"], payload["formula_code"], payload["product_id"] = (
        "BAD-PO",
        "BAD-FM",
        "999999",
    )
    forged = client.post("/mock-erp/", data=payload)
    assert forged.status_code == 200
    with app.app_context():
        assert ProductionOrder.query.filter_by(po_no="BAD-PO").count() == 0
