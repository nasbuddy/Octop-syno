"""DSM package lifecycle; the server runs as the package user, never as root."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import suppress
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("SYNOPKG_PKGVAR", "/var/packages/Octop/var"))
PID_FILE = DATA / "octop.pid"
PORT = 8089


def process_start(pid: int) -> str | None:
    """A PID alone may belong to another process after a reboot or crash."""
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except FileNotFoundError:
        return None
    boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    return None if fields[0] == "Z" else f"{boot_id}:{fields[19]}"


def running_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    state = json.loads(PID_FILE.read_text())
    pid = state["pid"]
    if (
        isinstance(pid, int)
        and pid > 1
        and isinstance(state["started"], str)
        and process_start(pid) == state["started"]
    ):
        return pid
    return None


def stop() -> int:
    pid = running_pid()
    if pid is not None:
        with suppress(ProcessLookupError):
            os.killpg(pid, signal.SIGTERM)
        deadline = time.monotonic() + 60
        while running_pid() is not None:
            if time.monotonic() >= deadline:
                print("Octop did not stop within 60s; check octop-service.log.", file=sys.stderr)
                return 1
            time.sleep(0.2)
    PID_FILE.unlink(missing_ok=True)
    return 0


def start() -> int:
    if running_pid() is not None:
        return 0
    # Fail before spawning if another service already owns the advertised port.
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", PORT))
    log_path = DATA / "octop-service.log"
    # ponytail: keep one previous startup log; use DSM log rotation for longer retention.
    if log_path.exists() and log_path.stat().st_size > 10 * 1024 * 1024:
        log_path.replace(DATA / "octop-service.log.1")
    with log_path.open("ab") as log:
        proc = subprocess.Popen(
            [str(ROOT / "bin" / "octop"), "run", "--host", "127.0.0.1", "--port", str(PORT)],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    PID_FILE.write_text(json.dumps({"pid": proc.pid, "started": process_start(proc.pid)}))
    deadline = time.monotonic() + 120
    try:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                PID_FILE.unlink(missing_ok=True)
                print("Octop exited during startup; check octop-service.log.", file=sys.stderr)
                return 1
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{PORT}/api/health", timeout=2
                ) as reply:
                    if json.load(reply).get("ok") is True:
                        return 0
            except (OSError, urllib.error.URLError, ValueError):
                pass
            time.sleep(0.5)
    except BaseException:
        stop()
        raise
    print("Octop startup timed out; check octop-service.log.", file=sys.stderr)
    stop()
    return 1


def main() -> int:
    os.umask(0o077)
    DATA.mkdir(parents=True, exist_ok=True)
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    if action == "start":
        return start()
    if action == "stop":
        return stop()
    if action == "status":
        return 0 if running_pid() is not None else 3
    if action in {"prestart", "prestop"}:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
