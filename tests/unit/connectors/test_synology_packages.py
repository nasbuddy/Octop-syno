from __future__ import annotations

import json
from urllib.parse import parse_qs

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from octop._vendor.nas_local_mcp import nas_mcp as runtime


class PackageNas:
    def __init__(self):
        self.calls = []
        self.version = "1.0-1"
        self.status = "running"
        self.finished = False
        self.task_failed = False
        self.installation_version = 2
        self.timeout_after_submit = False
        self.catalog = {
            "id": "Demo",
            "dname": "演示应用",
            "version": "2.0-2",
            "link": "https://packages.example.invalid/Demo.spk",
            "md5": "a" * 32,
            "size": 12345,
        }

    def request(self, request):
        fields = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        self.calls.append(fields)
        api, method = fields["api"], fields["method"]
        if api == "SYNO.API.Info":
            data = {
                "SYNO.Core.Package.Server": {"path": "entry.cgi", "minVersion": 2, "maxVersion": 3},
                "SYNO.Core.Package": {"path": "entry.cgi", "minVersion": 1, "maxVersion": 2},
                "SYNO.Core.Package.Control": {
                    "path": "entry.cgi",
                    "minVersion": 1,
                    "maxVersion": 1,
                },
                "SYNO.Core.Package.Installation": {
                    "path": "entry.cgi",
                    "minVersion": 1,
                    "maxVersion": self.installation_version,
                },
                "SYNO.Core.Package.Installation.Download": {
                    "path": "entry.cgi",
                    "minVersion": 1,
                    "maxVersion": 1,
                },
            }
        elif api == "SYNO.Core.Package.Server":
            assert fields["version"] == "3"
            data = {"packages": [self.catalog]}
        elif api == "SYNO.Core.Package.Control":
            assert fields["id"] == "Demo"
            self.status = "running" if method == "start" else "stopped"
            data = {}
        elif api == "SYNO.Core.Package" and method == "feasibility_check":
            assert json.loads(fields["packages"]) == ["Demo"]
            assert fields["type"] == "install_check"
            data = {"installable": True}
        elif api == "SYNO.Core.Package" and method == "get":
            data = {
                "id": "Demo",
                "version": "2.0-2" if self.finished and not self.task_failed else self.version,
                "additional": {"status": self.status},
            }
        elif method == "get_queue":
            assert json.loads(fields["pkgs"])[0]["pkg"] == "Demo"
            data = {"queue": [{"pkg": "Demo", "operation": "install", "version": "2.0-2"}]}
        elif method == "get":
            data = {"volumes": [{"volume_path": "/volume2"}]}
        elif method in {"install", "upgrade"}:
            expected_name = "Demo" if method == "install" else "演示应用"
            assert json.loads(fields["name"]) == expected_name
            assert json.loads(fields["url"]) == self.catalog["link"]
            assert json.loads(fields["checksum"]) == self.catalog["md5"]
            assert fields["filesize"] == "12345"
            assert fields["check_codesign"] == "true" and fields["force"] == "false"
            if method == "install":
                assert fields["volume_path"] == "/volume2"
                assert json.loads(fields["operation"]) == "install"
                assert fields["installrunpackage"] == "false"
            if self.timeout_after_submit:
                raise httpx.ReadTimeout("simulated", request=request)
            data = {"progress": 0, "data": {"taskid": "@synopkg_download_12", "status": "download"}}
        elif method == "status":
            assert json.loads(fields["task_id"]) == "@synopkg_download_12"
            data = {
                "finished": self.finished,
                "success": self.finished and not self.task_failed,
                "status": "failed"
                if self.task_failed
                else "installed"
                if self.finished
                else "download",
            }
        elif method == "check":
            assert json.loads(fields["taskid"]) == "@synopkg_download_12"
            data = {
                "status": "running" if self.finished else "non_installed",
                "codesign_error": None,
            }
        else:
            raise AssertionError((api, method))
        return httpx.Response(200, json={"success": True, "data": data})

    @property
    def writes(self):
        return [
            call for call in self.calls if call["method"] in {"install", "upgrade", "start", "stop"}
        ]

    def install_params(self):
        return {
            "id": "Demo",
            "url": self.catalog["link"],
            "checksum": self.catalog["md5"],
            "filesize": self.catalog["size"],
            "volume_path": "/volume2",
        }


@pytest.fixture
def nas(tmp_path):
    fake = PackageNas()
    config = runtime.Config(
        url="http://packages.invalid",
        sid="synthetic-package-session",
        allow_http=True,
        allow_writes=True,
        transfer_dir=str(tmp_path),
    )
    runtime.CACHE.clear()
    a = runtime.EMBEDDED_CONFIG.set(config)
    b = runtime.EMBEDDED_TRANSPORT.set(lambda: httpx.MockTransport(fake.request))
    c = runtime.notes.LOCALE.set("zh")
    yield fake, config
    runtime.notes.LOCALE.reset(c)
    runtime.EMBEDDED_TRANSPORT.reset(b)
    runtime.EMBEDDED_CONFIG.reset(a)
    runtime.CACHE.clear()


async def test_catalog_selects_the_registered_version_and_preflight_never_writes(nas):
    fake, _ = nas
    catalog = await runtime.nas_operate("packages.catalog")
    assert catalog["data"]["packages"][0]["id"] == "Demo"
    await runtime.nas_operate("packages.install_settings")
    await runtime.nas_operate("packages.feasibility", {"packages": ["Demo"]})
    queue = await runtime.nas_operate(
        "packages.queue", {"pkgs": [{"pkg": "Demo", "version": "2.0-2", "beta": False}]}
    )
    assert queue["data"]["queue"][0]["pkg"] == "Demo" and not fake.writes
    metadata = await runtime.nas_operations("套件源目录")
    assert metadata["items"][0]["registered_version"]


async def test_install_preview_then_submit_and_verify_task_and_installed_version(nas):
    fake, _ = nas
    params = fake.install_params()
    preview = await runtime.nas_operate("packages.install", params)
    assert not preview["executed"] and not fake.writes
    result = await runtime.nas_operate("packages.install", params, execute=True)
    assert result["data"]["data"]["taskid"] == "@synopkg_download_12"
    running = await runtime.nas_operate(
        "packages.install_status", {"task_id": "@synopkg_download_12"}
    )
    assert not running["data"]["finished"]
    old = await runtime.nas_operate("packages.get", {"id": "Demo"})
    assert old["data"]["version"] == "1.0-1"
    fake.finished = True
    finished = await runtime.nas_operate(
        "packages.install_status", {"task_id": "@synopkg_download_12"}
    )
    assert finished["data"]["finished"] and finished["data"]["success"]
    installed = await runtime.nas_operate("packages.get", {"id": "Demo"})
    assert installed["data"]["version"] == "2.0-2" and len(fake.writes) == 1


async def test_upgrade_uses_catalog_display_name_and_retains_signature_checks(nas):
    fake, _ = nas
    params = {key: value for key, value in fake.install_params().items() if key != "volume_path"}
    params["name"] = "演示应用"
    assert not (await runtime.nas_operate("packages.upgrade", params))["executed"]
    assert not fake.writes
    result = await runtime.nas_operate("packages.upgrade", params, execute=True)
    assert result["success"] and fake.writes[0]["method"] == "upgrade"
    assert "volume_path" not in fake.writes[0]


async def test_start_and_stop_remain_available_with_preview_and_state_query(nas):
    fake, _ = nas
    assert not (await runtime.nas_operate("packages.stop", {"id": "Demo"}))["executed"]
    assert not fake.writes
    await runtime.nas_operate("packages.stop", {"id": "Demo"}, execute=True)
    assert (await runtime.nas_operate("packages.get", {"id": "Demo"}))["data"]["additional"][
        "status"
    ] == "stopped"
    await runtime.nas_operate("packages.start", {"id": "Demo"}, execute=True)
    assert (await runtime.nas_operate("packages.get", {"id": "Demo"}))["data"]["additional"][
        "status"
    ] == "running"


async def test_upgrade_cannot_use_a_host_display_name_with_a_different_id(nas):
    fake, _ = nas
    params = {key: value for key, value in fake.install_params().items() if key != "volume_path"}
    params["name"] = "Octop-syno"
    result = await runtime.nas_operate("packages.upgrade", params, execute=True)
    assert result["status"] == "self_control" and not fake.calls


async def test_download_checkpoint_and_terminal_failure_are_not_reported_as_installed(nas):
    fake, _ = nas
    downloaded = await runtime.nas_operate(
        "packages.download_status", {"taskid": "@synopkg_download_12"}
    )
    assert downloaded["data"]["status"] == "non_installed"
    fake.finished = fake.task_failed = True
    status = await runtime.nas_operate(
        "packages.install_status", {"task_id": "@synopkg_download_12"}
    )
    assert status["data"]["finished"] and not status["data"]["success"]
    assert (await runtime.nas_operate("packages.get", {"id": "Demo"}))["data"]["version"] == "1.0-1"


@pytest.mark.parametrize(
    "name,params",
    [
        ("packages.stop", {"id": "Octop"}),
        ("packages.stop", {"id": "NasMCP"}),
        (
            "packages.install",
            {
                "id": "Octop",
                "url": "https://example.invalid/a",
                "checksum": "a" * 32,
                "filesize": 1,
                "volume_path": "/volume1",
            },
        ),
        (
            "packages.upgrade",
            {
                "id": "Octop",
                "name": "Octop-syno",
                "url": "https://example.invalid/a",
                "checksum": "a" * 32,
                "filesize": 1,
            },
        ),
    ],
)
async def test_cannot_interrupt_the_package_hosting_the_current_mcp(nas, name, params):
    fake, _ = nas
    result = await runtime.nas_operate(name, params, execute=True)
    assert result["status"] == "self_control" and not fake.calls


@pytest.mark.parametrize(
    "key,value",
    [
        ("id", "../bad"),
        ("url", "file:///etc/passwd"),
        ("url", "https://user:secret@example.invalid/a.spk"),
        ("checksum", "bad-md5"),
        ("filesize", -1),
        ("filesize", True),
        ("volume_path", "/etc"),
    ],
)
async def test_invalid_package_inputs_are_rejected_before_network_calls(nas, key, value):
    fake, _ = nas
    params = {**fake.install_params(), key: value}
    result = await runtime.nas_operate("packages.install", params, execute=True)
    assert result["status"] == "invalid" and not fake.calls
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize(
    "name", ["packages.install", "packages.upgrade", "packages.stop", "packages.start"]
)
async def test_every_package_write_honors_connector_write_permission(nas, name):
    fake, config = nas
    config.allow_writes = False
    params = fake.install_params() if name == "packages.install" else {"id": "Demo"}
    if name == "packages.upgrade":
        params = {
            key: value for key, value in fake.install_params().items() if key != "volume_path"
        }
        params["name"] = "演示应用"
    result = await runtime.nas_operate(name, params, execute=True)
    assert result["status"] == "writes_disabled" and not fake.writes


@pytest.mark.parametrize(
    "override", [{"force": True}, {"check_codesign": False}, {"operation": "uninstall"}]
)
async def test_install_cannot_disable_signature_checks_force_or_change_operation(nas, override):
    fake, _ = nas
    with pytest.raises(ToolError):
        await runtime.nas_operate(
            "packages.install", {**fake.install_params(), **override}, execute=True
        )
    assert not fake.writes


async def test_catalog_refresh_requires_real_booleans(nas):
    fake, _ = nas
    result = await runtime.nas_operate("packages.catalog", {"blloadothers": "false"})
    assert result["status"] == "invalid" and not fake.calls


async def test_submission_timeout_is_not_automatically_retried(nas):
    fake, _ = nas
    fake.timeout_after_submit = True
    with pytest.raises(ToolError):
        await runtime.nas_operate("packages.install", fake.install_params(), execute=True)
    assert len(fake.writes) == 1


async def test_localized_package_descriptions_are_searchable(nas):
    for locale, term in (("zh", "升级任务"), ("en", "package upgrade")):
        token = runtime.notes.LOCALE.set(locale)
        try:
            result = await runtime.nas_operations(term)
            assert any(item["name"] == "packages.upgrade" for item in result["items"])
        finally:
            runtime.notes.LOCALE.reset(token)
