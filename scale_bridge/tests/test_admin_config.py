from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scale_bridge.config import BridgeConfig, load_config, save_config
from scale_bridge.windows import admin_config
from scale_bridge.windows.admin_config import (
    AUTOMATIC_DISCOVERY,
    EDITABLE_CONFIGURATION_FIELDS,
    UAT_ORIGIN,
    AdministratorConfigurationError,
    AdministratorConfigurationValidationError,
    apply_administrator_config,
    build_administrator_config,
    configuration_display,
    launch_elevated_configuration,
    save_and_reload_administrator_config,
)
from scale_bridge.windows.service_control import (
    SERVICE_NAME,
    SERVICE_RUNNING,
    SERVICE_STOPPED,
    restart_service,
)


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
    with pytest.raises(AdministratorConfigurationValidationError, match="at least one"):
        build_administrator_config(
            existing_config(),
            workstation_code="WEIGH-01",
            scale_code="SCALE-01",
            preferred_usb_serial="",
            enable_uat=False,
            enable_production=False,
            production_origin="",
        )


def test_exact_reported_uat_only_configuration_accepts_blank_production_origin():
    configured = build_administrator_config(
        existing_config(),
        workstation_code="WEIGH-01",
        scale_code="SCALE-01",
        preferred_usb_serial="AJ03K7N2A",
        enable_uat=True,
        enable_production=False,
        production_origin="",
    )

    assert configured.workstation_code == "WEIGH-01"
    assert configured.scale_code == "SCALE-01"
    assert configured.preferred_usb_serial == "AJ03K7N2A"
    assert configured.allowed_origins == (UAT_ORIGIN,)


def test_unselected_uat_does_not_require_its_origin_for_production_only():
    configured = build_administrator_config(
        existing_config(),
        workstation_code="WEIGH-01",
        scale_code="SCALE-01",
        preferred_usb_serial="AJ03K7N2A",
        enable_uat=False,
        enable_production=True,
        production_origin="https://preweight.sct.local",
    )

    assert configured.allowed_origins == ("https://preweight.sct.local",)


def test_selected_production_requires_a_field_specific_origin():
    with pytest.raises(
        AdministratorConfigurationValidationError,
        match="Production URL is required",
    ):
        build_administrator_config(
            existing_config(),
            workstation_code="WEIGH-01",
            scale_code="SCALE-01",
            preferred_usb_serial="AJ03K7N2A",
            enable_uat=True,
            enable_production=True,
            production_origin="",
        )


def test_validation_failure_does_not_save_or_restart_service():
    saver = Mock()
    restarter = Mock()

    with pytest.raises(AdministratorConfigurationValidationError):
        updated = build_administrator_config(
            existing_config(),
            workstation_code="WEIGH-01",
            scale_code="SCALE-01",
            preferred_usb_serial="AJ03K7N2A",
            enable_uat=True,
            enable_production=True,
            production_origin="",
        )
        apply_administrator_config(
            updated,
            Path("unused.json"),
            saver=saver,
            restarter=restarter,
        )

    saver.assert_not_called()
    restarter.assert_not_called()


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


def test_restart_failure_restores_previous_configuration(tmp_path, monkeypatch):
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
    log_error = Mock()
    monkeypatch.setattr(admin_config.logger, "error", log_error)

    with pytest.raises(
        AdministratorConfigurationError,
        match="previous configuration was restored",
    ):
        apply_administrator_config(updated, path, restarter=restarter)

    assert load_config(path) == previous
    assert restarter.call_count == 2
    assert log_error.call_args_list[0].args == (
        "Administrator configuration %s failed: %s",
        "Scale Bridge service restart",
        "restart failed",
    )


def test_save_failure_leaves_previous_configuration_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    previous = existing_config()
    save_config(previous, path)
    restarter = Mock()
    log_error = Mock()
    monkeypatch.setattr(admin_config.logger, "error", log_error)

    def failing_saver(_config, _path):
        raise OSError("ACL write failed password=must-not-appear")

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
    assert log_error.call_args.args == (
        "Administrator configuration %s failed: %s",
        "secure configuration save",
        "ACL write failed password=[REDACTED]",
    )


def test_service_restart_targets_only_approved_service():
    calls = []
    states = iter([SERVICE_RUNNING, SERVICE_STOPPED, SERVICE_RUNNING])

    def runner(command, **_options):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="OK", stderr="")

    restart_service(
        runner=runner,
        state_reader=lambda: next(states),
        sleeper=lambda _seconds: None,
    )
    assert calls == [
        ["sc.exe", "stop", SERVICE_NAME],
        ["sc.exe", "start", SERVICE_NAME],
    ]


def test_service_restart_can_recover_when_service_is_already_stopped():
    responses = iter([SimpleNamespace(returncode=0, stdout="STATE: RUNNING", stderr="")])
    states = iter([SERVICE_STOPPED, SERVICE_RUNNING])
    calls = []

    def runner(command, **_options):
        calls.append(command)
        return next(responses)

    restart_service(
        runner=runner,
        state_reader=lambda: next(states),
        sleeper=lambda _seconds: None,
    )
    assert calls == [["sc.exe", "start", SERVICE_NAME]]
    assert calls[-1] == ["sc.exe", "start", SERVICE_NAME]


def test_service_restart_waits_for_stopped_before_starting():
    calls = []
    states = iter([SERVICE_RUNNING, 3, SERVICE_STOPPED, 2, SERVICE_RUNNING])

    def runner(command, **_options):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="OK", stderr="")

    restart_service(
        runner=runner,
        state_reader=lambda: next(states),
        sleeper=lambda _seconds: None,
    )

    assert calls == [
        ["sc.exe", "stop", SERVICE_NAME],
        ["sc.exe", "start", SERVICE_NAME],
    ]


def test_configuration_elevation_is_controlled_off_windows(monkeypatch):
    monkeypatch.setattr(admin_config.sys, "platform", "linux")
    with pytest.raises(AdministratorConfigurationError, match="only on Windows"):
        launch_elevated_configuration()


def test_windows_configuration_elevation_uses_runas_with_safe_arguments(monkeypatch):
    shell_execute = Mock(return_value=42)
    list2cmdline = Mock(return_value="--configure")
    monkeypatch.setattr(admin_config.sys, "platform", "win32")
    monkeypatch.setattr(
        admin_config.ctypes,
        "windll",
        SimpleNamespace(shell32=SimpleNamespace(ShellExecuteW=shell_execute)),
        raising=False,
    )
    monkeypatch.setattr(admin_config.subprocess, "list2cmdline", list2cmdline)
    executable = r"C:\Program Files\SCT\ScaleBridge\Diagnostics.exe"

    launch_elevated_configuration(executable=executable)

    list2cmdline.assert_called_once_with(["--configure"])
    shell_execute.assert_called_once_with(
        None,
        "runas",
        executable,
        "--configure",
        None,
        1,
    )


def test_administrator_ui_displays_exact_environment_urls_and_bilingual_errors():
    diagnostics = Path("scale_bridge/windows/diagnostics.py").read_text(encoding="utf-8")
    admin = Path("scale_bridge/windows/admin_config.py").read_text(encoding="utf-8")
    assert "self.uat_display.set(UAT_ORIGIN)" in diagnostics
    assert "self.production.get().strip()" in diagnostics
    assert "ไม่ได้เลือก / Not selected" in admin
    assert "Production URL is required when Production is selected." in admin
    assert "Configuration values are invalid." in diagnostics
    assert "The Scale Bridge service could not be restarted" in admin


def test_normal_diagnostics_configuration_display_is_read_only_and_persisted():
    display = configuration_display(
        {
            "workstation_code": "WEIGH-01",
            "scale_code": "SCALE-01",
            "preferred_usb_serial": "AJ03K7N2A",
            "allowed_origins": [UAT_ORIGIN, "https://preweight.sct.local"],
        }
    )

    assert display == {
        "workstation_code": "WEIGH-01",
        "scale_code": "SCALE-01",
        "preferred_usb_serial": "AJ03K7N2A",
        "selected_environments": "UAT, Production",
        "uat_origin": UAT_ORIGIN,
        "production_origin": "https://preweight.sct.local",
    }
    source = Path("scale_bridge/windows/diagnostics.py").read_text(encoding="utf-8")
    assert source.count("ttk.Combobox(") == 1
    assert "if self.edit_mode:" in source
    assert "แก้ไขในฐานะผู้ดูแลระบบ / Edit as Administrator" in source
    assert "การกำหนดค่าสำหรับผู้ดูแลระบบ / Administrator Configuration" not in source


def test_missing_preferred_device_displays_bilingual_automatic_discovery():
    display = configuration_display(
        {
            "workstation_code": "WEIGH-01",
            "scale_code": "SCALE-01",
            "preferred_usb_serial": None,
            "allowed_origins": [UAT_ORIGIN],
        }
    )

    assert display["preferred_usb_serial"] == AUTOMATIC_DISCOVERY


def test_elevated_edit_mode_exposes_only_approved_configuration_fields():
    assert EDITABLE_CONFIGURATION_FIELDS == (
        "workstation_code",
        "scale_code",
        "preferred_usb_serial",
        "enable_uat",
        "enable_production",
        "production_origin",
    )
    source = Path("scale_bridge/windows/diagnostics.py").read_text(encoding="utf-8")
    assert "URL ของ UAT / UAT Origin" in source
    assert "self.uat_display.set(UAT_ORIGIN)" in source


def test_successful_save_reloads_persisted_values_for_same_ui():
    persisted = BridgeConfig(
        workstation_code="WEIGH-02",
        scale_code="SCALE-02",
        preferred_usb_serial="AJ03K7N2A",
        allowed_origins=(UAT_ORIGIN,),
    )
    apply = Mock()
    loader = Mock(return_value=persisted)

    reloaded = save_and_reload_administrator_config(
        persisted,
        Path("config.json"),
        applier=apply,
        loader=loader,
    )

    apply.assert_called_once_with(persisted, Path("config.json"))
    loader.assert_called_once_with(Path("config.json"))
    assert reloaded == persisted
    source = Path("scale_bridge/windows/diagnostics.py").read_text(encoding="utf-8")
    assert "self._set_configuration(self.config)" in source
    assert "self.refresh()" in source


def test_cancel_closes_window_without_save_or_service_restart():
    source = Path("scale_bridge/windows/diagnostics.py").read_text(encoding="utf-8")
    cancel = source[source.index("    def cancel(self):") : source.index("\n\n\ndef main():")]
    assert "self.root.destroy()" in cancel
    assert "save_and_reload_administrator_config" not in cancel
    assert "restart_service" not in cancel
