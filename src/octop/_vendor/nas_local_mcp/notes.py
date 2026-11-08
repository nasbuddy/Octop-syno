"""Note Station writes, using the create/get/set protocol of the my-nas client."""

from contextvars import ContextVar
from dataclasses import asdict
from html.parser import HTMLParser

from octop.i18n import tr

LOCALE = ContextVar("octop_nas_notes_locale", default="en")
WRITES = frozenset({"notes.create", "notes.update", "notes.trash", "notes.restore"})


def describe(operation):
    details = asdict(operation)
    if operation.summary.startswith("synology."):
        details["summary"] = tr(operation.summary, LOCALE.get())
    return details


def _note(data, object_id=None):
    if isinstance(data, dict):
        if isinstance(data.get("object_id"), str) and data["object_id"]:
            return data if object_id is None or data["object_id"] == object_id else None
        for key in ("note", "item", "data", "notes"):
            found = _note(data.get(key), object_id)
            if found is not None:
                return found
    elif isinstance(data, list):
        found = [note for item in data if (note := _note(item, object_id)) is not None]
        if len(found) == 1:
            return found[0]
    return None


class _Brief(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.feed(content)

    def handle_data(self, data):
        self.parts.append(data)

    def text(self):
        return " ".join(" ".join(self.parts).split())[:200]


def _result(status, *, executed=False, **fields):
    return {
        "success": status in {"preview", "verified"},
        "executed": executed,
        "verified": status == "verified",
        "status": status,
        "message": tr("synology.notes." + status, LOCALE.get()),
        **fields,
    }


def _valid(name, params):
    for key in ("object_id", "ver", "parent_id", "title", "content", "brief"):
        if key in params and not isinstance(params[key], str):
            return False
    for key in ("parent_id", "title") if name == "notes.create" else ("object_id", "ver"):
        if not params.get(key, "").strip():
            return False
    if "tag_ids" in params and (
        not isinstance(params["tag_ids"], list)
        or any(not isinstance(tag, str) or not tag.strip() for tag in params["tag_ids"])
    ):
        return False
    return name != "notes.update" or any(
        key in params for key in ("title", "content", "brief", "tag_ids")
    )


def _tags(value):
    if not isinstance(value, list):
        return None
    ids = [tag.get("tag_id") if isinstance(tag, dict) else tag for tag in value]
    return sorted(ids) if all(isinstance(tag, str) for tag in ids) else None


async def operate(dsm, name, params, execute):
    # Imported after runtime initialization: the transport also dispatches here.
    from .nas_mcp import ApiCall

    if not _valid(name, params):
        return _result("invalid")
    try:
        ApiCall.valid_params(params)
    except ValueError:
        return _result("invalid")
    if execute and not dsm.config.allow_writes:
        return _result("writes_disabled")

    def call(method, values):
        return ApiCall(
            api="SYNO.NoteStation.Note", method=method, version=3, params=values, encoding="json"
        )

    async def read(object_id):
        response = await dsm.call(
            ApiCall(
                api="SYNO.NoteStation.Note",
                method="get",
                version=3,
                params={"object_id": object_id},
            )
        )
        return _note(response.get("data"), object_id)

    object_id = params.get("object_id")
    created = False
    attempted = False
    accepted = False
    phase = "prepare"
    try:
        if name == "notes.create":
            expected = {
                "title": params["title"],
                "parent_id": params["parent_id"],
                "content": params.get("content", ""),
            }
            if "brief" in params or "content" in params:
                expected["brief"] = params.get("brief", _Brief(params.get("content", "")).text())
            create = call(
                "create",
                {
                    "parent_id": params["parent_id"],
                    "title": params["title"],
                    "encrypt": False,
                    "commit_msg": {"device": "octop", "listable": False},
                },
            )
            await dsm.prepare(create)
            if not execute:
                return _result(
                    "preview",
                    name=name,
                    request=create.model_dump(),
                    changes=expected,
                    writes_enabled=dsm.config.allow_writes,
                    save_body_after_create=True,
                )
            phase, attempted = "create", True
            response = await dsm.call(create)
            accepted = True
            identity = _note(response.get("data"))
            if identity is None:
                return _result(
                    "write_unconfirmed",
                    executed=True,
                    phase=phase,
                    parent_id=params["parent_id"],
                    title=params["title"],
                )
            object_id, created = identity["object_id"], True

        phase = "read"
        current = await read(object_id)
        if (
            current is None
            or not isinstance(current.get("ver"), str)
            or not current["ver"]
            or "content" not in current
            or "title" not in current
        ):
            return _result("unreadable", executed=attempted, object_id=object_id, created=created)
        if current.get("encrypt"):
            return _result("encrypted", executed=attempted, object_id=object_id, created=created)
        if not created and current["ver"] != params["ver"]:
            return _result("conflict", object_id=object_id, current_ver=current["ver"])
        if created and any(current.get(key) != expected[key] for key in ("title", "parent_id")):
            return _result(
                "mismatch",
                executed=True,
                object_id=object_id,
                created=True,
                note=current,
                untrusted_content=True,
            )
        if created and current["content"]:
            return _result(
                "conflict",
                executed=True,
                object_id=object_id,
                created=True,
                current_ver=current["ver"],
            )

        if name in {"notes.create", "notes.update"}:
            if current.get("recycle"):
                return _result("recycled", object_id=object_id)
            changes = {key: params[key] for key in ("title", "content", "brief") if key in params}
            if "content" in params and "brief" not in changes:
                changes["brief"] = _Brief(params["content"]).text()
            values = {
                "object_id": object_id,
                "ver": current["ver"],
                "check_conflict": True,
                "commit_msg": {"device": "octop", "listable": False},
                **changes,
            }
            if "tag_ids" in params:
                values["tag"] = [params["tag_ids"]]
            request = call("set", values)
            if not created:
                expected = {
                    key: current[key]
                    for key in ("title", "content", "brief", "parent_id", "attachment", "tag")
                    if key in current
                }
            expected.update(changes)
            if "tag_ids" in params:
                expected["tag"] = params["tag_ids"]
            # Empty creation needs only the create call and its read-back.
            needs_write = not created or bool(params.get("content")) or "brief" in params
        else:
            expected = {"recycle": name == "notes.trash"}
            values = {"object_id": [object_id]}
            if name == "notes.trash":
                values["recycle"] = True
            request = call("delete" if name == "notes.trash" else "restore", values)
            needs_write = True

        await dsm.prepare(request)
        if not execute:
            return _result(
                "preview",
                name=name,
                object_id=object_id,
                ver=current["ver"],
                request=request.model_dump(),
                writes_enabled=dsm.config.allow_writes,
            )
        if needs_write:
            phase, attempted, accepted = "save", True, False
            await dsm.call(request)
            accepted = True
            phase = "verify"
            current = await read(object_id)
        if current is None:
            return _result(
                "unreadable",
                executed=True,
                object_id=object_id,
                created=created,
                write_accepted=accepted,
            )
        mismatches = [
            key
            for key, value in expected.items()
            if (
                _tags(current.get(key)) != _tags(value)
                if key == "tag" and "tag_ids" in params
                else current.get(key) != value
            )
        ]
        return _result(
            "mismatch" if mismatches else "verified",
            executed=True,
            object_id=object_id,
            created=created,
            write_accepted=accepted,
            note=current,
            mismatched_fields=mismatches,
            untrusted_content=True,
        )
    except ValueError:
        return _result(
            "write_unconfirmed" if attempted else "request_failed",
            executed=attempted,
            object_id=object_id,
            created=created,
            write_accepted=accepted,
            phase=phase,
        )
