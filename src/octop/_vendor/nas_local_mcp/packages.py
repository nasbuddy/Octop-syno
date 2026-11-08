"""Package Center request formats from my-nas lib/api/api.dart.

Installation is asynchronous: a successful submission still needs task/status
queries and a final installed-version check by the calling expert.
"""

import json
import re
from urllib.parse import urlsplit

from octop.i18n import tr

from .notes import LOCALE

OPERATIONS = frozenset(
    {
        "packages.catalog",
        "packages.install_settings",
        "packages.feasibility",
        "packages.queue",
        "packages.install",
        "packages.upgrade",
        "packages.install_status",
        "packages.download_status",
        "packages.start",
        "packages.stop",
    }
)
WRITES = frozenset({"packages.start", "packages.stop", "packages.install", "packages.upgrade"})
_HOST_PACKAGES = {"octop", "octop-syno", "nasmcp"}


class PackageError(ValueError):
    pass


def blocked(key):
    return {
        "success": False,
        "executed": False,
        "status": key,
        "message": tr("synology.packages." + key, LOCALE.get()),
    }


def _require(condition, key="invalid"):
    if not condition:
        raise PackageError(key)


def _id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value)


def prepare(name, operation, params):
    from .nas_mcp import ApiCall

    values = {**operation.defaults, **params}
    quoted = ()
    if name in {"packages.start", "packages.stop", "packages.install", "packages.upgrade"}:
        _require(_id(params.get("id")))
        if name != "packages.start":
            _require(params["id"].casefold() not in _HOST_PACKAGES, "self_control")
    if name in {"packages.install", "packages.upgrade"}:
        _require(isinstance(params.get("url"), str))
        url = urlsplit(params["url"])
        _require(
            url.scheme in {"https", "http"}
            and url.hostname
            and not url.username
            and not url.password
        )
        _require(
            isinstance(params.get("checksum"), str)
            and re.fullmatch(r"[0-9a-fA-F]{32}", params["checksum"])
        )
        _require(type(params.get("filesize")) is int and params["filesize"] > 0)
        values.pop("id")
        if name == "packages.install":
            _require(
                isinstance(params.get("volume_path"), str)
                and re.fullmatch(r"/volume[1-9][0-9]*", params["volume_path"])
            )
            values.update(
                name=params["id"],
                type=0,
                blqinst=False,
                operation="install",
                installrunpackage=False,
            )
        else:
            # The legacy upgrade endpoint uses the catalog dname, not its id.
            _require(isinstance(params.get("name"), str) and params["name"].strip())
            _require(params["name"].strip().casefold() not in _HOST_PACKAGES, "self_control")
        values.update(check_codesign=True, force=False)
        quoted = ("name", "url", "checksum", "operation")
    elif name in {"packages.install_status", "packages.download_status"}:
        key = "task_id" if name == "packages.install_status" else "taskid"
        _require(isinstance(params.get(key), str) and params[key].strip())
        quoted = (key,)
    elif name == "packages.feasibility":
        _require(
            isinstance(params.get("packages"), list)
            and params["packages"]
            and all(_id(item) for item in params["packages"])
        )
        _require(values["type"] == "install_check")
    elif name == "packages.queue":
        _require(isinstance(params.get("pkgs"), list) and params["pkgs"])
        for item in params["pkgs"]:
            _require(isinstance(item, dict) and _id(item.get("pkg")))
            _require(not (set(item) - {"pkg", "version", "operation", "beta"}))
            _require(item.get("operation", "install") == "install")
            _require("beta" not in item or type(item["beta"]) is bool)
            _require("version" not in item or isinstance(item["version"], str))
    elif name == "packages.catalog":
        _require(all(type(value) is bool for value in values.values()))
    for key in quoted:
        if key in values:
            values[key] = json.dumps(values[key], ensure_ascii=False)
    return ApiCall(
        api=operation.api,
        method=operation.method,
        version=operation.version,
        params=values,
        encoding="form",
    )
