import html
import json
import re
from pathlib import Path

from app.extensions import db
from app.models import WeighingTransaction
from tests.test_material_workflow import (
    MATERIAL_A_TAG,
    login,
    prepare_orders,
    seed_material_workflow,
)


def _material_queue_page(app, client):
    with app.app_context():
        user, station, _, _, _, orders, _, _ = seed_material_workflow(1)
        prepare_orders(user, station, orders)
        station_id = station.id
    login(client, station_id)
    client.get("/weighing/material?material=MAT-A")
    response = client.post(
        "/weighing/material/validate",
        json={"material_tag": MATERIAL_A_TAG, "selected_material_code": "MAT-A"},
    )
    assert response.get_json()["result"] == "MATCH"
    return client.get("/weighing/material")


def test_material_queue_uses_read_only_bridge_weight_and_bilingual_status(app, client):
    page = _material_queue_page(app, client)
    rendered = page.get_data(as_text=True)

    assert page.status_code == 200
    assert 'data-base-url="http://127.0.0.1:8765"' in rendered
    assert 'name="actual_weight" type="text" inputmode="none" readonly' in rendered
    assert 'aria-readonly="true"' in rendered
    assert "บันทึกน้ำหนักภาชนะ / Tare" in rendered
    assert "สถานะเครื่องชั่ง / Scale status" in rendered
    messages_match = re.search(r"data-messages='([^']+)'", rendered)
    assert messages_match is not None
    messages = json.loads(html.unescape(messages_match.group(1)))
    assert messages["connected"] == "เชื่อมต่อเครื่องชั่งแล้ว / Scale connected"
    assert messages["disconnected"] == "ไม่ได้เชื่อมต่อเครื่องชั่ง / Scale disconnected"
    assert messages["stable"] == "คงที่ / Stable"
    assert messages["unstable"] == "ไม่คงที่ / Unstable"
    assert "น้ำหนักรวม / Gross Weight" in rendered
    assert "น้ำหนักภาชนะ / Tare Weight" in rendered
    assert "น้ำหนักจริง / Actual Weight" in rendered
    assert messages["READING_STALE"] == "ค่าน้ำหนักเก่าเกินกำหนด / Scale reading is stale"
    assert messages["OVERLOAD"] == "เครื่องชั่งน้ำหนักเกิน / Scale overload"
    assert messages["NOT_DECODED"] == "รูปแบบค่าน้ำหนักไม่ถูกต้อง / Malformed scale reading"


def test_material_queue_sends_exact_context_and_keeps_save_gated(app, client):
    page = _material_queue_page(app, client)
    rendered = page.get_data(as_text=True)

    assert 'data-material="MAT-A"' in rendered
    assert 'data-production-order="PD001"' in rendered
    assert 'data-formula-item="1"' in rendered
    assert 'data-station="POWDER-ST"' in rendered
    assert 'class="btn btn-primary save-weighing" type="submit" disabled' in rendered

    script = Path("app/static/weighing_scale_bridge.js").read_text(encoding="utf-8")
    assert 'bridgeRequest("/context", {method: "POST"' in script
    assert 'bridgeRequest("/tare/capture", {method: "POST"' in script
    assert 'bridgeRequest("/status")' in script
    assert "contextsMatch(context, state.context)" in script
    assert "state.save_block_reason" in script
    assert "HTMLFormElement.prototype.submit.call(form)" in script
    assert "state.actual" in script


def test_bridge_ui_gets_do_not_create_weighing_data(app, client):
    _material_queue_page(app, client)
    client.get("/weighing/material")
    client.get("/weighing/material")

    with app.app_context():
        assert db.session.query(WeighingTransaction).count() == 0


def test_scale_bridge_adapter_exposes_no_physical_scale_control_surface():
    script = Path("app/static/weighing_scale_bridge.js").read_text(encoding="utf-8")
    api = Path("scale_bridge/api.py").read_text(encoding="utf-8")
    combined = f"{script}\n{api}".lower()

    assert "/serial/write" not in combined
    assert "/zero" not in combined
    assert "/calibration" not in combined
    assert "/reset" not in combined
    serial_source = Path("scale_bridge/serial_source.py").read_text(encoding="utf-8")
    assert ".write(" not in serial_source
    assert set(path for path in ("/context", "/tare/capture", "/tare/clear") if path in api) == {
        "/context",
        "/tare/capture",
        "/tare/clear",
    }
