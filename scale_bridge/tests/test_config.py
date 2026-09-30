import json
import stat

import pytest

from scale_bridge.config import BridgeConfig, ConfigurationError, load_config, save_config


def valid_config(**changes):
    values = {
        "workstation_code": "WEIGH-01",
        "scale_code": "SCALE-01",
        "allowed_origins": ("https://preweight.example",),
    }
    values.update(changes)
    return BridgeConfig(**values)


def test_machine_configuration_round_trip_contains_only_non_secret_settings(tmp_path):
    path = tmp_path / "config.json"
    save_config(valid_config(preferred_usb_serial="FT-ABC"), path)
    loaded = load_config(path)
    assert loaded.preferred_usb_serial == "FT-ABC"
    assert loaded.baudrate == 9600
    assert (loaded.bytesize, loaded.parity, loaded.stopbits) == (8, "N", 1)
    assert not loaded.xonxoff and not loaded.rtscts and not loaded.dsrdtr
    raw = path.read_text(encoding="utf-8").lower()
    assert not any(word in raw for word in ("password", "cookie", "token", "database_url"))


@pytest.mark.parametrize(
    "changes",
    [
        {"allowed_origins": ()},
        {"allowed_origins": ("*",)},
        {"allowed_origins": ("https://preweight.example/path",)},
        {"baudrate": 4800},
        {"bytesize": 7},
        {"parity": "E"},
        {"stopbits": 2},
        {"xonxoff": True},
        {"api_port": 80},
        {"stale_seconds": 0},
    ],
)
def test_invalid_configuration_is_rejected(changes):
    with pytest.raises(ConfigurationError):
        valid_config(**changes).validate()


def test_unknown_or_secret_configuration_field_is_rejected(tmp_path):
    path = tmp_path / "config.json"
    data = valid_config().as_json_dict()
    data["password"] = "must-not-be-accepted"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="unknown configuration"):
        load_config(path)


def test_updating_existing_configuration_preserves_file_permissions(tmp_path):
    path = tmp_path / "config.json"
    save_config(valid_config(), path)
    path.chmod(0o600)
    save_config(valid_config(preferred_usb_serial="FT-ABC"), path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert load_config(path).preferred_usb_serial == "FT-ABC"
