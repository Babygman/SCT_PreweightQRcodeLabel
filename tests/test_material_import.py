from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import Workbook
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    AuditLog,
    Material,
    MaterialImportBatch,
    MaterialImportRow,
    MaterialTag,
    MaterialTagBatch,
    MaterialTagDraft,
    Role,
    Station,
    User,
)
from app.services.material_import import MaterialImportError, parse_material_workbook

REAL_WORKBOOK = Path("/Users/rachin/Downloads/Material code.xlsx")


def _identity(app, role_code="ADMIN"):
    with app.app_context():
        role = Role(code=role_code, name=role_code.title())
        user = User(
            username=f"{role_code.lower()}-importer",
            password_hash=generate_password_hash("Test-only-password!"),
            display_name=f"{role_code.title()} Importer",
            roles=[role],
        )
        station = Station(code=f"{role_code[:3]}-ST", name="Import Station")
        db.session.add_all([role, user, station])
        db.session.commit()
        return user.id, station.id


def _authenticate(client, user_id, station_id):
    with client.session_transaction() as user_session:
        user_session["_user_id"] = str(user_id)
        user_session["_fresh"] = True
        user_session["station_id"] = station_id


def _workbook_bytes(rows, headers=("ITEM CODE", "CATEGORY_NO", "NAME")):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Sheet1"
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _upload(client, workbook_bytes, idempotency_key="11111111-1111-4111-8111-111111111111"):
    return client.post(
        "/master-data/material-import",
        data={
            "idempotency_key": idempotency_key,
            "workbook": (BytesIO(workbook_bytes), "materials.xlsx"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )


def test_feature_is_disabled_by_default_without_querying_new_tables(app, client):
    user_id, station_id = _identity(app)
    _authenticate(client, user_id, station_id)
    with app.app_context():
        MaterialImportRow.__table__.drop(db.engine)
        MaterialImportBatch.__table__.drop(db.engine)
    assert client.get("/master-data/material-import").status_code == 404


@pytest.mark.parametrize("role_code", ["OPERATOR", "PRODUCTION", "SUPERVISOR"])
def test_material_import_routes_are_admin_only(app, client, role_code):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id = _identity(app, role_code)
    _authenticate(client, user_id, station_id)
    assert client.get("/master-data/material-import").status_code == 403


def test_material_import_requires_authentication_and_station(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    assert client.get("/master-data/material-import").status_code == 302
    _identity(app)
    client.post(
        "/auth/login",
        data={"username": "admin-importer", "password": "Test-only-password!"},
    )
    response = client.get("/master-data/material-import")
    assert response.status_code == 302
    assert "/auth/station" in response.headers["Location"]


def test_apply_requires_csrf_when_enabled(app, client):
    app.config.update(MATERIAL_TAG_ISSUANCE_ENABLED=True, WTF_CSRF_ENABLED=True)
    user_id, station_id = _identity(app)
    _authenticate(client, user_id, station_id)
    assert client.post("/master-data/material-import/1/apply").status_code == 400


def test_structural_failure_is_persistent_and_audited(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id = _identity(app)
    _authenticate(client, user_id, station_id)
    response = _upload(client, b"not an xlsx")
    assert response.status_code == 302
    with app.app_context():
        batch = MaterialImportBatch.query.one()
        assert batch.status == "FAILED"
        assert "valid .xlsx" in batch.error_summary
        assert AuditLog.query.filter_by(event_type="MATERIAL_IMPORT_VALIDATION_FAILED").count() == 1


def test_row_validation_normalization_and_duplicate_classification():
    workbook_bytes = _workbook_bytes(
        [
            (" mat-1 ", " mat ", " Name One "),
            ("MAT-1", "MAT", "Duplicate Code"),
            (None, "MAT", "Missing Code"),
            ("MAT-2", "OTHER", "Wrong Category"),
            ("MAT-3", "MAT", "=1+1"),
        ]
    )
    rows = parse_material_workbook(
        workbook_bytes,
        maximum_bytes=5 * 1024 * 1024,
        maximum_rows=10_000,
        maximum_uncompressed_bytes=50 * 1024 * 1024,
    )
    assert [row.reason_code for row in rows] == [
        "DUPLICATE_ITEM_CODE",
        "DUPLICATE_ITEM_CODE",
        "REQUIRED_VALUE_MISSING",
        "CATEGORY_NOT_ALLOWED",
        "FORMULA_NOT_ALLOWED",
    ]
    assert rows[0].item_code == "MAT-1"
    assert rows[0].name == "Name One"


def test_workbook_rejects_wrong_headers_and_extra_sheet():
    bad_headers = _workbook_bytes([("MAT-1", "MAT", "Name")], headers=("CODE", "CAT", "NAME"))
    with pytest.raises(MaterialImportError, match="headers must be exactly"):
        parse_material_workbook(
            bad_headers,
            maximum_bytes=5 * 1024 * 1024,
            maximum_rows=10_000,
            maximum_uncompressed_bytes=50 * 1024 * 1024,
        )

    workbook = Workbook()
    workbook.active.title = "Sheet1"
    workbook.active.append(("ITEM CODE", "CATEGORY_NO", "NAME"))
    workbook.active.append(("MAT-1", "MAT", "Name"))
    workbook.create_sheet("Other")
    output = BytesIO()
    workbook.save(output)
    with pytest.raises(MaterialImportError, match="only the Sheet1"):
        parse_material_workbook(
            output.getvalue(),
            maximum_bytes=5 * 1024 * 1024,
            maximum_rows=10_000,
            maximum_uncompressed_bytes=50 * 1024 * 1024,
        )


@pytest.mark.skipif(
    not REAL_WORKBOOK.exists(), reason="Approved Material Master workbook unavailable"
)
def test_real_workbook_preview_apply_and_idempotency(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id = _identity(app)
    _authenticate(client, user_id, station_id)
    with app.app_context():
        db.session.add_all(
            [
                Material(
                    code="R01034L2",
                    name="Silquest A-1110 (17kg/Pail)",
                    unit="g",
                    classification="SPECIAL",
                    source_category_no="MAT",
                    is_active=False,
                ),
                Material(
                    code="R01038L1",
                    name="Stale Name",
                    unit="lb",
                    classification="PRESERVE",
                    source_category_no="OLD",
                    is_active=False,
                ),
            ]
        )
        db.session.commit()

    response = _upload(client, REAL_WORKBOOK.read_bytes())
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/master-data/material-import/1")
    preview = client.get(response.headers["Location"])
    assert preview.status_code == 200
    assert b"PG740" in preview.data

    with app.app_context():
        batch = MaterialImportBatch.query.one()
        assert (batch.total_rows, batch.inserted_count, batch.updated_count) == (329, 327, 1)
        assert (batch.unchanged_count, batch.rejected_count) == (1, 0)
        pg740 = MaterialImportRow.query.filter_by(name_normalized="PG740").one()
        assert pg740.name_normalized == "PG740"
        assert len({row.item_code_normalized for row in batch.rows}) == 329
        assert AuditLog.query.filter_by(event_type="MATERIAL_IMPORT_PREVIEWED").count() == 1

    applied = client.post("/master-data/material-import/1/apply", follow_redirects=True)
    assert applied.status_code == 200
    assert b"Material Master import applied successfully" in applied.data
    with app.app_context():
        assert Material.query.count() == 329
        updated = Material.query.filter_by(code="R01038L1").one()
        assert updated.name != "Stale Name"
        assert (updated.unit, updated.classification, updated.is_active) == (
            "lb",
            "PRESERVE",
            False,
        )
        unchanged = Material.query.filter_by(code="R01034L2").one()
        assert (unchanged.unit, unchanged.classification, unchanged.is_active) == (
            "g",
            "SPECIAL",
            False,
        )
        assert MaterialImportBatch.query.one().status == "APPLIED"
        assert AuditLog.query.filter_by(event_type="MATERIAL_IMPORT_APPLIED").count() == 1
        assert MaterialTagDraft.query.count() == 0
        assert MaterialTagBatch.query.count() == 0
        assert MaterialTag.query.count() == 0

    repeated = client.post("/master-data/material-import/1/apply")
    assert repeated.status_code == 302
    with app.app_context():
        assert Material.query.count() == 329
        assert AuditLog.query.filter_by(event_type="MATERIAL_IMPORT_APPLIED").count() == 1


def test_same_upload_idempotency_key_reuses_persistent_preview(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id = _identity(app)
    _authenticate(client, user_id, station_id)
    workbook = _workbook_bytes([("MAT-1", "MAT", "Material One")])
    first = _upload(client, workbook)
    second = _upload(client, workbook)
    assert first.headers["Location"] == second.headers["Location"]
    with app.app_context():
        assert MaterialImportBatch.query.count() == 1
        assert MaterialImportRow.query.count() == 1
        assert AuditLog.query.filter_by(event_type="MATERIAL_IMPORT_PREVIEWED").count() == 1
