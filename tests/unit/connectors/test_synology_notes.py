from __future__ import annotations

import copy
import json
from urllib.parse import parse_qs

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from octop._vendor.nas_local_mcp import nas_mcp as runtime


class NoteNas:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.note = {
            "object_id": "note-1",
            "parent_id": "book-1",
            "title": "已有标题",
            "content": '<p>原文<img ref="image-1"></p>',
            "brief": "原文",
            "ver": "001",
            "encrypt": False,
            "recycle": False,
            "attachment": {"file-1": {"ref": "image-1", "ext": "png"}},
            "tag": [{"tag_id": "tag-1"}],
        }
        self.api_version = 3
        self.reject_set = False
        self.timeout_after_set = False
        self.race_on_set = False
        self.fail_read_after_write = False
        self.bad_readback = False
        self.readback_wrapper = "note"
        self.created: list[str] = []

    def request(self, request: httpx.Request) -> httpx.Response:
        fields = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        values = {}
        for key, value in fields.items():
            try:
                values[key] = json.loads(value)
            except json.JSONDecodeError:
                values[key] = value
        self.calls.append(values)
        if fields["api"] == "SYNO.API.Info":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "SYNO.NoteStation.Note": {
                            "path": "entry.cgi",
                            "minVersion": 1,
                            "maxVersion": self.api_version,
                        },
                    },
                },
            )
        method = fields["method"]
        if method == "list":
            assert values["filter"]["recycle"] is True
            data = {"notes": [copy.deepcopy(self.note)] if self.note["recycle"] else []}
        elif method == "get":
            if self.fail_read_after_write and any(
                call.get("method") == "set" for call in self.calls
            ):
                return httpx.Response(503)
            note = copy.deepcopy(self.note)
            if self.bad_readback and any(call.get("method") == "set" for call in self.calls):
                note["content"] = "server did not retain requested body"
            data = {self.readback_wrapper: note} if self.readback_wrapper != "list" else [note]
        elif method == "create":
            assert values["encrypt"] is False
            assert fields["parent_id"] == json.dumps("book-1")
            assert json.loads(fields["title"]) == values["title"]
            self.created.append("note-created")
            self.note = {
                **self.note,
                "object_id": "note-created",
                "title": values["title"],
                "content": "",
                "brief": "",
                "attachment": {},
                "tag": [],
                "ver": "created-1",
            }
            data = {"object_id": "note-created"}
        elif method == "set":
            if self.race_on_set:
                self.note["ver"] = "concurrent-revision"
                return httpx.Response(200, json={"success": False, "error": {"code": 105}})
            assert values["object_id"] == self.note["object_id"]
            assert values["ver"] == self.note["ver"]
            assert values["check_conflict"] is True
            if self.reject_set:
                return httpx.Response(200, json={"success": False, "error": {"code": 105}})
            assert "attachment" not in values and "images" not in values
            for key in ("title", "content", "brief"):
                if key in values:
                    self.note[key] = values[key]
            if "tag" in values:
                assert len(values["tag"]) == 1 and isinstance(values["tag"][0], list)
                self.note["tag"] = [{"tag_id": tag} for tag in values["tag"][0]]
            self.note["ver"] = "next-" + self.note["ver"]
            if self.timeout_after_set:
                raise httpx.ReadTimeout("simulated", request=request)
            data = {"data": [{"object_id": self.note["object_id"], "ver": self.note["ver"]}]}
        elif method in ("delete", "restore"):
            assert values["object_id"] == [self.note["object_id"]]
            if method == "delete":
                assert values["recycle"] is True
            self.note["recycle"] = method == "delete"
            self.note["ver"] = "next-" + self.note["ver"]
            data = {}
        else:
            raise AssertionError(method)
        return httpx.Response(200, json={"success": True, "data": data})

    @property
    def mutations(self) -> list[dict]:
        return [
            call
            for call in self.calls
            if call.get("method") in {"create", "set", "delete", "restore"}
        ]


@pytest.fixture
def nas(tmp_path):
    fake = NoteNas()
    config = runtime.Config(
        url="http://nas.invalid",
        sid="synthetic-session",
        allow_http=True,
        allow_writes=True,
        transfer_dir=str(tmp_path),
    )
    runtime.CACHE.clear()
    config_token = runtime.EMBEDDED_CONFIG.set(config)
    transport_token = runtime.EMBEDDED_TRANSPORT.set(lambda: httpx.MockTransport(fake.request))
    locale_token = runtime.notes.LOCALE.set("zh")
    yield fake, config
    runtime.notes.LOCALE.reset(locale_token)
    runtime.EMBEDDED_TRANSPORT.reset(transport_token)
    runtime.EMBEDDED_CONFIG.reset(config_token)
    runtime.CACHE.clear()


async def test_create_previews_then_creates_saves_and_reads_back_once(nas):
    fake, _ = nas
    params = {"parent_id": "book-1", "title": '中文 "标题" 🐙', "content": "<p>正文 &amp; 引用</p>"}
    preview = await runtime.nas_operate("notes.create", params)
    assert preview["status"] == "preview" and preview["executed"] is False
    assert not fake.mutations
    result = await runtime.nas_operate("notes.create", params, execute=True)
    assert result["verified"] and result["object_id"] == "note-created"
    assert result["note"]["content"] == params["content"]
    assert result["note"]["brief"] == "正文 & 引用"
    assert [call["method"] for call in fake.mutations] == ["create", "set"]
    assert sum(call.get("method") == "get" for call in fake.calls) == 2


async def test_empty_note_creation_does_not_submit_an_extra_save(nas):
    fake, _ = nas
    result = await runtime.nas_operate(
        "notes.create", {"parent_id": "book-1", "title": "空笔记"}, execute=True
    )
    assert result["verified"]
    assert [call["method"] for call in fake.mutations] == ["create"]


@pytest.mark.parametrize("wrapper", ["note", "item", "data", "notes", "list"])
async def test_title_only_update_preserves_rich_body_attachments_and_tags(nas, wrapper):
    fake, _ = nas
    fake.readback_wrapper = wrapper
    original = copy.deepcopy(fake.note)
    result = await runtime.nas_operate(
        "notes.update", {"object_id": "note-1", "ver": "001", "title": "改名"}, execute=True
    )
    assert result["verified"] and result["note"]["title"] == "改名"
    for key in ("content", "brief", "attachment", "parent_id", "tag"):
        assert fake.note[key] == original[key]
    request = fake.mutations[0]
    assert "content" not in request and "tag" not in request and "attachment" not in request


async def test_update_body_and_tags_can_preview_then_verify_real_detail(nas):
    fake, _ = nas
    original_attachment = copy.deepcopy(fake.note["attachment"])
    params = {
        "object_id": "note-1",
        "ver": "001",
        "content": "<p>新正文</p>",
        "tag_ids": ["tag-2", "tag-3"],
    }
    preview = await runtime.nas_operate("notes.update", params)
    assert preview["status"] == "preview" and not fake.mutations
    result = await runtime.nas_operate("notes.update", params, execute=True)
    assert result["verified"] and result["note"]["ver"] != "001"
    assert fake.note["attachment"] == original_attachment
    assert fake.mutations[0]["tag"] == [["tag-2", "tag-3"]]


@pytest.mark.parametrize(
    "change",
    [
        {"ver": "newer"},
        {"encrypt": True},
        {"recycle": True},
        {"ver": ""},
        {"object_id": "different"},
    ],
)
async def test_stale_encrypted_recycled_or_incomplete_detail_blocks_writes(nas, change):
    fake, _ = nas
    fake.note.update(change)
    result = await runtime.nas_operate(
        "notes.update", {"object_id": "note-1", "ver": "001", "title": "改名"}, execute=True
    )
    assert not result["success"] and not fake.mutations


async def test_edit_after_preview_refuses_a_newer_revision(nas):
    fake, _ = nas
    params = {"object_id": "note-1", "ver": "001", "content": "<p>新正文</p>"}
    assert (await runtime.nas_operate("notes.update", params))["status"] == "preview"
    fake.note["ver"] = "002"
    result = await runtime.nas_operate("notes.update", params, execute=True)
    assert result["status"] == "conflict" and not fake.mutations
    assert "版本已变化" in result["message"]


@pytest.mark.parametrize(
    "name,params",
    [
        ("notes.create", {"parent_id": "book-1", "title": "新笔记"}),
        ("notes.update", {"object_id": "note-1", "ver": "001", "title": "新标题"}),
        ("notes.trash", {"object_id": "note-1", "ver": "001"}),
        ("notes.restore", {"object_id": "note-1", "ver": "001"}),
    ],
)
async def test_disabled_connector_never_sends_a_write(nas, name, params):
    fake, config = nas
    config.allow_writes = False
    result = await runtime.nas_operate(name, params, execute=True)
    assert result["status"] == "writes_disabled" and not fake.mutations


@pytest.mark.parametrize(
    "params",
    [
        {"object_id": "note-1", "ver": "", "title": "标题"},
        {"object_id": "note-1", "ver": "001", "content": {"unsafe": "object"}},
        {"object_id": "note-1", "ver": "001", "tag_ids": "not-a-list"},
        {"object_id": "note-1", "ver": "001"},
    ],
)
async def test_invalid_edit_arguments_never_reach_the_api(nas, params):
    fake, _ = nas
    result = await runtime.nas_operate("notes.update", params, execute=True)
    assert result["status"] == "invalid" and not fake.calls


async def test_second_step_failure_returns_created_id_without_creating_again(nas):
    fake, _ = nas
    fake.reject_set = True
    result = await runtime.nas_operate(
        "notes.create",
        {"parent_id": "book-1", "title": "新笔记", "content": "<p>正文</p>"},
        execute=True,
    )
    assert not result["success"] and result["created"]
    assert result["object_id"] == "note-created" and result["phase"] == "save"
    assert fake.created == ["note-created"]


async def test_timeout_after_a_committed_save_is_not_retried(nas):
    fake, _ = nas
    fake.timeout_after_set = True
    result = await runtime.nas_operate(
        "notes.update", {"object_id": "note-1", "ver": "001", "title": "已保存"}, execute=True
    )
    assert result["status"] == "write_unconfirmed" and result["object_id"] == "note-1"
    assert len(fake.mutations) == 1 and fake.note["title"] == "已保存"


async def test_server_conflict_during_save_never_forces_or_retries(nas):
    fake, _ = nas
    original = fake.note["content"]
    fake.race_on_set = True
    result = await runtime.nas_operate(
        "notes.update",
        {"object_id": "note-1", "ver": "001", "content": "<p>改动</p>"},
        execute=True,
    )
    assert result["status"] == "write_unconfirmed"
    assert fake.note["content"] == original and len(fake.mutations) == 1
    assert fake.mutations[0]["check_conflict"] is True


async def test_oversized_body_is_rejected_before_creating_an_empty_note(nas):
    fake, _ = nas
    result = await runtime.nas_operate(
        "notes.create",
        {"parent_id": "book-1", "title": "新笔记", "content": "x" * runtime.MAX_JSON},
        execute=True,
    )
    assert result["status"] == "invalid" and not fake.calls


async def test_recycle_bin_can_be_browsed_before_restoring(nas):
    fake, _ = nas
    fake.note["recycle"] = True
    result = await runtime.nas_operate("notes.recycled")
    assert result["data"]["notes"][0]["object_id"] == "note-1"
    assert not fake.mutations


async def test_successful_save_with_failed_readback_does_not_claim_completion(nas):
    fake, _ = nas
    fake.fail_read_after_write = True
    result = await runtime.nas_operate(
        "notes.update", {"object_id": "note-1", "ver": "001", "title": "已接受"}, execute=True
    )
    assert not result["verified"] and result["write_accepted"]
    assert len(fake.mutations) == 1


async def test_incorrect_readback_is_reported_as_mismatch(nas):
    fake, _ = nas
    fake.bad_readback = True
    result = await runtime.nas_operate(
        "notes.update",
        {"object_id": "note-1", "ver": "001", "content": "<p>新正文</p>"},
        execute=True,
    )
    assert result["status"] == "mismatch" and "content" in result["mismatched_fields"]


async def test_trash_and_restore_are_previewed_and_never_permanently_delete(nas):
    fake, _ = nas
    params = {"object_id": "note-1", "ver": "001"}
    assert (await runtime.nas_operate("notes.trash", params))["status"] == "preview"
    assert not fake.mutations
    trashed = await runtime.nas_operate("notes.trash", params, execute=True)
    assert trashed["verified"] and fake.note["recycle"]
    restored = await runtime.nas_operate(
        "notes.restore", {"object_id": "note-1", "ver": fake.note["ver"]}, execute=True
    )
    assert restored["verified"] and not fake.note["recycle"]
    with pytest.raises(ToolError):
        await runtime.nas_operate("notes.trash", {**params, "recycle": False}, execute=True)


async def test_unsupported_api_version_never_mutates(nas):
    fake, _ = nas
    fake.api_version = 2
    result = await runtime.nas_operate(
        "notes.create", {"parent_id": "book-1", "title": "新笔记"}, execute=True
    )
    assert result["status"] == "request_failed" and not fake.mutations


async def test_new_recipe_descriptions_and_errors_follow_request_locale(nas):
    _, config = nas
    config.allow_writes = False
    for locale, word in (("zh", "创建笔记"), ("en", "Create a note")):
        token = runtime.notes.LOCALE.set(locale)
        try:
            catalog = await runtime.nas_operations("notes.create")
            assert word in catalog["items"][0]["summary"]
            localized = await runtime.nas_operations(word)
            assert any(item["name"] == "notes.create" for item in localized["items"])
            result = await runtime.nas_operate(
                "notes.create", {"parent_id": "book-1", "title": "新笔记"}, execute=True
            )
            assert ("未允许写入" if locale == "zh" else "Writes are disabled") in result["message"]
        finally:
            runtime.notes.LOCALE.reset(token)
