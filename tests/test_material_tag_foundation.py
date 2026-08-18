from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    Material,
    MaterialImportBatch,
    MaterialImportRow,
    MaterialTag,
    MaterialTagBatch,
    MaterialTagDraft,
    MaterialTagPrintEvent,
    User,
)
from app.services.material_tag_issuance import (
    MaterialTagIssuanceError,
    build_material_tag_qr_payload,
    calculate_container_weights,
    calculate_expiry_date,
)
from app.services.weighing import parse_material_tag


def _qr_payload(**overrides):
    values = {
        "receiving_date": date(2026, 8, 5),
        "purchase_order": " PO-100 ",
        "purchase_order_line": " 010 ",
        "material_code": " r07047s1 ",
        "delivery_invoice": " INV-100 ",
        "vendor_lot": " 0508-P12675 ",
        "supplier": " Supplier A ",
        "comment": "",
        "warehouse": " WH-A ",
        "location": " LOC-1 ",
        "shelf": " S-1 ",
    }
    values.update(overrides)
    return build_material_tag_qr_payload(**values)


def test_weight_plan_exact_division_and_stable_json():
    plan = calculate_container_weights(Decimal("200.000"), Decimal("25.000"))
    assert plan.weights == (Decimal("25.000"),) * 8
    assert (plan.full_tag_count, plan.remainder_weight, plan.tag_count) == (
        8,
        Decimal("0.000"),
        8,
    )
    assert plan.json_values() == ("25.000",) * 8
    assert (
        plan.to_json()
        == '["25.000","25.000","25.000","25.000","25.000","25.000","25.000","25.000"]'
    )


def test_weight_plan_remainder_below_standard_and_reconciliation():
    plan = calculate_container_weights("210.000", "25.000")
    assert plan.weights == (Decimal("25.000"),) * 8 + (Decimal("10.000"),)
    assert sum(plan.weights, Decimal("0.000")) == Decimal("210.000")
    below = calculate_container_weights("0.001", "25.000")
    assert below.weights == (Decimal("0.001"),)


@pytest.mark.parametrize("value", ["1.0001", Decimal("1.0000")])
def test_weight_plan_rejects_excessive_precision(value):
    with pytest.raises(MaterialTagIssuanceError, match="no more than three decimals"):
        calculate_container_weights(value, "1.000")


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity", "-Infinity", 1.0, True, None])
def test_weight_plan_rejects_invalid_or_non_decimal_inputs(value):
    with pytest.raises(MaterialTagIssuanceError):
        calculate_container_weights(value, "1.000")


def test_weight_plan_enforces_two_hundred_tag_limit():
    assert calculate_container_weights("200.000", "1.000").tag_count == 200
    with pytest.raises(MaterialTagIssuanceError, match="between 1 and 200"):
        calculate_container_weights("201.000", "1.000")


@pytest.mark.parametrize(
    ("receiving", "expected"),
    [
        (date(2026, 8, 5), date(2027, 2, 4)),
        (date(2026, 8, 31), date(2027, 2, 27)),
        (date(2024, 2, 29), date(2024, 8, 28)),
        (date(2026, 12, 31), date(2027, 6, 29)),
        (date(2027, 8, 31), date(2028, 2, 28)),
    ],
)
def test_expiry_uses_approved_calendar_algorithm(receiving, expected):
    assert calculate_expiry_date(receiving) == expected


@pytest.mark.parametrize("invalid", [None, "05/08/2026", datetime(2026, 8, 5)])
def test_expiry_rejects_non_date_input(invalid):
    with pytest.raises(MaterialTagIssuanceError, match="valid date"):
        calculate_expiry_date(invalid)


def test_qr_payload_has_exact_order_format_normalization_and_empty_comment():
    payload = _qr_payload()
    assert payload == (
        "05/08/2026|PO-100|010|R07047S1|INV-100|0508-P12675|Supplier A||WH-A|LOC-1|S-1"
    )
    assert len(payload.split("|")) == 11
    parsed = parse_material_tag(payload)
    assert parsed.material_code == "R07047S1"
    assert parsed.comment == ""


@pytest.mark.parametrize(
    "field",
    [
        "purchase_order",
        "purchase_order_line",
        "material_code",
        "delivery_invoice",
        "vendor_lot",
        "supplier",
        "comment",
        "warehouse",
        "location",
        "shelf",
    ],
)
@pytest.mark.parametrize("invalid", ["value|other", "value\nother", "value\tother"])
def test_qr_payload_rejects_delimiters_and_control_characters(field, invalid):
    with pytest.raises(MaterialTagIssuanceError):
        _qr_payload(**{field: invalid})


def test_qr_payload_excludes_sequence_weight_expiry_and_other_unapproved_fields():
    payload = _qr_payload()
    assert "Tag 999" not in payload
    assert "25.000" not in payload
    assert "04/02/2027" not in payload
    assert "PG740" not in payload


def test_material_business_key_and_non_unique_name(app):
    with app.app_context():
        db.session.add_all(
            [
                Material(code="MAT-1", name="Duplicate Name", unit="kg"),
                Material(code="MAT-2", name="Duplicate Name", unit="kg"),
            ]
        )
        db.session.commit()
        db.session.add(Material(code="MAT-1", name="Another Name", unit="kg"))
        with pytest.raises(IntegrityError):
            db.session.commit()


def test_foundation_schema_columns_constraints_indexes_and_no_delete_cascade(app):
    expected_columns = {
        "material_import_batches": {"id", "file_sha256", "status", "idempotency_key"},
        "material_import_rows": {"id", "import_batch_id", "row_number", "result"},
        "material_tag_drafts": {
            "id",
            "draft_token",
            "calculated_tag_count",
            "calculated_weights_json",
        },
        "material_tag_batches": {
            "id",
            "batch_no",
            "material_code_snapshot",
            "qr_payload",
            "tag_count",
        },
        "material_tags": {"id", "batch_id", "sequence_no", "container_weight"},
        "material_tag_print_events": {
            "id",
            "batch_id",
            "material_tag_id",
            "print_scope",
            "print_type",
            "result",
        },
    }
    with app.app_context():
        inspector = inspect(db.engine)
        material_columns = {column["name"] for column in inspector.get_columns("materials")}
        assert {"source_category_no", "updated_at_utc", "updated_by_user_id"} <= material_columns
        for table, columns in expected_columns.items():
            assert columns <= {column["name"] for column in inspector.get_columns(table)}
            for foreign_key in inspector.get_foreign_keys(table):
                assert not foreign_key.get("options", {}).get("ondelete")

        check_sql = " ".join(
            constraint.get("sqltext") or ""
            for table in expected_columns
            for constraint in inspector.get_check_constraints(table)
        )
        for value in (
            "PREVIEWED",
            "APPLIED",
            "EXPIRED",
            "UNCHANGED",
            "REJECTED",
            "ISSUED",
            "BATCH",
            "INDIVIDUAL",
            "ORIGINAL",
            "REPRINT",
            "RENDERED",
            "FAILED",
        ):
            assert value in check_sql

        assert {index["name"] for index in inspector.get_indexes("materials")} >= {
            "ix_materials_name"
        }
        tag_unique_columns = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("material_tags")
        }
        assert tag_unique_columns == {("batch_id", "sequence_no")}


def test_foundation_relationships_do_not_delete_related_history():
    relationship_sets = (
        MaterialImportBatch.__mapper__.relationships,
        MaterialImportRow.__mapper__.relationships,
        MaterialTagDraft.__mapper__.relationships,
        MaterialTagBatch.__mapper__.relationships,
        MaterialTag.__mapper__.relationships,
        MaterialTagPrintEvent.__mapper__.relationships,
    )
    assert all(
        "delete" not in relationship.cascade
        for group in relationship_sets
        for relationship in group
    )


def test_database_rejects_invalid_import_status(app):
    with app.app_context():
        user = User(
            username="foundation-admin",
            password_hash=generate_password_hash("test-only"),
            display_name="Foundation Admin",
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(
            MaterialImportBatch(
                original_filename="materials.xlsx",
                file_sha256="0" * 64,
                status="INVALID",
                total_rows=1,
                uploaded_by_user_id=user.id,
                uploaded_at_utc=datetime(2026, 8, 18),
                idempotency_key="00000000-0000-0000-0000-000000000001",
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
