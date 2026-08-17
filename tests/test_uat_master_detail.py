from app.extensions import db
from app.models import Formula, ProductionOrder, WeighingTransaction
from app.services.weighing import parse_material_tag
from scripts.uat_master_detail import (
    FORMULA_CODES,
    MATERIAL_CODES,
    PO_CODES,
    UatMasterDetailError,
    generate_master_detail_artifacts,
    material_tag_payload,
    prepare_master_detail_uat,
)


def seed_foundation(app):
    result = app.test_cli_runner().invoke(args=["seed-uat"])
    assert result.exit_code == 0


def test_preparation_is_idempotent_and_creates_exact_empty_work_set(app):
    seed_foundation(app)
    with app.app_context():
        first = prepare_master_detail_uat(uat_enabled=True)
        second = prepare_master_detail_uat(uat_enabled=True)
        assert first.work_set_code == second.work_set_code
        assert [order.po_no for order in first.orders] == list(PO_CODES)
        assert [len(order.formula.items) for order in first.orders] == [10, 1]
        assert all(order.status == "READY" and order.work_set_active for order in first.orders)
        assert WeighingTransaction.query.count() == 0
        assert ProductionOrder.query.filter(ProductionOrder.po_no.in_(PO_CODES)).count() == 2
        assert Formula.query.filter(Formula.code.in_(FORMULA_CODES)).count() == 2


def test_preparation_refuses_production_and_another_active_work_set(app):
    seed_foundation(app)
    with app.app_context():
        try:
            prepare_master_detail_uat(uat_enabled=False)
        except UatMasterDetailError as exc:
            assert "disabled in production" in str(exc)
        else:
            raise AssertionError("Production preparation was not refused")

        station_id = db.session.scalar(
            db.select(ProductionOrder.id).where(ProductionOrder.po_no == "UAT-PO001")
        )
        order = db.session.get(ProductionOrder, station_id)
        from app.models import Station

        station = Station.query.filter_by(code="UAT-ST01").one()
        order.work_set_station_id = station.id
        order.work_set_code = "OTHER-WORK-SET"
        order.work_set_active = True
        db.session.commit()
        try:
            prepare_master_detail_uat(uat_enabled=True)
        except UatMasterDetailError as exc:
            assert "another active Work Set" in str(exc)
        else:
            raise AssertionError("Existing Work Set was not protected")


def test_artifacts_are_idempotent_and_use_real_payload_formats(app, tmp_path):
    first = generate_master_detail_artifacts(tmp_path, uat_enabled=True)
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    second = generate_master_detail_artifacts(tmp_path, uat_enabled=True)
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert first == second == tmp_path / "material-tags" / "index.html"
    assert before == after
    assert len(list((tmp_path / "material-tags").glob("*.png"))) == 10
    assert len(list((tmp_path / "documents").glob("*.png"))) == 4
    assert len(list((tmp_path / "documents").glob("*.html"))) == 4
    for number, code in enumerate(MATERIAL_CODES, start=1):
        parsed = parse_material_tag(material_tag_payload(number))
        assert parsed.material_code == code
        assert parsed.purchase_order_line == str(number * 10)
    try:
        generate_master_detail_artifacts(tmp_path / "production", uat_enabled=False)
    except UatMasterDetailError as exc:
        assert "disabled in production" in str(exc)
    else:
        raise AssertionError("Production artifact generation was not refused")
