"""Run with the packaged Python on Linux; no NAS, credentials or LLM calls needed."""

from __future__ import annotations

import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from importlib.metadata import distributions
from pathlib import Path


def assert_numpy_requirements(packages: Path, version: str) -> None:
    from packaging.requirements import Requirement

    for distribution in distributions(path=[str(packages)]):
        for raw in distribution.requires or []:
            requirement = Requirement(raw)
            if requirement.name.lower() == "numpy" and (
                requirement.marker is None or requirement.marker.evaluate()
            ):
                assert version in requirement.specifier, (
                    f"{distribution.metadata['Name']} requires {requirement}; bundled NumPy is {version}"
                )


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    assert not (root / "runtime" / "bin" / "uv").exists()
    assert not (root / "runtime" / "bin" / "patchelf").exists()
    sys.path.insert(0, str(root / "packages"))
    # Exercise bundled timezones without the build host's zoneinfo directories.
    import zoneinfo

    import tzdata

    assert zoneinfo.TZPATH == ()
    assert Path(tzdata.__file__).resolve().is_relative_to(root / "packages")
    assert zoneinfo.ZoneInfo("Asia/Shanghai").utcoffset(datetime(2026, 1, 1)) == timedelta(hours=8)
    assert zoneinfo.ZoneInfo("Europe/London").utcoffset(datetime(2026, 1, 1)) == timedelta(0)
    assert zoneinfo.ZoneInfo("Europe/London").utcoffset(datetime(2026, 7, 1)) == timedelta(hours=1)
    for module in (
        "PIL._imaging",
        "PIL._imagingft",
        "numpy.linalg",
        "_crypt",
        "tiktoken._tiktoken",
        "psycopg.pq",
        "cryptography.hazmat.bindings._rust",
    ):
        importlib.import_module(module)
    import _crypt

    import numpy
    import tiktoken
    from PIL import Image, ImageFont
    from psycopg import pq

    assert_numpy_requirements(root / "packages", numpy.__version__)
    if os.uname().machine == "x86_64":
        from numpy._core import _multiarray_umath

        assert set(_multiarray_umath.__cpu_baseline__) <= {"SSE", "SSE2", "SSE3"}
    assert Image.new("RGB", (1, 1), (1, 2, 3)).getpixel((0, 0)) == (1, 2, 3)
    png = io.BytesIO()
    Image.new("RGB", (2, 2), (1, 2, 3)).save(png, format="PNG")
    png.seek(0)
    with Image.open(png) as decoded:
        assert decoded.getpixel((0, 0)) == (1, 2, 3)
    assert ImageFont.load_default().getmask("NAS").getbbox() is not None
    assert list(numpy.linalg.solve([[2, 0], [0, 4]], [2, 4])) == [1.0, 1.0]
    matrix = numpy.arange(64, dtype=numpy.float64).reshape(8, 8)
    assert numpy.allclose(
        matrix @ matrix.T, numpy.sum(matrix[:, None, :] * matrix[None, :, :], axis=2)
    )
    signal = numpy.arange(32, dtype=numpy.float64)
    assert numpy.allclose(numpy.fft.ifft(numpy.fft.fft(signal)), signal)
    assert _crypt.crypt("spk-smoke", "$6$octop-smoke$").startswith("$6$octop-smoke$")
    assert pq.version() > 0
    encoding = tiktoken.Encoding(
        name="spk-smoke",
        pat_str=r"[\s\S]",
        mergeable_ranks={bytes([i]): i for i in range(256)},
        special_tokens={},
    )
    assert encoding.decode(encoding.encode("NAS 7.0")) == "NAS 7.0"
    libraries = set()
    system_libraries = set()
    for line in Path("/proc/self/maps").read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5].startswith("/") and ".so" in fields[5]:
            library = Path(fields[5]).resolve()
            if not library.is_relative_to(root):
                system_libraries.add(str(library))
            libraries.add(library.name)
    assert not system_libraries, f"extensions loaded system libraries: {sorted(system_libraries)}"
    assert {"libc.so.6", "libz.so.1", "libcrypt.so.1"} <= libraries
    # Child interpreters must also resolve the private loader without poisoning host commands.
    assert "LD_LIBRARY_PATH" not in os.environ
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import ssl, sqlite3; assert ssl.create_default_context().get_ca_certs()",
        ],
        env={**os.environ, "SSL_CERT_FILE": str(root / "packages" / "certifi" / "cacert.pem")},
        check=True,
    )
    expected_glibc = os.environ.get("EXPECTED_SYSTEM_GLIBC")
    if expected_glibc:
        actual = subprocess.check_output(["getconf", "GNU_LIBC_VERSION"], text=True).strip()
        assert actual == f"glibc {expected_glibc}", actual
    service = [sys.executable, str(root / "service.py")]
    with tempfile.TemporaryDirectory(prefix="octop-spk-test-") as tmp:
        env = {**os.environ, "SYNOPKG_PKGVAR": tmp}
        env.pop("SSL_CERT_FILE", None)

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
                for path, status in (
                    ("/api/auth/dsm/session", 401),
                    ("/octop/api/auth/dsm/session", 404),
                ):
                    request = urllib.request.Request(
                        "http://127.0.0.1:8089" + path, headers=headers
                    )
                    try:
                        urllib.request.urlopen(request)
                    except urllib.error.HTTPError as exc:
                        assert exc.code == status
                    else:
                        raise AssertionError("native authentication accepted an invalid session")
            pid_file = Path(tmp) / "octop.pid"
            first_state = pid_file.read_text()
            process_env = Path(f"/proc/{json.loads(first_state)['pid']}/environ").read_bytes()
            assert (
                b"SSL_CERT_FILE="
                + str(root / "packages" / "certifi" / "cacert.pem").encode()
                + b"\0"
                in process_env
            )
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
