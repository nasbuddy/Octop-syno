"""Run with the packaged Python on Linux; no NAS, credentials or LLM calls needed."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    service = [sys.executable, str(root / "service.py")]
    with tempfile.TemporaryDirectory(prefix="octop-spk-test-") as tmp:
        env = {**os.environ, "SYNOPKG_PKGVAR": tmp}

        def control(action: str, expected: int = 0) -> None:
            result = subprocess.run([*service, action], env=env, timeout=150, check=False)
            assert result.returncode == expected, (action, result.returncode)

        try:
            control("status", 3)
            control("start")
            assert not (Path(tmp) / "octop-login.txt").exists()
            assert not (Path(tmp) / ".octop" / "octop-login.txt").exists()
            with urllib.request.urlopen("http://127.0.0.1:8089/") as reply:
                html = reply.read()
                assert b"<html" in html and b"/octop/assets/" in html
                assert b'rel="manifest"' not in html
            for headers in ({}, {"Cookie": "id=forged", "X-Remote-User": "admin"}):
                request = urllib.request.Request(
                    "http://127.0.0.1:8089/api/auth/dsm/session", headers=headers
                )
                try:
                    urllib.request.urlopen(request)
                except urllib.error.HTTPError as exc:
                    assert exc.code == 401
                else:
                    raise AssertionError("native authentication accepted an invalid session")
            pid_file = Path(tmp) / "octop.pid"
            first_state = pid_file.read_text()
            control("start")
            assert pid_file.read_text() == first_state  # start is idempotent
            control("stop")
            control("status", 3)
            # A stale PID must neither report running nor signal an unrelated process.
            pid_file.write_text(json.dumps({"pid": os.getpid(), "started": "stale"}))
            control("status", 3)
            control("stop")
            pid_file.write_text(json.dumps({"pid": 2**30, "started": None}))
            control("status", 3)
            control("stop")
            marker = Path(tmp) / ".octop" / "persistence-check.txt"
            marker.write_text("keep across restart")
            control("start")
            control("status")
            with urllib.request.urlopen("http://127.0.0.1:8089/api/health") as reply:
                health = json.load(reply)
                assert health["ok"] and health["db"] and health["users_loaded"] == 0
            login = urllib.request.Request(
                "http://127.0.0.1:8089/api/auth/login",
                data=json.dumps({"username": "admin", "password": "unused"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            try:
                urllib.request.urlopen(login)
            except urllib.error.HTTPError as exc:
                assert exc.code == 401
            else:
                raise AssertionError("password login bypassed DSM authentication")
            assert marker.read_text() == "keep across restart"
            control("stop")
            control("status", 3)
        finally:
            control("stop")
    print("Native SPK smoke test passed: dashboard, auth gate, restart, persistence, stale PID.")


if __name__ == "__main__":
    main()
