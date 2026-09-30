import json
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.error import URLError
from urllib.request import urlopen

from scale_bridge.config import DEFAULT_CONFIG_DIR, DEFAULT_CONFIG_PATH, load_config, save_config
from scale_bridge.logging_setup import sanitize_message
from scale_bridge.serial_source import discover_ports
from scale_bridge.windows.service_control import SERVICE_NAME


class DiagnosticsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("การวินิจฉัย IDS701 / IDS701 Diagnostics")
        self.config = load_config(DEFAULT_CONFIG_PATH)
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
            text="บันทึกอุปกรณ์ที่เลือก / Save preferred device",
            command=self.save_preferred,
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

    def save_preferred(self):
        selected = self.device_value.get()
        if selected not in self.device_by_label:
            messagebox.showerror(
                "SCT Scale Bridge",
                "เลือกอุปกรณ์ FTDI ที่ตรวจพบ / Select a detected FTDI device.",
            )
            return
        if not self.device_by_label[selected]:
            messagebox.showerror(
                "SCT Scale Bridge",
                "อุปกรณ์นี้ไม่มีหมายเลข USB ที่ใช้เป็นตัวระบุถาวร / "
                "This device has no USB serial for persistent selection.",
            )
            return
        data = self.config.as_json_dict()
        data["preferred_usb_serial"] = self.device_by_label[selected]
        data["allowed_origins"] = tuple(data["allowed_origins"])
        data["vid"] = int(data["vid"], 16)
        data["pid"] = int(data["pid"], 16)
        from scale_bridge.config import BridgeConfig

        self.config = BridgeConfig(**data).validate()
        save_config(self.config, DEFAULT_CONFIG_PATH)
        messagebox.showinfo(
            "SCT Scale Bridge",
            "บันทึกเครื่องชั่งที่เลือกแล้ว โปรดเริ่มบริการใหม่ / "
            "Preferred scale saved. Restart the service.",
        )


def main():
    root = tk.Tk()
    DiagnosticsApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
