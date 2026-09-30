import json
import locale
import os
import stat
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scale_bridge.config import (
    BridgeConfig,
    ConfigurationError,
    _copy_existing_permissions,
    load_config,
    save_config,
)


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


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode-bit behavior")
def test_updating_existing_configuration_preserves_posix_file_permissions(tmp_path):
    path = tmp_path / "config.json"
    save_config(valid_config(), path)
    path.chmod(0o600)
    save_config(valid_config(preferred_usb_serial="FT-ABC"), path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert load_config(path).preferred_usb_serial == "FT-ABC"


def test_windows_permission_copy_preserves_existing_dacl_with_safe_mock(tmp_path):
    existing = tmp_path / "config.json"
    temporary = tmp_path / "config.tmp"
    existing.write_text("existing", encoding="utf-8")
    temporary.write_text("replacement", encoding="utf-8")
    descriptor = object()
    windows_security = SimpleNamespace(
        DACL_SECURITY_INFORMATION=4,
        GetFileSecurity=Mock(return_value=descriptor),
        SetFileSecurity=Mock(),
    )

    _copy_existing_permissions(
        existing,
        temporary,
        platform_name="nt",
        windows_security=windows_security,
    )

    windows_security.GetFileSecurity.assert_called_once_with(str(existing), 4)
    windows_security.SetFileSecurity.assert_called_once_with(str(temporary), 4, descriptor)


def test_utf8_configuration_round_trip_does_not_depend_on_preferred_encoding(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(locale, "getpreferredencoding", lambda _do_setlocale=True: "cp874")
    path = tmp_path / "config.json"
    config = BridgeConfig(
        workstation_code="สถานี-01",
        scale_code="เครื่องชั่ง-01",
        allowed_origins=("https://preweight.example",),
    )
    save_config(config, path)
    assert load_config(path) == config
    assert "เครื่องชั่ง-01" in path.read_text(encoding="utf-8")
