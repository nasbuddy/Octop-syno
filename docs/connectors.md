# Built-in connectors

**English** · [中文](#内置连接器)

Octop ships a catalog of OAuth / MCP connectors. Dashboard copy (`name`,
`description`, `auth_hint`, and credential-field labels) is bilingual (`en` /
`zh`) and follows `Accept-Language`.

**Source of truth:** [`src/octop/infra/connectors/catalog.json`](../src/octop/infra/connectors/catalog.json).
`src/octop/infra/connectors/catalog.py` only loads and validates that file.

You can also add **custom MCP** servers in the dashboard; they are not listed here.

# 内置连接器

[English](#built-in-connectors) · **中文**

Octop 内置一组 OAuth / MCP 连接器。控制台展示的名称、描述、授权提示和凭证字段
文案支持中英双语，跟随 `Accept-Language`。

**元数据源：** [`src/octop/infra/connectors/catalog.json`](../src/octop/infra/connectors/catalog.json)。
`catalog.py` 只负责加载和校验，不再手写 `_CATALOG`。

控制台还可以添加**自定义 MCP**，不在下表中。完整目录见下方表格。

## Catalog / 目录

The table below must match `catalog.json` (kind, English name, Chinese name,
category, auth, MCP mode, and order). Do not edit the rows by hand unless you
are updating `catalog.json` in the same change.

下表必须与 `catalog.json` 一致（`kind`、英文名、中文名、分类、鉴权、MCP 模式、顺序）。
改连接器时先改 JSON，再改此表。

| Kind | Name | 名称 | Category | Auth | MCP mode |
|------|------|------|----------|------|----------|
| `synology-nas` | Synology NAS | 群晖 NAS | self_hosted | custom_fields | internal |
| `tencent-docs` | Tencent Docs | 腾讯文档 | office | personal_token | remote |
| `tencent-ima` | Tencent IMA | 腾讯 IMA | knowledge | api_key | gateway |
| `tencent-meeting` | Tencent Meeting | 腾讯会议 | office | personal_token | remote |
| `tencent-news` | Tencent News | 腾讯新闻 | media | api_key | gateway |
| `wechat-reading` | Weixin Reading | 微信读书 | media | api_key | gateway |
| `tencent-lexiang` | Tencent Lexiang | 腾讯乐享 | office | api_key | remote |
| `tencent-weiyun` | Tencent Weiyun | 腾讯微云 | office | personal_token | remote |
| `qq-mail` | Personal Mail | 个人邮箱 | productivity | imap_app_password | gateway |
| `qq-music` | QQ Music | QQ 音乐 | media | api_key | gateway |
| `fliggy` | Fliggy | 飞猪 | travel | api_key | gateway |
| `baidu-map` | Baidu Maps | 百度地图 | travel | api_key | gateway |
| `ctrip-wendao` | Trip.com Wendao | 携程问道 | travel | api_key | gateway |
| `meituan-travel` | Meituan Travel | 美团旅游助手 | travel | api_key | gateway |
| `didi` | DiDi | 滴滴 | travel | api_key | remote |
| `yuandian` | Yuandian | 元典 | professional | api_key | gateway |
| `qcc` | Qichacha | 企查查 | professional | oauth2 | internal |
| `tencent-ardot` | Tencent Ardot | 腾讯设计 Ardot | office | oauth2 | remote |
| `youdao-note` | Youdao Note | 有道云笔记 | knowledge | personal_token | remote |
| `notion` | Notion | Notion | knowledge | oauth2 | remote |
| `openalex` | OpenAlex | OpenAlex | knowledge | oauth2 | remote |
| `dida365` | TickTick | 滴答清单 | productivity | oauth2 | remote |
| `feishu-cli` | Feishu CLI | 飞书 CLI | office | api_key | gateway |
| `wecom-cli` | WeCom CLI | 企业微信 CLI | office | api_key | gateway |
| `dingtalk-cli` | DingTalk CLI | 钉钉 CLI | office | custom_fields | gateway |
| `agently-cli` | Agent Mail | Agent Mail | office | custom_fields | gateway |
| `obsidian-cli` | Obsidian | Obsidian | knowledge | custom_fields | gateway |
| `yuque-mcp` | Yuque (official MCP) | 语雀（官方 MCP） | knowledge | personal_token | stdio |
| `ragflow` | ragflow | ragflow | knowledge | custom_fields | gateway |
| `weknora` | WeKnora | WeKnora | knowledge | custom_fields | gateway |
| `dify` | Dify | Dify | self_hosted | custom_fields | remote |

## MCP modes / MCP 模式

| Mode | Meaning | 含义 |
|------|---------|------|
| `remote` | The harness talks to the vendor MCP URL. | Harness 直连厂商 MCP 地址。 |
| `gateway` | An in-process Python adapter; the harness config is a name-only placeholder. | 进程内 Python 适配器；Harness 配置只占位。 |
| `internal` | Octop hosts HTTP MCP at `/api/internal/mcp`; the harness loads it over HTTP. | Octop 在 `/api/internal/mcp` 托管 HTTP MCP，Harness 经 HTTP 加载。 |

## Catalog JSON / 目录 JSON

Each `connectors[]` object is a `ConnectorCatalogEntry`. User-facing strings are
either a plain string (used for both locales) or `{ "en": "…", "zh": "…" }`.

`connectors[]` 每一项对应一个 `ConnectorCatalogEntry`。用户可见字符串可以是普通字符串（中英共用），或 `{ "en": "…", "zh": "…" }`。

Required fields: `kind`, `name`, `description`, `auth_kind`, `doc_url`, `icon`,
`color`, `phase`, `mcp_mode`, `category`.

Optional: `quick_auth_url`, `login_url`, `guide_url`, `manual_url`, `auth_hint`,
`allowed_tools`, `oauth_issuer`, `mcp_url`, `oauth_resource`, `oauth_scopes`,
`mcp_user_agent`, `credential_fields`, `remote_transport` (default `raw_http`).

`credential_fields[]` items: `key`, `label`; optional `field_type` (`text` /
`password` / `url` / `tags`), `required`, `placeholder`, `help`, `secret`.

## Deep dives / 深入说明

- [Agent Mail CLI](connectors-agently-mail.md)
- [Qichacha / 企查查](connectors-qcc.md)
- [RAGFlow](connectors-ragflow.md)

## Synology NAS / 群晖 NAS

原生 DSM 套件内置 NAS MCP 与“群晖管家”专家。首次打开已登录的 Octop 页面，会为当前用户创建一个私有的“本机群晖 NAS”连接器，并将“群晖管家”加入该用户的专家列表；不会替换原有专家或当前选择。连接器只绑定到这个专家，不会为所有其他专家默认启用。

无需额外 NAS MCP 套件、MCP 令牌或 DSM 密码。每次工具调用都由 DSM 的 `authenticate.cgi` 重新验证当前用户会话，并按 DSM 账号权限请求本机 WebAPI。会话只保留在 NAS 内存中，不写入连接器数据库、专家文件或安装包；服务重启或 DSM 登录失效后，重新打开已登录的 Octop 页面即可恢复。默认写操作先预览，明确授权后才传 `execute=true`；连接器中的 `allow_writes=false` 可进一步限制为只读。

提供 10 个工具（状态、API 发现、描述、配方、操作、请求、批处理、上传、下载、文本读取），以及能力说明资源和只读巡检提示词。文件传输位于每个用户独立的 Octop 传输目录，不能访问其他用户的传输目录。连接器不能共享给其他账号；发现某 API 不代表其方法、参数、套件和权限已验证。

The native DSM package includes NAS MCP and a private Synology NAS expert for each user. It reuses the verified DSM session without a separate MCP service, token or password. Each tool call revalidates the DSM session. Business requests stay on NAS loopback, and the normal DSM permission and session checks remain enabled. Writes preview by default and require explicit `execute=true`; `allow_writes=false` restricts the connector to reads and previews. Session credentials stay in memory, and transfer files are isolated per user. Reopen the signed-in Octop page after a restart or DSM login expiry. API discovery is not method or device verification.

### Package Center operations / 套件管理

套件启停已有 `packages.start` / `packages.stop`。新增配方通过同一个 `nas_operate` 提供：套件目录 `packages.catalog`、安装目标卷 `packages.install_settings`、兼容性检查 `packages.feasibility`、依赖队列 `packages.queue`、安装 `packages.install`、升级 `packages.upgrade`、任务进度 `packages.install_status` 和下载检查点 `packages.download_status`。目录使用当前 NAS 注册的 API 版本，不写死只支持 v1。

安装和升级参数取自实际套件目录，保留每个字段要求的 JSON 编码。操作默认预览，写开关开启且对具体目标获得授权后执行；提交任务后需继续查进度，并通过 `packages.get` 核对最终版本。新安装默认不自动启动，用户要求运行时再调用启动配方。签名检查固定开启、不提供强制安装开关；当前 MCP 的宿主 Octop/NasMCP 不允许通过该连接停止或升级。

依赖、冲突、许可和安装向导需在提交前核对；超时后查询任务而不是盲目重提。自定义安装页、需要人工继续的签名/下载检查点、手动 SPK 上传和卸载不作为已自动化的流程。参见[官方套件中心安装流程](https://kb.synology.com/en-global/DSM/tutorial/How_to_install_applications_with_Package_Center)。本次操作仅有模拟协议与集成验证，尚未实机安装、停止或升级套件，已纳入 `0013` SPK，使用前需升级 NAS 上的套件。

Package operations reuse the same MCP tool. New recipes cover catalog and volume queries, compatibility/dependency checks, installation, upgrades and task/download status. They retain signature checks, default to preview and respect the connector write permission. A submitted task is not a completed installation; read task status and verify the final installed version. The expert must review dependencies, licenses and wizard requirements, and use native Package Center for interactive checkpoints. Self-stop/self-upgrade of the hosting Octop/NasMCP package is blocked. These additions are bundled starting with the `0013` SPK; upgrade the installed package to use them.

### Note Station writes / 笔记写入

通过 `nas_operate` 使用 `notes.create`、`notes.update`、`notes.trash` 和 `notes.restore`；`notes.recycled` 查询回收站。工具数量仍为 10 个。创建要求实际笔记本 `parent_id` 和标题，正文使用 HTML；编辑要求 `notes.get` 返回的 `object_id` 与原始字符串 `ver`，可修改标题、正文、摘要或 `tag_ids`。所有写入先预览；明确授权并开启连接器写开关后以 `execute=true` 执行。

创建按“创建 → 读取版本 → 保存正文 → 回读”执行。编辑发送 `check_conflict=true`，仅提交指定字段，不发送附件删除或替换指令，随后回读核对正文和原有附件。`verified=true` 才表示验证完成。创建的第二步失败会返回已创建的笔记 ID；`write_unconfirmed` 时先查询该 ID，不自动重试创建或保存。移入回收站和恢复只做提交前版本核对，不是服务端事务，不提供永久删除。

加密笔记写入、附件增删、移动和共享未纳入这些操作。以上流程以配套 my-nas 客户端的 Note Station v3 请求格式实现；模拟协议与应用集成测试不能替代实际 NAS 的读写验收。`0013` 安装包包含上述笔记写入代码，使用前需升级 NAS 上的套件。

Use the same `nas_operate` tool for `notes.create`, `notes.update`, `notes.trash` and `notes.restore`; `notes.recycled` lists recycled notes. Note writes preview by default, require connector write permission and explicit execution, and are verified by reading the note back. Creation saves the body after obtaining the new note ID and revision. Edits require the exact revision string, use server conflict checks and preserve unspecified fields and attachments. Unconfirmed results must be queried before retrying; a partially created note retains its ID. Encrypted-note writes, attachment mutations, moves, sharing and permanent deletion are not implemented by these recipes. These additions are bundled starting with the `0013` SPK; upgrade the installed package to use them.
