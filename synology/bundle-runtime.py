"""Keep Linux runtime libraries inside the SPK, without changing DSM libraries."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


def source_archives(dsc: str) -> list[tuple[str, int, str]]:
    section = re.search(r"^Checksums-Sha256:\n((?: [^\n]+\n)+)", dsc, re.MULTILINE)
    if section is None:
        raise ValueError("Debian source description has no SHA-256 checksums")
    result = []
    for line in section.group(1).splitlines():
        digest, size, name = line.split()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_~-]*", name) or not re.fullmatch(
            r"[0-9a-f]{64}", digest
        ):
            raise ValueError("invalid source archive entry")
        result.append((digest, int(size), name))
    return result


def minimum_kernel(library: Path) -> tuple[int, int, int]:
    data = library.read_bytes()
    note = struct.pack("<III", 4, 16, 1) + b"GNU\0"
    offset = data.find(note)
    if offset < 0:
        raise ValueError("runtime libc has no GNU ABI tag")
    system, major, minor, patch = struct.unpack_from("<IIII", data, offset + len(note))
    if system != 0:
        raise ValueError("runtime libc does not target Linux")
    return major, minor, patch


def patch_elf(path: Path, root: Path, elf_machine: int, interpreter: str) -> bool:
    with path.open("rb") as stream:
        header = stream.read(20)
    if not header.startswith(b"\x7fELF"):
        return False
    if header[4:6] != b"\x02\x01" or struct.unpack_from("<H", header, 18)[0] != elf_machine:
        raise ValueError(f"wrong ELF architecture: {path.relative_to(root)}")
    if struct.unpack_from("<H", header, 16)[0] not in (2, 3):
        return False
    library_dir = root / "runtime" / "lib"
    # Keep the matching glibc bootstrap pair intact; patch libraries that depend on it.
    if path in (library_dir / "libc.so.6", library_dir / Path(interpreter).name):
        return False
    previous = subprocess.check_output(["patchelf", "--print-rpath", str(path)], text=True).strip()
    relative = os.path.relpath(library_dir, path.parent)
    private = "$ORIGIN" if relative == "." else "$ORIGIN/" + relative
    paths = [private, "$ORIGIN", *(previous.split(":") if previous else [])]
    subprocess.run(
        ["patchelf", "--force-rpath", "--set-rpath", ":".join(dict.fromkeys(paths)), str(path)],
        check=True,
    )
    probe = subprocess.run(["patchelf", "--print-interpreter", str(path)], capture_output=True)
    if probe.returncode == 0:
        subprocess.run(["patchelf", "--set-interpreter", interpreter, str(path)], check=True)
    return True


def bundle_sources(licenses: Path, cache: Path, source: str, version: str) -> None:
    directory = source[:4] if source.startswith("lib") else source[0]
    base = f"https://deb.debian.org/debian/pool/main/{directory}/{source}/"
    description = f"{source}_{version.split(':')[-1]}.dsc"
    with urllib.request.urlopen(base + description, timeout=120) as response:
        dsc = response.read().decode()
    (licenses / description).write_text(dsc)
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as temporary:
        for digest, size, name in source_archives(dsc):
            cached = cache / name
            candidate = cached if cached.is_file() else Path(temporary) / name
            if candidate != cached:
                with (
                    urllib.request.urlopen(base + name, timeout=120) as response,
                    candidate.open("wb") as output,
                ):
                    shutil.copyfileobj(response, output)
            with candidate.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if candidate.stat().st_size != size or actual != digest:
                raise ValueError(f"source archive checksum mismatch: {name}")
            if candidate != cached:
                candidate.replace(cached)
            shutil.copyfile(cached, licenses / name)


def bundle(root: Path) -> None:
    machine = platform.machine()
    loader, elf_machine = {
        "x86_64": ("ld-linux-x86-64.so.2", 62),
        "aarch64": ("ld-linux-aarch64.so.1", 183),
    }[machine]
    library_dir = root / "runtime" / "lib"
    interpreter = f"/var/packages/Octop/target/runtime/lib/{loader}"
    patched = 0
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        patched += patch_elf(path, root, elf_machine, interpreter)

    multiarch = f"{machine}-linux-gnu"
    kernel = minimum_kernel(Path("/lib") / multiarch / "libc.so.6")
    if kernel > (3, 10, 0):
        raise ValueError(f"runtime requires Linux {kernel}, newer than the DSM 7.0 baseline")
    libraries = (
        loader,
        "libc.so.6",
        "libm.so.6",
        "libpthread.so.0",
        "librt.so.1",
        "libdl.so.2",
        "libresolv.so.2",
        "libutil.so.1",
        "libanl.so.1",
        "libnss_dns.so.2",
        "libnss_files.so.2",
        "libstdc++.so.6",
        "libgcc_s.so.1",
        "libz.so.1",
        "libcrypt.so.1",
        "libfribidi.so.0",
    )
    for name in libraries:
        target = library_dir / name
        shutil.copyfile(Path("/lib") / multiarch / name, target)
        target.chmod(0o755)
        patched += patch_elf(target, root, elf_machine, interpreter)
    # Pillow's FriBidi shim tries the unversioned name before the runtime SONAME.
    (library_dir / "libfribidi.so").symlink_to("libfribidi.so.0")

    licenses = root / "licenses" / "linux-runtime"
    licenses.mkdir(parents=True)
    versions = {}
    for package in ("libc6", "libstdc++6", "libgcc-s1", "zlib1g", "libcrypt1", "libfribidi0"):
        versions[package] = subprocess.check_output(
            ["dpkg-query", "-W", "-f=${source:Version}", package],
            text=True,
        )
        shutil.copyfile(f"/usr/share/doc/{package}/copyright", licenses / f"{package}-copyright")
    for name in ("LGPL-2.1", "GPL-3"):
        shutil.copyfile(f"/usr/share/common-licenses/{name}", licenses / name)

    # Ship matching upstream sources and Debian patches for these runtime libraries.
    cache = Path("/build/runtime-sources")
    for package, source in (
        ("libc6", "glibc"),
        ("libcrypt1", "libxcrypt"),
        ("zlib1g", "zlib"),
        ("libfribidi0", "fribidi"),
    ):
        bundle_sources(licenses, cache, source, versions[package])

    manifest = {
        "machine": machine,
        "interpreter": interpreter,
        "sources": versions,
        "libraries": list(libraries),
        "patched_elf_files": patched,
        "minimum_linux_kernel": list(kernel),
    }
    (root / "runtime-compatibility.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    bundle(Path(sys.argv[1]).resolve())
