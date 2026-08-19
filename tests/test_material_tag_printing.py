import base64
from io import BytesIO

import pytest
from PIL import Image
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    AuditLog,
    Material,
    MaterialTag,
    MaterialTagBatch,
    MaterialTagPrintEvent,
    Role,
    Station,
    User,
    WeighingTransaction,
)
from app.services.material_tag_issuance import (
    MaterialTagIssuanceError,
    create_material_tag_draft,
    create_print_event,
    issue_material_tag_draft,
    material_tag_qr_data_uri,
)
from app.services.weighing import parse_material_tag


def setup_batch(app, *, total="200.000", standard="25.000", name="PG740", suffix="one"):
    with app.app_context():
        role = Role.query.filter_by(code="SUPERVISOR").one_or_none()
        if role is None:
            role = Role(code="SUPERVISOR", name="Supervisor")
        user = User(
            username=f"printer-{suffix}",
            password_hash=generate_password_hash("test"),
            display_name="Print Supervisor",
            roles=[role],
        )
        station = Station(code=f"PRINT-{suffix}", name="Print Station")
        material = Material(
            code=f"R-{suffix}",
            name=name,
            unit="kg",
            source_category_no="MAT",
            is_active=True,
        )
        db.session.add_all([user, station, material])
        db.session.commit()
        draft = create_material_tag_draft(
            values={
                "material_id": material.id,
                "receiving_date": "05/08/2026",
                "purchase_order": f"PO-{suffix}",
                "purchase_order_line": "10",
                "delivery_invoice": f"INV-{suffix}",
                "vendor_lot": f"LOT-{suffix}",
                "supplier": "Supplier",
                "comment": "Isolated",
                "warehouse": "WH",
                "location": "LOC",
                "shelf": "SHELF",
                "total_received_weight": total,
                "standard_container_weight": standard,
            },
            user_id=user.id,
            station_id=station.id,
        )
        batch = issue_material_tag_draft(
            token=draft.draft_token, user_id=user.id, station_id=station.id
        )
        return user.id, station.id, batch.id


def authenticate(client, user_id, station_id):
    with client.session_transaction() as user_session:
        user_session["_user_id"] = str(user_id)
        user_session["_fresh"] = True
        user_session["station_id"] = station_id


def test_stage_d_routes_feature_disabled_without_new_table_queries(app, client):
    user_id, station_id, batch_id = setup_batch(app)
    authenticate(client, user_id, station_id)
    with app.app_context():
        MaterialTagPrintEvent.__table__.drop(db.engine)
    for method, path in (
        (client.post, f"/material-tags/batches/{batch_id}/print"),
        (client.post, f"/material-tags/batches/{batch_id}/reprint"),
        (client.post, f"/material-tags/batches/{batch_id}/tags/1/reprint"),
        (client.get, "/material-tags/print-events/1/view"),
        (client.get, "/material-tags/history"),
        (client.get, "/material-tags/calibration"),
    ):
        assert method(path).status_code == 404


@pytest.mark.parametrize("role_code", ["OPERATOR", "PRODUCTION"])
def test_stage_d_routes_reject_unapproved_roles(app, client, role_code):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id, batch_id = setup_batch(app)
    with app.app_context():
        role = Role.query.filter_by(code="SUPERVISOR").one()
        role.code = role_code
        db.session.commit()
    authenticate(client, user_id, station_id)
    for method, path in (
        (client.get, "/material-tags/history"),
        (client.get, "/material-tags/calibration"),
        (client.post, f"/material-tags/batches/{batch_id}/print"),
        (client.get, "/material-tags/print-events/1/view"),
    ):
        assert method(path).status_code == 403


def test_stage_d_routes_require_authentication_and_station(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    assert client.get("/material-tags/history").status_code == 302
    setup_batch(app)
    client.post("/auth/login", data={"username": "printer-one", "password": "test"})
    response = client.get("/material-tags/calibration")
    assert response.status_code == 302 and "/auth/station" in response.headers["Location"]


def test_original_post_event_print_pages_refresh_safe_and_no_mutation(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id, batch_id = setup_batch(app)
    authenticate(client, user_id, station_id)
    response = client.post(f"/material-tags/batches/{batch_id}/print")
    assert response.status_code == 302
    view = client.get(response.headers["Location"])
    assert view.status_code == 200
    assert view.data.count(b'class="material-tag"') == 8
    assert b"Tag 1 of 8" in view.data and b"Tag 8 of 8" in view.data
    assert b"25.00 kg" in view.data
    assert b"window.print" in view.data and b">Print<" in view.data
    client.get(response.headers["Location"])
    with app.app_context():
        event = MaterialTagPrintEvent.query.one()
        assert (event.print_scope, event.print_type, event.result) == (
            "BATCH",
            "ORIGINAL",
            "RENDERED",
        )
        assert AuditLog.query.filter_by(event_type="MATERIAL_TAG_BATCH_PRINT_RENDERED").count() == 1
        assert WeighingTransaction.query.count() == 0


@pytest.mark.parametrize("reason", [None, "", "short", "x" * 501, "valid reason\nunsafe"])
def test_reprint_reason_validation(app, reason):
    user_id, station_id, batch_id = setup_batch(app)
    with app.app_context(), pytest.raises(MaterialTagIssuanceError):
        create_print_event(
            batch_id=batch_id,
            user_id=user_id,
            station_id=station_id,
            print_type="REPRINT",
            reason=reason,
        )


def test_batch_and_individual_reprint_event_semantics(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id, batch_id = setup_batch(app, total="210.000")
    authenticate(client, user_id, station_id)
    client.post(f"/material-tags/batches/{batch_id}/print")
    batch_reprint = client.post(
        f"/material-tags/batches/{batch_id}/reprint",
        data={"reason": "Damaged receiving label"},
    )
    with app.app_context():
        tag_id = MaterialTag.query.filter_by(batch_id=batch_id, sequence_no=9).one().id
    individual = client.post(
        f"/material-tags/batches/{batch_id}/tags/{tag_id}/reprint",
        data={"reason": "Container label damaged"},
    )
    assert batch_reprint.status_code == individual.status_code == 302
    assert client.get(batch_reprint.headers["Location"]).data.count(b'class="material-tag"') == 9
    individual_view = client.get(individual.headers["Location"])
    assert individual_view.data.count(b'class="material-tag"') == 1
    assert b"Tag 9 of 9" in individual_view.data and b"10.00 kg" in individual_view.data
    with app.app_context():
        events = MaterialTagPrintEvent.query.order_by(MaterialTagPrintEvent.id).all()
        assert [(e.print_scope, e.print_type, e.material_tag_id) for e in events] == [
            ("BATCH", "ORIGINAL", None),
            ("BATCH", "REPRINT", None),
            ("INDIVIDUAL", "REPRINT", tag_id),
        ]
        assert AuditLog.query.filter_by(event_type="MATERIAL_TAG_REPRINT_RENDERED").count() == 2


def test_cross_batch_and_unknown_tag_rejected(app):
    user_id, station_id, first_id = setup_batch(app, suffix="one")
    _other_user, _other_station, second_id = setup_batch(app, suffix="two")
    with app.app_context():
        foreign_tag = MaterialTag.query.filter_by(batch_id=second_id).first()
        for tag_id in (foreign_tag.id, 999999):
            with pytest.raises(MaterialTagIssuanceError, match="does not belong"):
                create_print_event(
                    batch_id=first_id,
                    tag_id=tag_id,
                    user_id=user_id,
                    station_id=station_id,
                    print_type="REPRINT",
                    scope="INDIVIDUAL",
                    reason="Approved isolated reprint",
                )


def test_qr_is_deterministic_has_quiet_zone_and_stored_payload_only(app):
    _user_id, _station_id, batch_id = setup_batch(app, total="210.000")
    with app.app_context():
        batch = db.session.get(MaterialTagBatch, batch_id)
        first = material_tag_qr_data_uri(batch.qr_payload)
        second = material_tag_qr_data_uri(batch.qr_payload)
        assert first == second
        assert parse_material_tag(batch.qr_payload).raw_payload == batch.qr_payload
        assert all(value not in batch.qr_payload for value in ("PG740", "210.000", "Tag 9"))
        image = Image.open(BytesIO(base64.b64decode(first.split(",", 1)[1]))).convert("1")
        assert image.getpixel((0, 0)) == 255
        assert image.getpixel((image.width - 1, image.height - 1)) == 255


def test_render_failure_is_sanitized_and_audited(app):
    user_id, station_id, batch_id = setup_batch(app)
    with app.app_context():
        batch = db.session.get(MaterialTagBatch, batch_id)
        batch.qr_payload = "invalid"
        db.session.commit()
        with pytest.raises(MaterialTagIssuanceError, match="failed safely"):
            create_print_event(
                batch_id=batch_id,
                user_id=user_id,
                station_id=station_id,
                print_type="ORIGINAL",
            )
        event = MaterialTagPrintEvent.query.one()
        assert event.result == "FAILED"
        assert event.error_message == "Stored QR payload could not be rendered."
        assert AuditLog.query.filter_by(event_type="MATERIAL_TAG_PRINT_FAILED").count() == 1


def test_detail_original_then_reprint_controls_and_print_history(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id, batch_id = setup_batch(app)
    authenticate(client, user_id, station_id)
    before = client.get(f"/material-tags/batches/{batch_id}")
    assert b"Print Batch" in before.data and b"Reprint Batch" not in before.data
    client.post(f"/material-tags/batches/{batch_id}/print")
    after = client.get(f"/material-tags/batches/{batch_id}")
    assert b"Reprint Batch" in after.data and b"Print page rendered" in after.data
    assert b"Reprint Tag 1" in after.data
    assert after.data.count(b">Reprint reason</label>") == 9
    assert after.data.count(b'placeholder="Enter reason (10') == 9
    assert after.data.count(b'<input class="form-control form-control-sm"') == 8
    assert b"stored in print history" in after.data
    assert b"Thailand Time) Thailand Time" not in after.data
    with app.app_context():
        tag_ids = [tag.id for tag in MaterialTag.query.filter_by(batch_id=batch_id).all()]
    for tag_id in tag_ids:
        field_id = f"tag-reprint-reason-{tag_id}".encode()
        assert b'for="' + field_id + b'"' in after.data
        assert b'id="' + field_id + b'"' in after.data
    for forbidden in (b"Delete", b"Void", b"Cancel", b"Edit Weight"):
        assert forbidden not in after.data


def test_history_filters_order_counts_and_invalid_dates(app, client):
    app.config.update(MATERIAL_TAG_ISSUANCE_ENABLED=True, MATERIAL_TAG_HISTORY_PAGE_SIZE=1)
    user_id, station_id, first_id = setup_batch(app, suffix="alpha")
    authenticate(client, user_id, station_id)
    client.post(f"/material-tags/batches/{first_id}/print")
    _u2, _s2, _second_id = setup_batch(app, suffix="beta", name="Duplicate Name")
    response = client.get("/material-tags/history?material_code=R-alpha")
    assert b"R-alpha" in response.data and b"R-beta" not in response.data
    assert b"Original rendered" in response.data
    assert client.get("/material-tags/history?date_from=invalid").status_code == 400
    bounded = client.get(
        "/material-tags/history?date_from=05/08/2026&date_to=05/08/2026&material_code=R-alpha"
    )
    assert bounded.status_code == 200 and b"R-alpha" in bounded.data
    assert b'value="05/08/2026"' in bounded.data
    assert b'placeholder="dd/mm/yyyy"' in bounded.data
    paged_filter = client.get(
        "/material-tags/history?date_from=05/08/2026&date_to=05/08/2026"
    )
    assert b"date_from=05/08/2026" in paged_filter.data
    assert b"date_to=05/08/2026" in paged_filter.data
    page = client.get("/material-tags/history")
    assert b"Page 1 of 2" in page.data


def test_calibration_and_label_physical_css_no_business_mutation(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id, batch_id = setup_batch(app)
    authenticate(client, user_id, station_id)
    calibration = client.get("/material-tags/calibration")
    assert b"76.2" in calibration.data and b"SAFE AREA" in calibration.data
    assert b"non-production" in calibration.data.lower()
    response = client.post(f"/material-tags/batches/{batch_id}/print")
    print_page = client.get(response.headers["Location"])
    for expected in (
        b"@page{size:3in 2.5in;margin:0}",
        b"MATERIAL TAG",
        b"Sunstar Chemical",
        b"Vendor Lot:",
        "ป้ายแสดงการรับและตรวจสอบวัตถุดิบ".encode(),
        "QC ตรวจสอบผ่าน".encode(),
        b"page-break-after:always",
    ):
        assert expected in print_page.data
    assert b">Lot:</b>" not in print_page.data
    with app.app_context():
        assert MaterialTagBatch.query.count() == 1
        assert MaterialTag.query.count() == 8


def test_longest_real_name_renders_without_rejection(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    longest = "Basic Calcium Petronate (Lobase C-4501J)Use R03047L1*change to R03047"
    user_id, station_id, batch_id = setup_batch(app, name=longest)
    authenticate(client, user_id, station_id)
    response = client.post(f"/material-tags/batches/{batch_id}/print")
    page = client.get(response.headers["Location"])
    assert longest.encode() in page.data


def test_two_hundred_tag_print_view_is_complete_and_ordered(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id, batch_id = setup_batch(app, standard="1.000")
    authenticate(client, user_id, station_id)
    response = client.post(f"/material-tags/batches/{batch_id}/print")
    page = client.get(response.headers["Location"])
    assert page.data.count(b'class="material-tag"') == 200
    assert page.data.index(b"Tag 1 of 200") < page.data.index(b"Tag 200 of 200")


def test_print_routes_require_csrf_when_enabled(app, client):
    app.config.update(MATERIAL_TAG_ISSUANCE_ENABLED=True, WTF_CSRF_ENABLED=True)
    user_id, station_id, batch_id = setup_batch(app)
    authenticate(client, user_id, station_id)
    assert client.post(f"/material-tags/batches/{batch_id}/print").status_code == 400


@pytest.mark.parametrize("reason", ["", "short", "x" * 501, "valid reason\nunsafe"])
def test_failed_reprint_post_renders_accessible_error_without_event(app, client, reason):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id, batch_id = setup_batch(app)
    authenticate(client, user_id, station_id)
    client.post(f"/material-tags/batches/{batch_id}/print")
    with app.app_context():
        tag_id = MaterialTag.query.filter_by(batch_id=batch_id, sequence_no=1).one().id
        before = MaterialTagPrintEvent.query.count()
    response = client.post(
        f"/material-tags/batches/{batch_id}/tags/{tag_id}/reprint",
        data={"reason": reason},
    )
    assert response.status_code == 400
    assert b'aria-invalid="true"' in response.data
    assert b'role="alert"' in response.data
    assert reason.strip().encode() in response.data
    with app.app_context():
        assert MaterialTagPrintEvent.query.count() == before


def test_failed_batch_reprint_preserves_reason_without_event(app, client):
    app.config["MATERIAL_TAG_ISSUANCE_ENABLED"] = True
    user_id, station_id, batch_id = setup_batch(app)
    authenticate(client, user_id, station_id)
    client.post(f"/material-tags/batches/{batch_id}/print")
    with app.app_context():
        before = MaterialTagPrintEvent.query.count()
    response = client.post(
        f"/material-tags/batches/{batch_id}/reprint", data={"reason": "short"}
    )
    assert response.status_code == 400
    assert b'id="batch-reprint-reason"' in response.data
    assert b'aria-invalid="true"' in response.data
    assert b">short</textarea>" in response.data
    with app.app_context():
        assert MaterialTagPrintEvent.query.count() == before
