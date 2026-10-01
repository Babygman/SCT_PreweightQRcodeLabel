import json
from datetime import UTC, datetime
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from scale_bridge.api import LOOPBACK_HOST, create_server
from scale_bridge.identity import ScaleIdentity
from scale_bridge.ids701 import IDS701FrameParser
from scale_bridge.state import ScaleStateEngine

ORIGIN = "http://127.0.0.1:5000"


@pytest.fixture
def running_api():
    now = datetime(2026, 9, 29, 8, 0, tzinfo=UTC)
    engine = ScaleStateEngine(clock=lambda: now)
    engine.connect(
        ScaleIdentity(scale_code="SCALE-01", com_port="COM3", workstation="WEIGH-01")
    )
    engine.ingest(IDS701FrameParser().parse(b"ST,GS,+   0.80kg"), received_at=now)
    server = create_server(
        engine,
        port=0,
        allowed_origins=[ORIGIN],
        diagnostic_configuration={
            "workstation_code": "WEIGH-01",
            "scale_code": "SCALE-01",
            "preferred_usb_serial": "AJ03K7N2A",
            "allowed_origins": [ORIGIN],
        },
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield engine, server.server_address, server
    server.shutdown()
    server.server_close()
    thread.join()


def request(address, path, *, method="GET", origin=None, payload=None):
    headers = {}
    if origin:
        headers["Origin"] = origin
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = Request(
        f"http://{address[0]}:{address[1]}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    with urlopen(req, timeout=2) as response:
        body = response.read()
        return response.status, dict(response.headers), json.loads(body) if body else None


def test_api_binds_loopback_and_exposes_only_reading_state(running_api):
    _engine, address, _server = running_api
    assert address[0] == LOOPBACK_HOST == "127.0.0.1"
    status, headers, health = request(address, "/health", origin=ORIGIN)
    assert status == 200 and health == {"status": "ok"}
    assert headers["Access-Control-Allow-Origin"] == ORIGIN
    assert "*" not in headers["Access-Control-Allow-Origin"]
    _, _, state = request(address, "/status", origin=ORIGIN)
    assert state["connected"] is True
    assert state["gross"] == "0.80"
    assert state["configuration"] == {
        "workstation_code": "WEIGH-01",
        "scale_code": "SCALE-01",
        "preferred_usb_serial": "AJ03K7N2A",
        "allowed_origins": [ORIGIN],
    }
    _, _, capabilities = request(address, "/capabilities", origin=ORIGIN)
    assert capabilities["api_version"] == 2
    assert capabilities["receive_only"] is True
    assert capabilities["serial_write"] is False
    assert capabilities["states"]["READY"] == {
        "th": "พร้อมบันทึก",
        "en": "Ready to save",
    }


def test_status_reports_multiple_scales_as_a_bilingual_controlled_state(running_api):
    engine, address, _server = running_api
    engine.disconnect("MULTIPLE_SCALES")
    _, _, state = request(address, "/status", origin=ORIGIN)
    assert state["connected"] is False
    assert state["user_state"] == {
        "code": "MULTIPLE_SCALES",
        "label_th": "พบเครื่องชั่งหลายเครื่อง",
        "label_en": "Multiple scales detected",
    }


def test_origin_validation_and_no_device_control_endpoint(running_api):
    _engine, address, _server = running_api
    with pytest.raises(HTTPError) as forbidden:
        request(address, "/tare/capture", method="POST", origin="https://evil.example")
    assert forbidden.value.code == 403
    with pytest.raises(HTTPError) as missing_origin:
        request(address, "/tare/capture", method="POST")
    assert missing_origin.value.code == 403
    with pytest.raises(HTTPError) as absent:
        request(address, "/serial/write", method="POST", origin=ORIGIN, payload={"data": "AA"})
    assert absent.value.code == 404


def test_cors_preflight_allows_only_configured_origin(running_api):
    _engine, address, _server = running_api
    status, headers, _body = request(address, "/context", method="OPTIONS", origin=ORIGIN)
    assert status == 204
    assert headers["Access-Control-Allow-Origin"] == ORIGIN
    assert headers["Access-Control-Allow-Methods"] == "GET, POST, OPTIONS"
    assert headers["Access-Control-Allow-Headers"] == "Content-Type"
    with pytest.raises(HTTPError) as forbidden:
        request(address, "/context", method="OPTIONS", origin="https://evil.example")
    assert forbidden.value.code == 403


def test_tare_and_context_api_clear_tare_without_persistence(running_api):
    engine, address, _server = running_api
    status, _, captured = request(address, "/tare/capture", method="POST", origin=ORIGIN)
    assert status == 200 and captured["tare"] == "0.80"
    status, _, changed = request(
        address,
        "/context",
        method="POST",
        origin=ORIGIN,
        payload={"material": "R01006S1", "production_order": "PO-1"},
    )
    assert status == 200
    assert changed["tare"] is None
    assert engine.context.material == "R01006S1"


def test_non_loopback_or_wildcard_configuration_is_rejected():
    engine = ScaleStateEngine()
    with pytest.raises(ValueError, match="explicit non-wildcard"):
        create_server(engine, allowed_origins=["*"])
