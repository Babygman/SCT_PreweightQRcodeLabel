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
