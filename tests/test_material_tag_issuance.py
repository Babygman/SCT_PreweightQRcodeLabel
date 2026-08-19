import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.dialects import mssql
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    AuditLog,
    Material,
    MaterialTag,
    MaterialTagBatch,
    MaterialTagDraft,
    MaterialTagPrintEvent,
    Role,
    Station,
    User,
    WeighingTransaction,
    utcnow,
)
from app.services.material_import import apply_material_import, create_material_import_preview
from app.services.material_tag_issuance import (
    MaterialTagIssuanceError,
    _draft_for_issue_statement,
    create_material_tag_draft,
    issue_material_tag_draft,
)
from app.services.weighing import parse_material_tag

REAL_WORKBOOK = Path("/Users/rachin/Downloads/Material code.xlsx")


def identity(app, role_code="SUPERVISOR", suffix="one"):
    with app.app_context():
        role = Role(code=f"{role_code}-{suffix}", name=role_code)
        user = User(
            username=f"{role_code.lower()}-{suffix}",
            password_hash=generate_password_hash("test"),
            display_name=f"{role_code} {suffix}",
            roles=[role],
        )
        # Decorator checks exact role codes, while distinct users may share one role.
        role.code = role_code
        station = Station(code=f"ST-{suffix}", name="Station")
        db.session.add_all([role, user, station])
        db.session.commit()
        return user.id, station.id


def authenticate(client, user_id, station_id=None):
    with client.session_transaction() as user_session:
        user_session["_user_id"] = str(user_id)
        user_session["_fresh"] = True
        if station_id:
            user_session["station_id"] = station_id


def add_material(app, code="R07047S1", name="PG740", active=True):
    with app.app_context():
        material = Material(
            code=code,
            name=name,
            unit="kg",
            source_category_no="MAT",
            classification="GENERAL",
            is_active=active,
        )
        db.session.add(material)
        db.session.commit()
        return material.id


def values(material_id, **updates):
    result = {
        "material_id": str(material_id),
        "receiving_date": "05/08/2026",
        "purchase_order": " ISO-UAT-PO ",
        "purchase_order_line": " 10 ",
        "delivery_invoice": " ISO-UAT-INV ",
        "vendor_lot": " ISO-UAT-LOT ",
        "supplier": " Isolated Supplier ",
        "comment": " Isolated only ",
        "warehouse": " WH-UAT ",
        "location": " LOC-UAT ",
        "shelf": " S-UAT ",
        "total_received_weight": "200.000",
        "standard_container_weight": "25.000",
    }
    result.update(updates)
    return result


def create_draft(app, material_id, user_id, station_id, **updates):
    with app.app_context():
        return create_material_tag_draft(
            values=values(material_id, **updates),
            user_id=user_id,
            station_id=station_id,
        ).draft_token


def test_feature_gate_returns_404_without_querying_stage_tables(app, client):
    user_id, station_id = identity(app)
    authenticate(client, user_id, station_id)
    with app.app_context():
        MaterialTagDraft.__table__.drop(db.engine)
    for method, path in (
        (client.get, "/material-tags/"),
        (client.get, "/material-tags/new"),
        (client.get, "/material-tags/materials/search"),
        (client.get, "/material-tags/drafts/nope/preview"),
        (client.post, "/material-tags/drafts/nope/confirm"),
        (client.get, "/material-tags/batches/1"),
    ):
        assert method(path).status_code == 404
    assert b"Material Tag Issuance" not in client.get("/").data


def test_sql_server_draft_lock_uses_update_and_hold_lock():
    sql = str(_draft_for_issue_statement("token").compile(dialect=mssql.dialect()))
    assert "WITH (UPDLOCK, HOLDLOCK)" in sql


@pytest.mark.parametrize("role", ["SUPERVISOR", "ADMIN"])
def test_approved_roles_can_access_with_station(app, client, role):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id = identity(app, role)
    authenticate(client, user_id, station_id)
    assert client.get("/material-tags/new").status_code == 200
    home = client.get("/")
    assert b"Material Tag Issuance" in home.data
    assert b"Production Weighing" in home.data
    assert b"Material Tag Management" in home.data


@pytest.mark.parametrize("role", ["OPERATOR", "PRODUCTION"])
def test_unapproved_roles_denied_direct_urls_and_navigation(app, client, role):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id = identity(app, role)
    authenticate(client, user_id, station_id)
    assert client.get("/material-tags/new").status_code == 403
    assert b"Material Tag Issuance" not in client.get("/").data


def test_requires_authentication_and_station(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    assert client.get("/material-tags/new").status_code == 302
    identity(app)
    client.post("/auth/login", data={"username": "supervisor-one", "password": "test"})
    response = client.get("/material-tags/new")
    assert response.status_code == 302
    assert "/auth/station" in response.headers["Location"]


def test_material_search_code_name_order_pagination_and_inactive(app, client):
    app.config.update(MATERIAL_TAG_ISSUANCE_ENABLED=True, MATERIAL_TAG_SEARCH_PAGE_SIZE=2)
    user_id, station_id = identity(app)
    add_material(app, "B-002", "Duplicate")
    add_material(app, "A-001", "Duplicate")
    add_material(app, "C-003", "Other")
    add_material(app, "D-004", "Hidden", False)
    authenticate(client, user_id, station_id)
    response = client.get("/material-tags/materials/search?q=duplicate")
    assert response.status_code == 200
    assert response.data.index(b"A-001") < response.data.index(b"B-002")
    assert b"D-004" not in response.data
    page = client.get("/material-tags/materials/search?page=2")
    assert b"Page 2 of 2" in page.data


@pytest.mark.parametrize(
    "updates",
    [
        {"purchase_order": " "},
        {"vendor_lot": "bad|lot"},
        {"supplier": "bad\nvalue"},
        {"receiving_date": "not-a-date"},
        {"receiving_date": "31/12/1999"},
        {"total_received_weight": "1.0001"},
        {"total_received_weight": "0"},
        {"total_received_weight": "NaN"},
        {"total_received_weight": "201", "standard_container_weight": "1"},
    ],
)
def test_server_rejects_invalid_form_values(app, updates):
    user_id, station_id = identity(app)
    material_id = add_material(app)
    with app.app_context(), pytest.raises(MaterialTagIssuanceError):
        create_material_tag_draft(
            values=values(material_id, **updates), user_id=user_id, station_id=station_id
        )


def test_inactive_and_unknown_material_rejected(app):
    user_id, station_id = identity(app)
    inactive_id = add_material(app, active=False)
    with app.app_context():
        for material_id in (inactive_id, 999999):
            with pytest.raises(MaterialTagIssuanceError, match="active Material"):
                create_material_tag_draft(
                    values=values(material_id), user_id=user_id, station_id=station_id
                )


def test_draft_is_persistent_normalized_audited_and_creates_no_issued_records(app):
    user_id, station_id = identity(app)
    material_id = add_material(app)
    token = create_draft(app, material_id, user_id, station_id)
    with app.app_context():
        draft = MaterialTagDraft.query.filter_by(draft_token=token).one()
        assert draft.status == "PREVIEWED"
        assert draft.purchase_order == "ISO-UAT-PO"
        assert draft.calculated_tag_count == 8
        assert json.loads(draft.calculated_weights_json) == ["25.000"] * 8
        assert draft.expires_at_utc - draft.created_at_utc == timedelta(minutes=60)
        assert MaterialTagBatch.query.count() == MaterialTag.query.count() == 0
        assert MaterialTagPrintEvent.query.count() == WeighingTransaction.query.count() == 0
        assert AuditLog.query.one().event_type == "MATERIAL_TAG_PREVIEWED"


def test_preview_content_and_no_print_controls(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id = identity(app)
    token = create_draft(app, add_material(app), user_id, station_id)
    authenticate(client, user_id, station_id)
    response = client.get(f"/material-tags/drafts/{token}/preview")
    for expected in (
        b"PG740",
        b"04/02/2027",
        b"Tag 8 of 8",
        b"200.000 = 200.000",
        b"share the same QR payload",
        b"become immutable",
        b"Thailand Time",
    ):
        assert expected in response.data
    assert b"Print" not in response.data and b"Reprint" not in response.data


def test_route_creates_preview_confirms_once_and_redirects_repeat(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id = identity(app)
    material_id = add_material(app)
    authenticate(client, user_id, station_id)
    response = client.post("/material-tags/new", data=values(material_id))
    assert response.status_code == 302
    preview_url = response.headers["Location"]
    assert "/material-tags/drafts/" in preview_url
    assert client.get(preview_url).status_code == 200
    assert client.get(preview_url.replace("/preview", "/confirm")).status_code == 405
    confirmed = client.post(preview_url.replace("/preview", "/confirm"))
    assert (
        confirmed.status_code == 302 and "/material-tags/batches/" in confirmed.headers["Location"]
    )
    repeated = client.post(preview_url.replace("/preview", "/confirm"))
    assert repeated.status_code == 302
    with app.app_context():
        assert MaterialTagBatch.query.count() == 1
        assert MaterialTag.query.count() == 8


def test_receiving_date_field_is_strict_and_preserves_invalid_input(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id = identity(app)
    material_id = add_material(app)
    authenticate(client, user_id, station_id)
    response = client.post(
        "/material-tags/new", data=values(material_id, receiving_date="31/04/2026")
    )
    assert response.status_code == 200
    assert b"Enter a valid date in dd/mm/yyyy format" in response.data
    assert b'value="31/04/2026"' in response.data
    with app.app_context():
        assert MaterialTagDraft.query.count() == 0


def test_large_preview_warning_and_two_hundred_rows(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id = identity(app)
    token = create_draft(
        app,
        add_material(app),
        user_id,
        station_id,
        total_received_weight="200.000",
        standard_container_weight="1.000",
    )
    authenticate(client, user_id, station_id)
    response = client.get(f"/material-tags/drafts/{token}/preview")
    assert b"Large issuance" in response.data
    assert b"Tag 200 of 200" in response.data
    assert b"max-height: 24rem; overflow-y: auto" in response.data


def test_issue_exact_batch_snapshot_children_qr_audit_and_idempotency(app):
    user_id, station_id = identity(app)
    material_id = add_material(app)
    token = create_draft(app, material_id, user_id, station_id, total_received_weight="210.000")
    with app.app_context():
        batch = issue_material_tag_draft(token=token, user_id=user_id, station_id=station_id)
        first_id = batch.id
        assert batch.batch_no.startswith("MTB-") and len(batch.batch_no) == 19
        assert (batch.material_code_snapshot, batch.material_name_snapshot) == ("R07047S1", "PG740")
        assert batch.expiry_date.isoformat() == "2027-02-04"
        assert batch.tag_count == 9
        assert [tag.sequence_no for tag in batch.tags] == list(range(1, 10))
        assert [tag.container_weight for tag in batch.tags] == [Decimal("25.000")] * 8 + [
            Decimal("10.000")
        ]
        assert sum((tag.container_weight for tag in batch.tags), Decimal("0")) == Decimal("210.000")
        assert len(batch.qr_payload.split("|")) == 11
        assert parse_material_tag(batch.qr_payload).material_code == "R07047S1"
        assert "210.000" not in batch.qr_payload and "2027" not in batch.qr_payload
        again = issue_material_tag_draft(token=token, user_id=user_id, station_id=station_id)
        assert again.id == first_id
        assert MaterialTagBatch.query.count() == 1
        assert MaterialTag.query.count() == 9
        assert AuditLog.query.filter_by(event_type="MATERIAL_TAG_BATCH_ISSUED").count() == 1
        assert MaterialTagPrintEvent.query.count() == WeighingTransaction.query.count() == 0


def test_ownership_expiry_inactive_and_tamper_prevent_issuance(app):
    user_id, station_id = identity(app)
    material_id = add_material(app)
    token = create_draft(app, material_id, user_id, station_id)
    with app.app_context():
        with pytest.raises(MaterialTagIssuanceError, match="creator"):
            issue_material_tag_draft(token=token, user_id=user_id + 1, station_id=station_id)
        draft = MaterialTagDraft.query.filter_by(draft_token=token).one()
        draft.calculated_weights_json = '["199.999"]'
        db.session.commit()
        with pytest.raises(MaterialTagIssuanceError, match="integrity"):
            issue_material_tag_draft(token=token, user_id=user_id, station_id=station_id)

    expiry_token = create_draft(app, material_id, user_id, station_id)
    with app.app_context():
        draft = MaterialTagDraft.query.filter_by(draft_token=expiry_token).one()
        draft.expires_at_utc = utcnow() - timedelta(seconds=1)
        db.session.commit()
        with pytest.raises(MaterialTagIssuanceError, match="expired"):
            issue_material_tag_draft(token=expiry_token, user_id=user_id, station_id=station_id)
        assert MaterialTagBatch.query.count() == 0
        assert MaterialTagDraft.query.filter_by(draft_token=expiry_token).one().status == "EXPIRED"


def test_child_failure_rolls_back_entire_issuance(app, monkeypatch):
    user_id, station_id = identity(app)
    token = create_draft(app, add_material(app), user_id, station_id)

    def fail_child(**_kwargs):
        raise RuntimeError("isolated child failure")

    monkeypatch.setattr("app.services.material_tag_issuance.MaterialTag", fail_child)
    with app.app_context():
        with pytest.raises(MaterialTagIssuanceError, match="failed safely"):
            issue_material_tag_draft(token=token, user_id=user_id, station_id=station_id)
        assert MaterialTagBatch.query.count() == MaterialTag.query.count() == 0
        assert MaterialTagDraft.query.one().status == "PREVIEWED"
        assert AuditLog.query.filter_by(event_type="MATERIAL_TAG_BATCH_ISSUED").count() == 0


def test_batch_number_collision_retries_safely(app, monkeypatch):
    user_id, station_id = identity(app)
    material_id = add_material(app)
    first_token = create_draft(app, material_id, user_id, station_id)
    second_token = create_draft(
        app, material_id, user_id, station_id, vendor_lot="ISO-UAT-LOT-SECOND"
    )
    with app.app_context():
        first = issue_material_tag_draft(token=first_token, user_id=user_id, station_id=station_id)
        candidates = iter((first.batch_no, "MTB-20260818-999999"))
        monkeypatch.setattr(
            "app.services.material_tag_issuance._next_batch_number", lambda: next(candidates)
        )
        second = issue_material_tag_draft(
            token=second_token, user_id=user_id, station_id=station_id
        )
        assert second.batch_no == "MTB-20260818-999999"
        assert MaterialTagBatch.query.count() == 2


def test_issued_detail_is_read_only_and_contains_children(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id = identity(app, "ADMIN")
    token = create_draft(app, add_material(app), user_id, station_id)
    with app.app_context():
        batch_id = issue_material_tag_draft(token=token, user_id=user_id, station_id=station_id).id
    authenticate(client, user_id, station_id)
    response = client.get(f"/material-tags/batches/{batch_id}")
    assert response.status_code == 200
    assert b"Issued data is immutable" in response.data
    assert b"Print Batch" in response.data
    assert b"Tag 8 of 8" in response.data
    assert b"200.000 = 200.000" in response.data
    assert b"ST-one" in response.data
    assert b"Reprint Tag 1" in response.data


def test_mutations_require_csrf_when_enabled(app, client):
    app.config.update(MATERIAL_TAG_ISSUANCE_ENABLED=True, WTF_CSRF_ENABLED=True)
    user_id, station_id = identity(app)
    material_id = add_material(app)
    authenticate(client, user_id, station_id)
    assert client.post("/material-tags/new", data=values(material_id)).status_code == 400
    assert client.post("/material-tags/drafts/nope/confirm").status_code == 400


@pytest.mark.skipif(not REAL_WORKBOOK.exists(), reason="Approved workbook unavailable")
@pytest.mark.parametrize(
    ("total", "expected_weights"),
    [
        ("200.000", [Decimal("25.000")] * 8),
        ("210.000", [Decimal("25.000")] * 8 + [Decimal("10.000")]),
    ],
)
def test_real_pg740_import_draft_and_issuance_isolated(app, total, expected_weights):
    user_id, station_id = identity(app, "ADMIN")
    with app.app_context():
        preview = create_material_import_preview(
            file_bytes=REAL_WORKBOOK.read_bytes(),
            filename=REAL_WORKBOOK.name,
            idempotency_key=f"11111111-1111-4111-8111-{total[:3].replace('.', ''):0>12}",
            user_id=user_id,
            station_id=station_id,
            maximum_bytes=5 * 1024 * 1024,
            maximum_rows=5_000,
            maximum_uncompressed_bytes=50 * 1024 * 1024,
        )
        apply_material_import(batch_id=preview.id, user_id=user_id, station_id=station_id)
        material = Material.query.filter_by(code="R07047S1").one()
        assert material.name == "PG740"
        draft = create_material_tag_draft(
            values=values(material.id, total_received_weight=total),
            user_id=user_id,
            station_id=station_id,
        )
        batch = issue_material_tag_draft(
            token=draft.draft_token, user_id=user_id, station_id=station_id
        )
        assert batch.material_name_snapshot == "PG740"
        assert batch.expiry_date.isoformat() == "2027-02-04"
        assert [tag.container_weight for tag in batch.tags] == expected_weights
        assert sum(expected_weights, Decimal("0")) == Decimal(total)
        parsed = parse_material_tag(batch.qr_payload)
        assert parsed.raw_payload == batch.qr_payload
        assert len(batch.qr_payload.split("|")) == 11
        assert all(
            excluded not in batch.qr_payload for excluded in ("PG740", total, "04/02/2027", "Tag 1")
        )
        assert WeighingTransaction.query.count() == 0
