import subprocess
import time

SERVICE_NAME = "SCTPreweightScaleBridge"
SERVICE_STOPPED = 1
SERVICE_RUNNING = 4
SERVICE_TRANSITION_TIMEOUT_SECONDS = 30


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


def query_service_state():
    import win32serviceutil

    return win32serviceutil.QueryServiceStatus(SERVICE_NAME)[1]


def _wait_for_state(expected, *, state_reader, sleeper, monotonic, timeout):
    deadline = monotonic() + timeout
    while state_reader() != expected:
        if monotonic() >= deadline:
            raise RuntimeError("Scale Bridge service state transition timed out")
        sleeper(0.25)


def restart_service(
    *,
    runner=subprocess.run,
    state_reader=query_service_state,
    sleeper=time.sleep,
    monotonic=time.monotonic,
    timeout=SERVICE_TRANSITION_TIMEOUT_SECONDS,
):
    if state_reader() != SERVICE_STOPPED:
        stop = service_command("stop", runner=runner)
        if stop["returncode"] != 0:
            raise RuntimeError("Scale Bridge service could not be stopped")
        _wait_for_state(
            SERVICE_STOPPED,
            state_reader=state_reader,
            sleeper=sleeper,
            monotonic=monotonic,
            timeout=timeout,
        )
    start = service_command("start", runner=runner)
    if start["returncode"] != 0:
        raise RuntimeError("Scale Bridge service could not be started")
    _wait_for_state(
        SERVICE_RUNNING,
        state_reader=state_reader,
        sleeper=sleeper,
        monotonic=monotonic,
        timeout=timeout,
    )
    return start
