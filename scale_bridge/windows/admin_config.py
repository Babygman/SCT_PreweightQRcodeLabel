import ctypes
import logging
import subprocess
import sys
from dataclasses import replace

from scale_bridge.config import BridgeConfig, load_config, save_config
from scale_bridge.logging_setup import sanitize_message
from scale_bridge.windows.service_control import restart_service

UAT_ORIGIN = "http://preweight-uat.sct.local"
logger = logging.getLogger("scale_bridge.windows.admin_config")


class AdministratorConfigurationError(RuntimeError):
    pass


class AdministratorConfigurationValidationError(ValueError):
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
    workstation_code = workstation_code.strip()
    scale_code = scale_code.strip()
    preferred_usb_serial = (preferred_usb_serial or "").strip()
    production_origin = production_origin.strip()
    if not workstation_code:
        raise AdministratorConfigurationValidationError(
            "ต้องระบุรหัสสถานีงาน / Workstation Code is required."
        )
    if not scale_code:
        raise AdministratorConfigurationValidationError(
            "ต้องระบุรหัสเครื่องชั่ง / Scale Code is required."
        )
    if not enable_uat and not enable_production:
        raise AdministratorConfigurationValidationError(
            "ต้องเลือกสภาพแวดล้อมเว็บอย่างน้อยหนึ่งรายการ / "
            "Select at least one Web Environment."
        )
    if enable_production and not production_origin:
        raise AdministratorConfigurationValidationError(
            "ต้องระบุ URL ของ Production เมื่อเลือก Production / "
            "Production URL is required when Production is selected."
        )
    origins = []
    if enable_uat:
        origins.append(UAT_ORIGIN)
    if enable_production:
        origins.append(production_origin)
    try:
        return replace(
            existing,
            workstation_code=workstation_code,
            scale_code=scale_code,
            preferred_usb_serial=preferred_usb_serial or None,
            allowed_origins=tuple(origins),
        ).validate()
    except ValueError as exc:
        raise AdministratorConfigurationValidationError(
            "URL ของ Production ไม่ถูกต้อง / Production URL is invalid."
        ) from exc


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
    stage = "secure configuration save"
    try:
        saver(config, path)
        saved = True
        stage = "Scale Bridge service restart"
        restarter()
    except Exception as exc:
        logger.error("Administrator configuration %s failed: %s", stage, sanitize_message(exc))
        recovery_error = None
        if saved:
            try:
                saver(previous, path)
                restarter()
            except Exception as recovery_exc:
                recovery_error = recovery_exc
                logger.error(
                    "Administrator configuration recovery failed: %s",
                    sanitize_message(recovery_exc),
                )
        detail = (
            " ไม่สามารถคืนค่ากำหนดเดิมได้ / Previous configuration recovery failed."
            if recovery_error
            else ""
        )
        user_message = (
            "ไม่สามารถบันทึกไฟล์การกำหนดค่าอย่างปลอดภัยได้ / "
            "The configuration file could not be saved securely."
            if not saved
            else "เริ่มบริการ Scale Bridge ใหม่ไม่สำเร็จ จึงคืนค่ากำหนดเดิมแล้ว / "
            "The Scale Bridge service could not be restarted, so the previous "
            "configuration was restored."
        )
        raise AdministratorConfigurationError(
            f"{user_message}{detail}"
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
