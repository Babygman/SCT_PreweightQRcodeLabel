import subprocess

SERVICE_NAME = "SCTPreweightScaleBridge"


def service_command(action, *, runner=subprocess.run):
    if action not in {"start", "stop", "query"}:
        raise ValueError("unsupported service action")
    completed = runner(
        ["sc.exe", action, SERVICE_NAME],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    return {
        "action": action,
        "returncode": completed.returncode,
        "output": (completed.stdout or completed.stderr).strip(),
    }


def restart_service(*, runner=subprocess.run):
    stop = service_command("stop", runner=runner)
    already_stopped = "STOPPED" in stop["output"] or "1062" in stop["output"]
    if stop["returncode"] != 0 and not already_stopped:
        raise RuntimeError("Scale Bridge service could not be stopped")
    start = service_command("start", runner=runner)
    if start["returncode"] != 0:
        raise RuntimeError("Scale Bridge service could not be started")
    return start
