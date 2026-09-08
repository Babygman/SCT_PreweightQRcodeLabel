from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    AuditLog,
    Formula,
    FormulaItem,
    Material,
    MaterialImportBatch,
    MaterialImportRow,
    Product,
    ProductionOrder,
    ProductionOrderProductSnapshot,
    Role,
    Station,
    User,
)
from app.services.mock_erp import MockDocumentError, create_mock_order
from app.services.preparation import prepare_production_order

pytestmark = pytest.mark.usefixtures("approved_materials")

INVALID_DATE_MESSAGE = (
    "กรุณาเลือกวันที่ที่ถูกต้องจากปฏิทิน / "
    "Please select a valid date from the calendar."
)
EARLY_FINISH_MESSAGE = (
    "วันที่คาดว่าจะผลิตเสร็จต้องไม่ก่อนวันที่ผลิต / "
    "Expected Finish Date cannot be earlier than Production Date."
)


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


def mock_form_payload(**changes):
    payload = {
        "po_no": "PD-DATE",
        "formula_code": "FS-DATE",
        "product_code": "FG-DATE",
        "product_name": "Finished Good Date Test",
        "production_lot": "LOT-DATE",
        "quantity": "100.000",
        "production_date": "2026-09-07",
        "expected_finish_date": "2026-09-08",
    }
    payload.update(changes)
    return payload


def document_counts():
    return (
        ProductionOrder.query.count(),
        Formula.query.count(),
        FormulaItem.query.count(),
        ProductionOrderProductSnapshot.query.count(),
        Product.query.count(),
        AuditLog.query.count(),
    )


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


def test_approved_material_selection_is_distinct_injectable_and_excludes_ineligible(
    app, approved_materials
):
    with app.app_context():
        applied_batch = MaterialImportBatch.query.filter_by(status="APPLIED").one()
        excluded = [
            Material(code="MOCK-RM001", name="Mock", unit="kg", is_active=True),
            Material(
                code="NOT-IMPORTED", name="Not imported", unit="kg", is_active=True,
                source_category_no="MAT",
            ),
            Material(
                code="INACTIVE-MAT", name="Inactive", unit="kg", is_active=False,
                source_category_no="MAT",
            ),
            Material(
                code="PREVIEWED-MAT", name="Previewed", unit="kg", is_active=True,
                source_category_no="MAT",
            ),
            Material(
                code="REJECTED-MAT", name="Rejected", unit="kg", is_active=True,
                source_category_no="MAT",
            ),
        ]
        db.session.add_all(excluded)
        db.session.flush()
        db.session.add(
            MaterialImportRow(
                import_batch_id=applied_batch.id,
                row_number=100,
                item_code_normalized="INACTIVE-MAT",
                category_no_normalized="MAT",
                name_normalized="Inactive",
                result="INSERT",
            )
        )
        previewed_batch = MaterialImportBatch(
            original_filename="previewed.xlsx", file_sha256="b" * 64, status="PREVIEWED",
            total_rows=1, inserted_count=1, updated_count=0, unchanged_count=0,
            rejected_count=0, uploaded_by_user_id=applied_batch.uploaded_by_user_id,
            uploaded_at_utc=applied_batch.uploaded_at_utc,
            idempotency_key="00000000-0000-4000-8000-000000000002",
        )
        db.session.add(previewed_batch)
        db.session.flush()
        db.session.add_all(
            [
                MaterialImportRow(
                    import_batch_id=previewed_batch.id, row_number=2,
                    item_code_normalized="PREVIEWED-MAT", category_no_normalized="MAT",
                    name_normalized="Previewed", result="INSERT",
                ),
                MaterialImportRow(
                    import_batch_id=applied_batch.id, row_number=101,
                    item_code_normalized="REJECTED-MAT", category_no_normalized="MAT",
                    name_normalized="Rejected", result="REJECTED",
                ),
            ]
        )
        db.session.commit()
        before = [
            (
                m.id,
                m.code,
                m.name,
                m.unit,
                m.classification,
                m.source_category_no,
                m.is_active,
                m.updated_at_utc,
                m.updated_by_user_id,
            )
            for m in Material.query.order_by(Material.id)
        ]
        sampled_codes = []

        def sampler(population, count):
            sampled_codes.extend(material.code for material in population)
            return list(reversed(population))[:count]

        order = create_mock_order(
            po_no="ELIGIBLE-PO", product_code="FG-ELIGIBLE", product_name="Eligible",
            production_lot="ELIGIBLE-LOT", quantity=Decimal("30"),
            formula_code="ELIGIBLE-FM", production_date=date(2026, 9, 8),
            expected_finish_date=date(2026, 9, 9), material_sampler=sampler,
        )
        selected_ids = [item.material_id for item in order.formula.items]
        assert len(selected_ids) == len(set(selected_ids)) == 30
        assert set(sampled_codes) == {
            db.session.get(Material, material_id).code for material_id in approved_materials
        }
        assert not {
            "MOCK-RM001", "NOT-IMPORTED", "INACTIVE-MAT", "PREVIEWED-MAT", "REJECTED-MAT"
        } & set(sampled_codes)
        after = [
            (
                m.id,
                m.code,
                m.name,
                m.unit,
                m.classification,
                m.source_category_no,
                m.is_active,
                m.updated_at_utc,
                m.updated_by_user_id,
            )
            for m in Material.query.order_by(Material.id)
        ]
        assert after == before


def test_runtime_sampler_uses_system_random(app, monkeypatch):
    called = []

    def sample(_self, population, count):
        called.append((len(population), count))
        return population[:count]

    monkeypatch.setattr("app.services.mock_erp.random.SystemRandom.sample", sample)
    with app.app_context():
        build_order()
    assert called == [(30, 30)]


def test_fewer_than_30_approved_materials_is_bilingual_with_zero_residue(app):
    expected = (
        "ต้องมีวัตถุดิบที่ใช้งานและผ่านการนำเข้าที่อนุมัติแล้วอย่างน้อย 30 รายการ / "
        "At least 30 active approved imported Materials are required."
    )
    with app.app_context():
        Material.query.filter_by(code="APPROVED-MAT-030").one().is_active = False
        db.session.commit()
        before = document_counts()
        with pytest.raises(MockDocumentError, match="At least 30") as error:
            build_order()
        assert str(error.value) == expected
        assert document_counts() == before


def test_database_exception_rolls_back_every_pending_document_row(app, monkeypatch):
    with app.app_context():
        before = document_counts()
        original_commit = db.session.commit

        def fail_commit():
            db.session.flush()
            raise SQLAlchemyError("forced isolated failure")

        monkeypatch.setattr(db.session, "commit", fail_commit)
        with pytest.raises(SQLAlchemyError, match="forced isolated failure"):
            build_order()
        monkeypatch.setattr(db.session, "commit", original_commit)
        assert document_counts() == before


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
        assert order.production_date == date(2026, 8, 10)
        assert order.expected_finish_date == date(2026, 8, 15)
    po_document = client.get(f"/mock-erp/{po_id}/production-order")
    formula_document = client.get(f"/mock-erp/{po_id}/formula-sheet")
    po_qr = client.get(f"/mock-erp/qr/po/{po_id}.png")
    formula_qr = client.get(f"/mock-erp/qr/formula/{formula_id}.png")
    assert b"PRODUCTION ORDER" in po_document.data
    assert b"FORMULA SHEET" in formula_document.data
    assert formula_document.data.count(b"APPROVED-MAT-") == 30
    assert b"MOCK-RM" not in formula_document.data
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


def test_mock_erp_renders_shared_read_only_date_pickers_and_minimum_sync(app, client):
    with app.app_context():
        _, station = seed_user("ADMIN")
        station_id = station.id
    authenticate(client, station_id)

    response = client.get("/mock-erp/")

    assert response.status_code == 200
    assert b'name="production_date"' in response.data
    assert b'name="expected_finish_date"' in response.data
    assert response.data.count(b'type="date"') == 2
    assert response.data.count(b"data-date-picker") == 2
    assert response.data.count(b"data-date-display") == 2
    assert response.data.count(b"readonly") >= 2
    assert response.data.count(b"data-date-button") == 2
    assert response.data.count(b"data-date-input") == 2
    assert "วันที่ผลิต / Production Date".encode() in response.data
    assert "วันที่คาดว่าจะผลิตเสร็จ / Expected Finish Date".encode() in response.data
    assert date.today().isoformat().encode() in response.data
    assert date.today().strftime("%d/%m/%Y").encode() in response.data
    assert b"expectedFinishDate.min = productionDate.value" in response.data
    assert b"productionDate.addEventListener('input', syncExpectedFinishMinimum)" in response.data
    picker_script = client.get("/static/date-picker.js")
    assert picker_script.status_code == 200
    assert b"input.showPicker" in picker_script.data
    assert b"input.focus()" in picker_script.data
    assert b"input.click()" in picker_script.data
    assert b"`${match[3]}/${match[2]}/${match[1]}`" in picker_script.data


def test_malformed_finish_date_is_bilingual_and_creates_no_partial_data(app, client):
    with app.app_context():
        _, station = seed_user("ADMIN")
        station_id = station.id
    authenticate(client, station_id)
    with app.app_context():
        before = document_counts()

    response = client.post(
        "/mock-erp/",
        data=mock_form_payload(expected_finish_date="08092026"),
    )

    assert response.status_code == 200
    assert INVALID_DATE_MESSAGE.encode() in response.data
    with app.app_context():
        assert document_counts() == before


def test_malformed_production_date_does_not_compare_string_to_date(app, client):
    with app.app_context():
        _, station = seed_user("ADMIN")
        station_id = station.id
    authenticate(client, station_id)
    with app.app_context():
        before = document_counts()

    response = client.post(
        "/mock-erp/",
        data=mock_form_payload(production_date="07092026"),
    )

    assert response.status_code == 200
    assert INVALID_DATE_MESSAGE.encode() in response.data
    with app.app_context():
        assert document_counts() == before


def test_finish_date_before_production_is_rejected_without_partial_data(app, client):
    with app.app_context():
        _, station = seed_user("ADMIN")
        station_id = station.id
    authenticate(client, station_id)
    with app.app_context():
        before = document_counts()

    response = client.post(
        "/mock-erp/",
        data=mock_form_payload(expected_finish_date="2026-09-06"),
    )

    assert response.status_code == 200
    assert EARLY_FINISH_MESSAGE.encode() in response.data
    with app.app_context():
        assert document_counts() == before


def test_missing_date_uses_bilingual_required_error_without_partial_data(app, client):
    with app.app_context():
        _, station = seed_user("ADMIN")
        station_id = station.id
    authenticate(client, station_id)
    with app.app_context():
        before = document_counts()

    response = client.post(
        "/mock-erp/",
        data=mock_form_payload(expected_finish_date=""),
    )

    assert response.status_code == 200
    assert "จำเป็นต้องกรอกข้อมูลนี้ / This field is required.".encode() in response.data
    with app.app_context():
        assert document_counts() == before
