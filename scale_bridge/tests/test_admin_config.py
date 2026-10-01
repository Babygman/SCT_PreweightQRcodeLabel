from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scale_bridge.config import BridgeConfig, ConfigurationError, load_config, save_config
from scale_bridge.windows.admin_config import (
    UAT_ORIGIN,
    AdministratorConfigurationError,
    apply_administrator_config,
    build_administrator_config,
    launch_elevated_configuration,
)
from scale_bridge.windows.service_control import SERVICE_NAME, restart_service


def existing_config():
    return BridgeConfig(
        workstation_code="WEIGH-01",
        scale_code="SCALE-01",
        preferred_usb_serial="FT-OLD",
        allowed_origins=(UAT_ORIGIN,),
    )


@pytest.mark.parametrize(
    ("uat", "production", "expected"),
    [
        (True, False, (UAT_ORIGIN,)),
        (False, True, ("https://preweight.sct.local",)),
        (True, True, (UAT_ORIGIN, "https://preweight.sct.local")),
    ],
)
def test_administrator_configuration_supports_uat_production_or_both(
    uat, production, expected
):
    configured = build_administrator_config(
        existing_config(),
        workstation_code=" WEIGH-02 ",
        scale_code=" SCALE-02 ",
        preferred_usb_serial="FT-NEW",
        enable_uat=uat,
        enable_production=production,
        production_origin="https://preweight.sct.local",
    )
    assert configured.workstation_code == "WEIGH-02"
    assert configured.scale_code == "SCALE-02"
    assert configured.preferred_usb_serial == "FT-NEW"
    assert configured.allowed_origins == expected


def test_administrator_configuration_requires_at_least_one_environment():
    with pytest.raises(ConfigurationError, match="at least one"):
        build_administrator_config(
            existing_config(),
            workstation_code="WEIGH-01",
            scale_code="SCALE-01",
            preferred_usb_serial="",
            enable_uat=False,
            enable_production=False,
            production_origin="",
        )


def test_configuration_save_is_atomic_and_restarts_only_scale_bridge(tmp_path):
    path = tmp_path / "config.json"
    save_config(existing_config(), path)
    updated = build_administrator_config(
        existing_config(),
        workstation_code="WEIGH-02",
        scale_code="SCALE-02",
        preferred_usb_serial="FT-NEW",
        enable_uat=True,
        enable_production=False,
        production_origin="",
    )
    restarter = Mock()

    apply_administrator_config(updated, path, restarter=restarter)

    assert load_config(path) == updated
    restarter.assert_called_once_with()


def test_restart_failure_restores_previous_configuration(tmp_path):
    path = tmp_path / "config.json"
    previous = existing_config()
    save_config(previous, path)
    updated = build_administrator_config(
        previous,
        workstation_code="WEIGH-02",
        scale_code="SCALE-02",
        preferred_usb_serial="FT-NEW",
        enable_uat=True,
        enable_production=False,
        production_origin="",
    )
    restarter = Mock(side_effect=[RuntimeError("restart failed"), None])

    with pytest.raises(AdministratorConfigurationError, match="Configuration was not applied"):
        apply_administrator_config(updated, path, restarter=restarter)

    assert load_config(path) == previous
    assert restarter.call_count == 2


def test_save_failure_leaves_previous_configuration_unchanged(tmp_path):
    path = tmp_path / "config.json"
    previous = existing_config()
    save_config(previous, path)
    restarter = Mock()

    def failing_saver(_config, _path):
        raise OSError("write failed")

    with pytest.raises(AdministratorConfigurationError):
        apply_administrator_config(
            build_administrator_config(
                previous,
                workstation_code="WEIGH-02",
                scale_code="SCALE-02",
                preferred_usb_serial="FT-NEW",
                enable_uat=True,
                enable_production=False,
                production_origin="",
            ),
            path,
            saver=failing_saver,
            restarter=restarter,
        )

    assert load_config(path) == previous
    restarter.assert_not_called()


def test_service_restart_targets_only_approved_service():
    calls = []

    def runner(command, **_options):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="OK", stderr="")

    restart_service(runner=runner)
    assert calls == [
        ["sc.exe", "stop", SERVICE_NAME],
        ["sc.exe", "start", SERVICE_NAME],
    ]


def test_service_restart_can_recover_when_service_is_already_stopped():
    responses = iter(
        [
            SimpleNamespace(returncode=1062, stdout="STATE: STOPPED", stderr=""),
            SimpleNamespace(returncode=0, stdout="STATE: RUNNING", stderr=""),
        ]
    )
    calls = []

    def runner(command, **_options):
        calls.append(command)
        return next(responses)

    restart_service(runner=runner)
    assert calls[-1] == ["sc.exe", "start", SERVICE_NAME]


def test_configuration_elevation_is_controlled_off_windows():
    with pytest.raises(AdministratorConfigurationError, match="only on Windows"):
        launch_elevated_configuration()


def test_administrator_ui_displays_exact_environment_urls_and_bilingual_errors():
    diagnostics = Path("scale_bridge/windows/diagnostics.py").read_text(encoding="utf-8")
    assert "UAT_ORIGIN if self.enable_uat.get()" in diagnostics
    assert "self.production.get().strip()" in diagnostics
    assert "ไม่ได้เลือก / Not selected" in diagnostics
    assert "ไม่สามารถบันทึกการกำหนดค่าได้ โปรดตรวจสอบค่าที่ป้อน / " in diagnostics
    assert "Configuration could not be saved. Check the entered values." in diagnostics
