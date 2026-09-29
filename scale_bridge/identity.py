from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True, slots=True)
class ScaleIdentity:
    scale_code: str
    model: str = "IDS701-PLCD"
    usb_serial_number: str | None = None
    vid: int = 0x0403
    pid: int = 0x6001
    com_port: str | None = None
    workstation: str | None = None

    def with_port(self, com_port: str | None, workstation: str | None = None):
        return replace(
            self,
            com_port=com_port,
            workstation=self.workstation if workstation is None else workstation,
        )

    def as_dict(self):
        data = asdict(self)
        data["vid"] = f"{self.vid:04X}"
        data["pid"] = f"{self.pid:04X}"
        return data
