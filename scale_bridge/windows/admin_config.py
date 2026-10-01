import ctypes
import subprocess
import sys
from dataclasses import replace

from scale_bridge.config import BridgeConfig, load_config, save_config
from scale_bridge.windows.service_control import restart_service

UAT_ORIGIN = "http://preweight-uat.sct.local"


class AdministratorConfigurationError(RuntimeError):
    pass


def build_administrator_config(
    existing: BridgeConfig,
    *,
    workstation_code,
    scale_code,
    preferred_usb_serial,
    enable_uat,
    enable_production,
    production_origin,
):
    origins = []
    if enable_uat:
        origins.append(UAT_ORIGIN)
    if enable_production:
        origins.append(production_origin.strip())
    return replace(
        existing,
        workstation_code=workstation_code.strip(),
        scale_code=scale_code.strip(),
        preferred_usb_serial=preferred_usb_serial or None,
        allowed_origins=tuple(origins),
    ).validate()


def apply_administrator_config(
    config,
    path,
    *,
    loader=load_config,
    saver=save_config,
    restarter=restart_service,
):
    previous = loader(path)
    saved = False
    try:
        saver(config, path)
        saved = True
        restarter()
    except Exception as exc:
        recovery_error = None
        if saved:
            try:
                saver(previous, path)
                restarter()
            except Exception as recovery_exc:
                recovery_error = recovery_exc
        detail = (
            " ไม่สามารถคืนค่ากำหนดเดิมได้ / Previous configuration recovery failed."
            if recovery_error
            else ""
        )
        raise AdministratorConfigurationError(
            "บันทึกการกำหนดค่าไม่สำเร็จและไม่ได้ใช้การเปลี่ยนแปลง / "
            f"Configuration was not applied.{detail}"
        ) from exc


def is_administrator():
    if sys.platform != "win32":
        return False
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def launch_elevated_configuration(executable=None):
    if sys.platform != "win32":
        raise AdministratorConfigurationError(
            "รองรับการกำหนดค่านี้เฉพาะ Windows / Configuration is available only on Windows."
        )
    program = executable or sys.executable
    result = ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        program,
        subprocess.list2cmdline(["--configure"]),
        None,
        1,
    )
    if result <= 32:
        raise AdministratorConfigurationError(
            "ไม่ได้รับสิทธิ์ผู้ดูแลระบบ / Administrator elevation was not granted."
        )
