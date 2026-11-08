"""Runtime packaging must reject wrong architectures and unsafe source entries."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "synology" / "bundle-runtime.py"
_BUILD_SCRIPT = _SCRIPT.with_name("build-spk.sh")
posix_only = pytest.mark.skipif(os.name != "posix", reason="SPK build uses a POSIX shell")


def _load():
    spec = importlib.util.spec_from_file_location("synology_runtime", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("requirement", "compatible"),
    [
        ("numpy>=2.3.2,<3", True),
        ("NumPy>=2.4", False),
        ('numpy>=2.4; python_version >= "3.0"', False),
        ('numpy>=2.4; extra == "unused"', True),
    ],
)
def test_numpy_compatibility_pin_respects_active_dependency_constraints(
    tmp_path: Path, requirement: str, compatible: bool
) -> None:
    spec = importlib.util.spec_from_file_location(
        "synology_smoke", _SCRIPT.with_name("smoke-test.py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    metadata = tmp_path / "numpy_consumer-1.0.dist-info" / "METADATA"
    metadata.parent.mkdir()
    metadata.write_text(
        f"Metadata-Version: 2.1\nName: numpy-consumer\nVersion: 1.0\nRequires-Dist: {requirement}\n"
    )
    if compatible:
        module.assert_numpy_requirements(tmp_path, "2.3.5")
    else:
        with pytest.raises(AssertionError, match="numpy-consumer requires"):
            module.assert_numpy_requirements(tmp_path, "2.3.5")


def _write_elf(path: Path, *, machine: int = 62, elf_type: int = 3) -> None:
    header = bytearray(20)
    header[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", header, 16, elf_type)
    struct.pack_into("<H", header, 18, machine)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header)


def _spk_metadata(upstream_version: str, build: str) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is unavailable")
    return subprocess.run(
        [
            bash,
            "-c",
            'source "$1"; spk_version_metadata "$2" "$3"',
            "bash",
            str(_BUILD_SCRIPT),
            upstream_version,
            build,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@posix_only
def test_spk_prereleases_and_final_use_increasing_numeric_versions() -> None:
    versions = [
        ("1.0.3b1", "0007", "1.0.3-0007 yes"),
        ("1.0.3b2", "0008", "1.0.3-0008 yes"),
        ("1.0.3rc1", "0009", "1.0.3-0009 yes"),
        ("1.0.3", "0010", "1.0.3-0010 no"),
    ]
    previous_build = 6
    for upstream, build, expected in versions:
        result = _spk_metadata(upstream, build)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == expected
        numeric_version = result.stdout.split()[0]
        numbers = [int(part) for part in numeric_version.replace("-", ".").split(".")]
        assert len(numbers) == 4
        assert all(0 <= number <= 2**31 - 1 for number in numbers)
        assert previous_build < numbers[-1]
        previous_build = numbers[-1]


@posix_only
@pytest.mark.parametrize(
    ("upstream", "build"),
    [("1.0.3.dev1", "0007"), ("1.0.3+local", "0007"), ("1.0.3b1", "0007beta")],
)
def test_spk_metadata_rejects_unsupported_versions(upstream: str, build: str) -> None:
    result = _spk_metadata(upstream, build)
    assert result.returncode == 2
    assert not result.stdout


def test_source_checksums_are_read_from_the_signed_description() -> None:
    digest = "a" * 64
    dsc = f"-----BEGIN PGP SIGNED MESSAGE-----\nHash: SHA512\n\nChecksums-Sha256:\n {digest} 123 glibc_2.36.orig.tar.xz\nFiles:\n ignored\n"
    assert _load().source_archives(dsc) == [(digest, 123, "glibc_2.36.orig.tar.xz")]


@pytest.mark.parametrize("entry", ["../outside.tar.xz", "..", "/outside.tar.xz"])
def test_source_archives_cannot_escape_the_license_directory(entry: str) -> None:
    with pytest.raises(ValueError, match="invalid source archive"):
        _load().source_archives(f"Checksums-Sha256:\n {'a' * 64} 123 {entry}\n")


def test_missing_source_checksums_are_rejected() -> None:
    with pytest.raises(ValueError, match="no SHA-256"):
        _load().source_archives("Format: 3.0 (quilt)\n")


@posix_only
@pytest.mark.parametrize(
    ("relative_path", "previous", "has_interpreter", "expected"),
    [
        (
            "packages/vendor.libs/dependency.so",
            "$ORIGIN/../../runtime/lib:$ORIGIN/../../runtime/lib:$ORIGIN/../other.libs",
            False,
            "$ORIGIN/../../runtime/lib:$ORIGIN:$ORIGIN/../other.libs",
        ),
        ("runtime/lib/libz.so.1", "", False, "$ORIGIN"),
        ("runtime/bin/python3.12", "$ORIGIN/../lib", True, "$ORIGIN/../lib:$ORIGIN"),
    ],
)
def test_elf_rpath_keeps_vendor_paths_and_finds_siblings_without_duplicates(
    tmp_path: Path,
    monkeypatch,
    relative_path: str,
    previous: str,
    has_interpreter: bool,
    expected: str,
) -> None:
    module = _load()
    path = tmp_path / relative_path
    _write_elf(path, elf_type=2 if has_interpreter else 3)
    interpreter = "/var/packages/Octop/target/runtime/lib/ld-linux-x86-64.so.2"
    current = {"rpath": previous, "interpreters": []}
    monkeypatch.setattr(
        module.subprocess, "check_output", lambda *_args, **_kwargs: current["rpath"]
    )

    def run(command, **_kwargs):
        if "--set-rpath" in command:
            current["rpath"] = command[-2]
        elif "--set-interpreter" in command:
            current["interpreters"].append(command[-2])
        return subprocess.CompletedProcess(
            command, int("--print-interpreter" in command and not has_interpreter)
        )

    monkeypatch.setattr(module.subprocess, "run", run)
    for _ in range(2):
        assert module.patch_elf(path, tmp_path, 62, interpreter)
        assert current["rpath"] == expected
    assert current["interpreters"] == ([interpreter, interpreter] if has_interpreter else [])


@pytest.mark.parametrize("name", ["libc.so.6", "ld-linux-x86-64.so.2"])
def test_glibc_bootstrap_pair_is_not_modified(tmp_path: Path, monkeypatch, name: str) -> None:
    module = _load()
    path = tmp_path / "runtime" / "lib" / name
    _write_elf(path)

    def unexpected_patchelf(*_args, **_kwargs):
        raise AssertionError("the glibc bootstrap pair must not be patched")

    monkeypatch.setattr(module.subprocess, "run", unexpected_patchelf)
    monkeypatch.setattr(module.subprocess, "check_output", unexpected_patchelf)
    assert not module.patch_elf(
        path, tmp_path, 62, "/var/packages/Octop/target/runtime/lib/ld-linux-x86-64.so.2"
    )


@posix_only
def test_runtime_copies_missing_libraries_and_patches_after_copy(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load()
    (tmp_path / "runtime" / "lib").mkdir(parents=True)
    monkeypatch.setattr(module.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(module, "minimum_kernel", lambda _path: (3, 2, 0))
    versions = {
        "libc6": "2.36-9+deb12u14",
        "libstdc++6": "12.2.0-14+deb12u1",
        "libgcc-s1": "12.2.0-14+deb12u1",
        "zlib1g": "1:1.2.13.dfsg-1",
        "libcrypt1": "1:4.4.33-2",
        "libfribidi0": "1.0.8-2.1",
    }
    monkeypatch.setattr(
        module.subprocess, "check_output", lambda command, **_kwargs: versions[command[-1]]
    )
    copied, patched, sources = [], [], []

    def copyfile(source, destination):
        Path(destination).write_bytes(b"copied library or license")
        copied.append(Path(source))

    def patch(path, *_args):
        assert path.read_bytes() == b"copied library or license"
        patched.append(path.name)
        return True

    monkeypatch.setattr(module.shutil, "copyfile", copyfile)
    monkeypatch.setattr(module, "patch_elf", patch)
    monkeypatch.setattr(
        module,
        "bundle_sources",
        lambda _licenses, _cache, source, version: sources.append((source, version)),
    )
    module.bundle(tmp_path)
    manifest = json.loads((tmp_path / "runtime-compatibility.json").read_text())
    assert {"libz.so.1", "libcrypt.so.1", "libfribidi.so.0"} <= set(manifest["libraries"])
    assert set(manifest["libraries"]) == set(patched)
    assert manifest["sources"] == versions
    assert (tmp_path / "runtime/lib/libfribidi.so").readlink() == Path("libfribidi.so.0")
    assert (tmp_path / "runtime/lib/libfribidi.so").resolve().is_file()
    for package in ("zlib1g", "libcrypt1", "libfribidi0"):
        assert any(path.parts[-2:] == (package, "copyright") for path in copied)
    assert sources == [
        ("glibc", versions["libc6"]),
        ("libxcrypt", versions["libcrypt1"]),
        ("zlib", versions["zlib1g"]),
        ("fribidi", versions["libfribidi0"]),
    ]


@pytest.mark.parametrize(
    ("source", "version", "directory"),
    [
        ("glibc", "2.36-9", "g"),
        ("libxcrypt", "1:4.4.33-2", "libx"),
        ("zlib", "1:1.2.13-1", "z"),
        ("fribidi", "1.0.8-2.1", "f"),
    ],
)
def test_sources_include_verified_upstream_and_debian_patches(
    tmp_path: Path, monkeypatch, source: str, version: str, directory: str
) -> None:
    module = _load()
    licenses, cache = tmp_path / "licenses", tmp_path / "cache"
    licenses.mkdir()
    cache.mkdir()
    upstream_name = f"{source}.orig.tar.xz"
    patch_name = f"{source}.debian.tar.xz"
    archives = {upstream_name: b"upstream source", patch_name: b"Debian packaging patches"}
    dsc = "Checksums-Sha256:\n" + "".join(
        f" {hashlib.sha256(data).hexdigest()} {len(data)} {name}\n"
        for name, data in archives.items()
    )
    description = f"{source}_{version.split(':')[-1]}.dsc"
    base = f"https://deb.debian.org/debian/pool/main/{directory}/{source}/"
    responses = {base + description: dsc.encode(), base + patch_name: archives[patch_name]}
    requested = []
    (cache / upstream_name).write_bytes(archives[upstream_name])

    def urlopen(url, **_kwargs):
        requested.append(url)
        return io.BytesIO(responses[url])

    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    module.bundle_sources(licenses, cache, source, version)
    assert (licenses / description).read_text() == dsc
    assert requested == [base + description, base + patch_name]
    for name, data in archives.items():
        assert (licenses / name).read_bytes() == data
        assert (cache / name).read_bytes() == data


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("mismatch", ["checksum", "size"])
def test_corrupt_sources_are_rejected_before_inclusion(
    tmp_path: Path, monkeypatch, cached: bool, mismatch: str
) -> None:
    module = _load()
    licenses, cache = tmp_path / "licenses", tmp_path / "cache"
    licenses.mkdir()
    cache.mkdir()
    data, name = b"source archive", "libxcrypt.orig.tar.xz"
    digest = "0" * 64 if mismatch == "checksum" else hashlib.sha256(data).hexdigest()
    size = len(data) + (mismatch == "size")
    dsc = f"Checksums-Sha256:\n {digest} {size} {name}\n"
    if cached:
        (cache / name).write_bytes(data)
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda url, **_kwargs: io.BytesIO(dsc.encode() if url.endswith(".dsc") else data),
    )
    with pytest.raises(ValueError, match="source archive checksum mismatch"):
        module.bundle_sources(licenses, cache, "libxcrypt", "1:4.4.33-2")
    assert not (licenses / name).exists()


def test_foreign_elf_is_rejected_before_patching(tmp_path: Path, monkeypatch) -> None:
    module = _load()
    monkeypatch.setattr(module.platform, "machine", lambda: "x86_64")
    header = bytearray(20)
    header[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", header, 18, 183)
    (tmp_path / "foreign.so").write_bytes(header)
    with pytest.raises(ValueError, match="wrong ELF architecture"):
        module.bundle(tmp_path)


def test_linux_minimum_kernel_is_read_from_gnu_abi_note(tmp_path: Path) -> None:
    library = tmp_path / "libc.so.6"
    library.write_bytes(b"prefix" + struct.pack("<III4sIIII", 4, 16, 1, b"GNU\0", 0, 3, 7, 0))
    assert _load().minimum_kernel(library) == (3, 7, 0)


def test_missing_kernel_abi_is_not_assumed_compatible(tmp_path: Path) -> None:
    library = tmp_path / "libc.so.6"
    library.write_bytes(b"not an ELF library")
    with pytest.raises(ValueError, match="no GNU ABI"):
        _load().minimum_kernel(library)
