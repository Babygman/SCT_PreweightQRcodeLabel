import sys

import servicemanager
import win32event
import win32service
import win32serviceutil

from scale_bridge.config import DEFAULT_CONFIG_DIR, DEFAULT_CONFIG_PATH, load_config
from scale_bridge.host import BridgeHost


class SCTPreweightScaleBridgeService(win32serviceutil.ServiceFramework):
    _svc_name_ = "SCTPreweightScaleBridge"
    _svc_display_name_ = "SCT Preweight IDS701 Scale Bridge"
    _svc_description_ = "Receive-only local bridge for the IDS701 weighing scale."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.host = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.host:
            self.host.stop()
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("SCT Preweight Scale Bridge starting")
        config = load_config(DEFAULT_CONFIG_PATH)
        self.host = BridgeHost(config, DEFAULT_CONFIG_DIR / "logs")
        self.host.serve()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(SCTPreweightScaleBridgeService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(SCTPreweightScaleBridgeService)
