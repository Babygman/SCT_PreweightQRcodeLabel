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
    UAT_ORIGIN,
    AdministratorConfigurationError,
    AdministratorConfigurationValidationError,
    apply_administrator_config,
    build_administrator_config,
    is_administrator,
    launch_elevated_configuration,
)
from scale_bridge.windows.service_control import SERVICE_NAME


class DiagnosticsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("การวินิจฉัย IDS701 / IDS701 Diagnostics")
        try:
            self.config = load_config(DEFAULT_CONFIG_PATH)
        except ConfigurationError:
            # Standard users intentionally cannot read the hardened machine configuration.
            # Diagnostics needs only non-secret protocol defaults to query loopback safely.
            self.config = BridgeConfig(
                workstation_code="DIAGNOSTICS",
                scale_code="DIAGNOSTICS",
                allowed_origins=(UAT_ORIGIN,),
            )
        self.device_by_label = {}
        self.service_value = tk.StringVar()
        self.bridge_value = tk.StringVar()
        self.device_value = tk.StringVar()
        self.reading_value = tk.StringVar()
        self._build()
        self.refresh()

    def _build(self):
        frame = ttk.Frame(self.root, padding=16)
        frame.grid(sticky="nsew")
        for row, (label, value) in enumerate(
            [
                ("สถานะบริการ / Service status", self.service_value),
                ("สถานะบริดจ์ / Bridge status", self.bridge_value),
                ("ค่าน้ำหนัก IDS701 / IDS701 reading", self.reading_value),
            ]
        ):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w")
            ttk.Label(frame, textvariable=value).grid(row=row, column=1, sticky="w")
        ttk.Label(frame, text="อุปกรณ์ FTDI ที่เลือก / Preferred FTDI device").grid(
            row=3, column=0, sticky="w"
        )
        self.devices = ttk.Combobox(
            frame,
            textvariable=self.device_value,
            state="readonly",
            width=70,
        )
        self.devices.grid(row=3, column=1, sticky="ew")
        ttk.Button(
            frame,
            text="การกำหนดค่าสำหรับผู้ดูแลระบบ / Administrator Configuration",
            command=self.open_administrator_configuration,
        ).grid(row=4, column=1, sticky="e")
        ttk.Button(frame, text="รีเฟรช / Refresh", command=self.refresh).grid(
            row=5, column=1, sticky="e"
        )
        ttk.Label(frame, text="ข้อผิดพลาดล่าสุดที่ล้างข้อมูลแล้ว / Sanitized recent errors").grid(
            row=6, column=0, sticky="nw"
        )
        self.errors = tk.Text(frame, width=90, height=10, state="disabled")
        self.errors.grid(row=6, column=1, sticky="nsew")

    def refresh(self):
        result = subprocess.run(
            ["sc.exe", "query", SERVICE_NAME],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.service_value.set("RUNNING" if "RUNNING" in result.stdout else "STOPPED/UNAVAILABLE")
        ports = discover_ports(vid=self.config.vid, pid=self.config.pid)
        labels = []
        self.device_by_label.clear()
        for port in ports:
            serial = port.serial_number or "ไม่มีหมายเลข USB / no USB serial"
            label = f"{port.device} | {port.vid:04X}:{port.pid:04X} | {serial} | {port.description}"
            labels.append(label)
            self.device_by_label[label] = port.serial_number
        self.devices["values"] = labels
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


class AdministratorConfigurationApp:
    def __init__(self, root):
        self.root = root
        self.root.title("การกำหนดค่าสำหรับผู้ดูแลระบบ / Administrator Configuration")
        self.config = load_config(DEFAULT_CONFIG_PATH)
        production = next(
            (origin for origin in self.config.allowed_origins if origin != UAT_ORIGIN),
            "",
        )
        self.workstation = tk.StringVar(value=self.config.workstation_code)
        self.scale = tk.StringVar(value=self.config.scale_code)
        self.preferred = tk.StringVar(value=self.config.preferred_usb_serial or "")
        self.enable_uat = tk.BooleanVar(value=UAT_ORIGIN in self.config.allowed_origins)
        self.enable_production = tk.BooleanVar(value=bool(production))
        self.production = tk.StringVar(value=production)
        self.uat_display = tk.StringVar()
        self.production_display = tk.StringVar()
        self._build()
        self._refresh_environment_display()

    def _build(self):
        frame = ttk.Frame(self.root, padding=16)
        frame.grid(sticky="nsew")
        fields = (
            ("รหัสสถานีงาน / Workstation Code", self.workstation),
            ("รหัสเครื่องชั่ง / Scale Code", self.scale),
        )
        for row, (label, variable) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w")
            ttk.Entry(frame, textvariable=variable, width=55).grid(row=row, column=1, sticky="ew")

        ttk.Label(frame, text="อุปกรณ์ FTDI ที่ต้องการ / Preferred FTDI Device").grid(
            row=2, column=0, sticky="w"
        )
        serials = sorted(
            {
                port.serial_number
                for port in discover_ports(vid=self.config.vid, pid=self.config.pid)
                if port.serial_number
            }
            | ({self.config.preferred_usb_serial} if self.config.preferred_usb_serial else set())
        )
        ttk.Combobox(
            frame,
            textvariable=self.preferred,
            values=serials,
            state="readonly",
            width=52,
        ).grid(row=2, column=1, sticky="ew")

        ttk.Checkbutton(
            frame,
            text="UAT",
            variable=self.enable_uat,
            command=self._refresh_environment_display,
        ).grid(row=3, column=0, sticky="w")
        ttk.Label(frame, textvariable=self.uat_display).grid(row=3, column=1, sticky="w")
        ttk.Checkbutton(
            frame,
            text="Production",
            variable=self.enable_production,
            command=self._refresh_environment_display,
        ).grid(row=4, column=0, sticky="w")
        production_entry = ttk.Entry(frame, textvariable=self.production, width=55)
        production_entry.grid(row=4, column=1, sticky="ew")
        production_entry.bind("<KeyRelease>", lambda _event: self._refresh_environment_display())
        ttk.Label(frame, textvariable=self.production_display).grid(row=5, column=1, sticky="w")
        ttk.Button(
            frame,
            text="บันทึกการกำหนดค่า / Save Configuration",
            command=self.save,
        ).grid(row=6, column=1, sticky="e", pady=(12, 0))

    def _refresh_environment_display(self):
        self.uat_display.set(UAT_ORIGIN if self.enable_uat.get() else "ไม่ได้เลือก / Not selected")
        self.production_display.set(
            self.production.get().strip()
            if self.enable_production.get() and self.production.get().strip()
            else "ไม่ได้เลือก / Not selected"
        )

    def save(self):
        try:
            updated = build_administrator_config(
                self.config,
                workstation_code=self.workstation.get(),
                scale_code=self.scale.get(),
                preferred_usb_serial=self.preferred.get(),
                enable_uat=self.enable_uat.get(),
                enable_production=self.enable_production.get(),
                production_origin=self.production.get(),
            )
            apply_administrator_config(updated, DEFAULT_CONFIG_PATH)
        except AdministratorConfigurationValidationError as exc:
            messagebox.showerror(
                "SCT Scale Bridge",
                str(exc),
            )
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
        self.root.destroy()


def main():
    root = tk.Tk()
    if "--configure" in sys.argv:
        if not is_administrator():
            root.withdraw()
            messagebox.showerror(
                "SCT Scale Bridge",
                "ต้องใช้สิทธิ์ผู้ดูแลระบบเพื่อเปลี่ยนการกำหนดค่า / "
                "Administrator privileges are required to change configuration.",
            )
            root.destroy()
            return
        configure_logging(DEFAULT_CONFIG_DIR / "logs")
        AdministratorConfigurationApp(root)
    else:
        DiagnosticsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
