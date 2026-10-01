import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.error import URLError
from urllib.request import urlopen

from scale_bridge.config import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_PATH,
    BridgeConfig,
    ConfigurationError,
    load_config,
)
from scale_bridge.logging_setup import configure_logging, sanitize_message
from scale_bridge.serial_source import discover_ports
from scale_bridge.windows.admin_config import (
    AUTOMATIC_DISCOVERY,
    NOT_SELECTED,
    UAT_ORIGIN,
    UNAVAILABLE,
    AdministratorConfigurationError,
    AdministratorConfigurationValidationError,
    build_administrator_config,
    configuration_display,
    is_administrator,
    launch_elevated_configuration,
    save_and_reload_administrator_config,
)
from scale_bridge.windows.service_control import SERVICE_NAME


class DiagnosticsApp:
    def __init__(self, root, *, edit_mode=False):
        self.root = root
        self.edit_mode = edit_mode
        self.root.title("การวินิจฉัย IDS701 / IDS701 Diagnostics")
        self.config = self._load_initial_config()
        self.service_value = tk.StringVar()
        self.bridge_value = tk.StringVar()
        self.reading_value = tk.StringVar()
        self.workstation = tk.StringVar()
        self.scale = tk.StringVar()
        self.preferred = tk.StringVar()
        self.selected_environments = tk.StringVar()
        self.enable_uat = tk.BooleanVar()
        self.enable_production = tk.BooleanVar()
        self.uat_display = tk.StringVar()
        self.production = tk.StringVar()
        self.production_display = tk.StringVar()
        self._set_configuration(self.config)
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.cancel)
        self.refresh()

    def _load_initial_config(self):
        try:
            return load_config(DEFAULT_CONFIG_PATH)
        except ConfigurationError:
            if self.edit_mode:
                raise
            return BridgeConfig(
                workstation_code="DIAGNOSTICS",
                scale_code="DIAGNOSTICS",
                allowed_origins=(UAT_ORIGIN,),
            )

    def _build(self):
        frame = ttk.Frame(self.root, padding=16)
        frame.grid(sticky="nsew")
        rows = (
            ("สถานะบริการ / Service Status", self.service_value),
            ("สถานะบริดจ์ / Bridge Status", self.bridge_value),
            ("ค่าน้ำหนัก IDS701 / IDS701 Reading", self.reading_value),
        )
        for row, (label, value) in enumerate(rows):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w")
            ttk.Label(frame, textvariable=value).grid(row=row, column=1, sticky="w")

        row = len(rows)
        self._configuration_field(
            frame,
            row,
            "รหัสสถานีงาน / Workstation Code",
            self.workstation,
        )
        row += 1
        self._configuration_field(frame, row, "รหัสเครื่องชั่ง / Scale Code", self.scale)
        row += 1
        self._preferred_device_field(frame, row)
        row += 1
        self._environment_field(frame, row)
        row += 1
        ttk.Label(frame, text="URL ของ UAT / UAT Origin").grid(row=row, column=0, sticky="w")
        ttk.Label(frame, textvariable=self.uat_display).grid(row=row, column=1, sticky="w")
        row += 1
        self._production_origin_field(frame, row)
        row += 1

        if self.edit_mode:
            buttons = ttk.Frame(frame)
            buttons.grid(row=row, column=1, sticky="e", pady=(12, 0))
            ttk.Button(buttons, text="ยกเลิก / Cancel", command=self.cancel).grid(
                row=0,
                column=0,
                padx=(0, 8),
            )
            ttk.Button(
                buttons,
                text="บันทึกการกำหนดค่า / Save Configuration",
                command=self.save,
            ).grid(row=0, column=1)
        else:
            ttk.Button(
                frame,
                text="แก้ไขในฐานะผู้ดูแลระบบ / Edit as Administrator",
                command=self.open_administrator_configuration,
            ).grid(row=row, column=1, sticky="e", pady=(12, 0))
        row += 1
        ttk.Button(frame, text="รีเฟรช / Refresh", command=self.refresh).grid(
            row=row,
            column=1,
            sticky="e",
        )
        row += 1
        ttk.Label(frame, text="ข้อผิดพลาดล่าสุดที่ล้างข้อมูลแล้ว / Sanitized Recent Errors").grid(
            row=row,
            column=0,
            sticky="nw",
        )
        self.errors = tk.Text(frame, width=90, height=10, state="disabled")
        self.errors.grid(row=row, column=1, sticky="nsew")

    def _configuration_field(self, frame, row, label, variable):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w")
        if self.edit_mode:
            ttk.Entry(frame, textvariable=variable, width=55).grid(
                row=row,
                column=1,
                sticky="ew",
            )
        else:
            ttk.Label(frame, textvariable=variable).grid(row=row, column=1, sticky="w")

    def _preferred_device_field(self, frame, row):
        ttk.Label(frame, text="อุปกรณ์ FTDI ที่ต้องการ / Preferred FTDI Device").grid(
            row=row,
            column=0,
            sticky="w",
        )
        if self.edit_mode:
            serials = sorted(
                {
                    port.serial_number
                    for port in discover_ports(vid=self.config.vid, pid=self.config.pid)
                    if port.serial_number
                }
                | (
                    {self.config.preferred_usb_serial}
                    if self.config.preferred_usb_serial
                    else set()
                )
            )
            serials.insert(0, AUTOMATIC_DISCOVERY)
            ttk.Combobox(
                frame,
                textvariable=self.preferred,
                values=serials,
                state="readonly",
                width=52,
            ).grid(row=row, column=1, sticky="ew")
        else:
            ttk.Label(frame, textvariable=self.preferred).grid(row=row, column=1, sticky="w")

    def _environment_field(self, frame, row):
        ttk.Label(frame, text="สภาพแวดล้อมที่เลือก / Selected Environments").grid(
            row=row,
            column=0,
            sticky="w",
        )
        if self.edit_mode:
            choices = ttk.Frame(frame)
            choices.grid(row=row, column=1, sticky="w")
            ttk.Checkbutton(
                choices,
                text="UAT",
                variable=self.enable_uat,
                command=self._refresh_environment_display,
            ).grid(row=0, column=0, sticky="w")
            ttk.Checkbutton(
                choices,
                text="Production",
                variable=self.enable_production,
                command=self._refresh_environment_display,
            ).grid(row=0, column=1, sticky="w", padx=(12, 0))
        else:
            ttk.Label(frame, textvariable=self.selected_environments).grid(
                row=row,
                column=1,
                sticky="w",
            )

    def _production_origin_field(self, frame, row):
        ttk.Label(frame, text="URL ของ Production / Production Origin").grid(
            row=row,
            column=0,
            sticky="w",
        )
        if self.edit_mode:
            entry = ttk.Entry(frame, textvariable=self.production, width=55)
            entry.grid(row=row, column=1, sticky="ew")
            entry.bind("<KeyRelease>", lambda _event: self._refresh_environment_display())
        else:
            ttk.Label(frame, textvariable=self.production_display).grid(
                row=row,
                column=1,
                sticky="w",
            )

    def _set_configuration(self, config):
        if isinstance(config, BridgeConfig):
            data = {
                "workstation_code": config.workstation_code,
                "scale_code": config.scale_code,
                "preferred_usb_serial": config.preferred_usb_serial,
                "allowed_origins": config.allowed_origins,
            }
        else:
            data = config
        display = configuration_display(data)
        origins = tuple(data.get("allowed_origins") or ())
        production = next((origin for origin in origins if origin != UAT_ORIGIN), "")
        self.workstation.set(data.get("workstation_code") or UNAVAILABLE)
        self.scale.set(data.get("scale_code") or UNAVAILABLE)
        self.preferred.set(data.get("preferred_usb_serial") or AUTOMATIC_DISCOVERY)
        self.enable_uat.set(UAT_ORIGIN in origins)
        self.enable_production.set(bool(production))
        self.production.set(production)
        self.selected_environments.set(display["selected_environments"])
        self.uat_display.set(display["uat_origin"] if not self.edit_mode else UAT_ORIGIN)
        self.production_display.set(display["production_origin"])

    def _refresh_environment_display(self):
        selected = []
        if self.enable_uat.get():
            selected.append("UAT")
        if self.enable_production.get():
            selected.append("Production")
        self.selected_environments.set(", ".join(selected) if selected else NOT_SELECTED)
        self.uat_display.set(UAT_ORIGIN)
        self.production_display.set(
            self.production.get().strip()
            if self.enable_production.get() and self.production.get().strip()
            else NOT_SELECTED
        )

    def refresh(self):
        result = subprocess.run(
            ["sc.exe", "query", SERVICE_NAME],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.service_value.set("RUNNING" if "RUNNING" in result.stdout else "STOPPED/UNAVAILABLE")
        try:
            with urlopen(f"http://127.0.0.1:{self.config.api_port}/status", timeout=2) as response:
                state = json.loads(response.read())
            user_state = state["user_state"]
            self.bridge_value.set(f"{user_state['label_th']} / {user_state['label_en']}")
            reading = state.get("reading") or {}
            self.reading_value.set(
                f"frame={reading.get('status', '-')} | stable={state.get('stable')} | "
                f"Gross={state.get('gross')} | Tare={state.get('tare')} | "
                f"Actual={state.get('actual')} | last={state.get('last_reading_time')}"
            )
            if not self.edit_mode and state.get("configuration"):
                self._set_configuration(state["configuration"])
        except (OSError, URLError, ValueError, KeyError):
            self.bridge_value.set("ไม่สามารถเชื่อมต่อ Scale Bridge ได้ / Bridge unavailable")
            self.reading_value.set("ไม่มีค่าน้ำหนัก / Reading unavailable")
        self._load_recent_errors(DEFAULT_CONFIG_DIR / "logs" / "scale-bridge.log")

    def _load_recent_errors(self, path: Path):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
        except OSError:
            lines = ["ไม่มีบันทึกการวินิจฉัย / No diagnostic log is available."]
        content = "\n".join(sanitize_message(line) for line in lines)
        self.errors.configure(state="normal")
        self.errors.delete("1.0", tk.END)
        self.errors.insert("1.0", content)
        self.errors.configure(state="disabled")

    def open_administrator_configuration(self):
        try:
            launch_elevated_configuration()
        except AdministratorConfigurationError as exc:
            messagebox.showerror("SCT Scale Bridge", str(exc))

    def save(self):
        try:
            updated = build_administrator_config(
                self.config,
                workstation_code=self.workstation.get(),
                scale_code=self.scale.get(),
                preferred_usb_serial=(
                    "" if self.preferred.get() == AUTOMATIC_DISCOVERY else self.preferred.get()
                ),
                enable_uat=self.enable_uat.get(),
                enable_production=self.enable_production.get(),
                production_origin=self.production.get(),
            )
            self.config = save_and_reload_administrator_config(
                updated,
                DEFAULT_CONFIG_PATH,
            )
            self._set_configuration(self.config)
            self.refresh()
        except AdministratorConfigurationValidationError as exc:
            messagebox.showerror("SCT Scale Bridge", str(exc))
            return
        except ConfigurationError:
            messagebox.showerror(
                "SCT Scale Bridge",
                "ค่าการกำหนดค่าไม่ถูกต้อง / Configuration values are invalid.",
            )
            return
        except AdministratorConfigurationError as exc:
            messagebox.showerror("SCT Scale Bridge", str(exc))
            return
        messagebox.showinfo(
            "SCT Scale Bridge",
            "บันทึกการกำหนดค่าและเริ่มบริการ Scale Bridge ใหม่แล้ว / "
            "Configuration saved and the Scale Bridge service restarted.",
        )

    def cancel(self):
        self.root.destroy()


def main():
    root = tk.Tk()
    edit_mode = "--configure" in sys.argv
    if edit_mode and not is_administrator():
        root.withdraw()
        messagebox.showerror(
            "SCT Scale Bridge",
            "ต้องใช้สิทธิ์ผู้ดูแลระบบเพื่อเปลี่ยนการกำหนดค่า / "
            "Administrator privileges are required to change configuration.",
        )
        root.destroy()
        return
    if edit_mode:
        configure_logging(DEFAULT_CONFIG_DIR / "logs")
    DiagnosticsApp(root, edit_mode=edit_mode)
    root.mainloop()


if __name__ == "__main__":
    main()
