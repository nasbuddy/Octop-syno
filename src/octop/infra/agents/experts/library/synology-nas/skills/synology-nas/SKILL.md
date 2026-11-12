---
name: synology-nas
description: 群晖 NAS 共用连接检查、授权与结果验证流程，以及 DSM 系统、存储和网络巡检；具体应用转到对应的 synology 应用技能。
---

# 群晖 NAS 操作流程

本技能复用连接器提供的 NAS MCP 工具，不内置 NAS 地址或凭据，也不赋予额外权限。使用实际注入的工具名称（可能带连接器前缀）。

## 1. 连接检查

调用 `nas_status`。只有 `authenticated=true` 才继续业务查询。`configured`、`session_present` 或 API 发现成功不能证明登录成功。输出中隐藏凭据；登录失效时停止并引导用户重新登录 DSM 并回到 Octop。

原生 DSM 套件首次登录会自动创建“群辉NAS”私有连接器并绑定到这个专家，无需单独安装 NAS MCP 或获取 MCP 令牌。没有工具时先检查该连接器是否停用、是否在当前专家中选用，以及 DSM 登录是否有效。不要搜索本机或其他用户的凭据。会话只在内存中保存；服务重启后需重新打开已登录的 Octop 页面。

## 2. 选择应用技能

根据请求只读取相关的应用技能；它们共用本文的连接、授权和验证流程，不是独立账号或连接器。

| 应用 | Skill |
| --- | --- |
| Note Station 笔记、笔记本、笔记待办 | [synology-notes](../synology-notes/SKILL.md) |
| Synology Calendar 日历、事件、日历待办 | [synology-calendar](../synology-calendar/SKILL.md) |
| 套件中心、应用运行状态与启停 | [synology-packages](../synology-packages/SKILL.md) |
| File Station 文件管理 | [synology-files](../synology-files/SKILL.md) |
| Download Station 下载任务 | [synology-downloads](../synology-downloads/SKILL.md) |
| Container Manager / Docker | [synology-containers](../synology-containers/SKILL.md) |
| Virtual Machine Manager 虚拟机 | [synology-vmm](../synology-vmm/SKILL.md) |
| Synology Photos 个人与共享照片 | [synology-photos](../synology-photos/SKILL.md) |
| Audio Station 音乐与播放列表 | [synology-audio](../synology-audio/SKILL.md) |

系统、存储和网络巡检继续使用本技能。未列出的应用先发现真实能力，不宣称已有专属技能。

## 3. 查找配方

根据目标调用 `nas_operations(query=关键词)`，读取实际配方名、必填参数、默认值、读写属性和当前 NAS 的版本可用性。以下名称仅作检索起点，必须以实时目录为准：

| 需求 | 检索关键词 / 常见配方 |
| --- | --- |
| 系统巡检 | `system` / `system.info`、`system.utilization` |
| 存储与硬盘 | `storage` / `storage.volumes`、`storage.info`、`storage.smart` |
| 文件与共享目录 | `files` / `files.shares`、`files.list`、`files.stat` |
| 下载管理 | `downloads` |
| 套件管理 | `packages` |
| 网络接口 | `network` / `network.interfaces` |
| 容器、虚拟机、备份、音乐及其他应用 | 搜索业务关键词，结合 `nas_apis` 查当前已安装应用的能力 |

读取指定文本使用 `nas_read_text`；传输文件使用 `nas_upload` / `nas_download`，先核对路径、大小与覆盖选项。服务端 `local_file` 指 MCP 服务所在机器的路径，不一定是用户电脑，也不一定是 Octop 工作区。

## 4. 查询与变更

- 已知只读配方：`nas_operate(name=目录返回的名称, params=经过核对的参数)`。
- 已知写入配方：先 `nas_operate(..., execute=false)` 获取预览，展示目标和影响；取得具体授权且写开关开启后，使用相同参数和 `execute=true`。
- 无配方时：通过 `nas_apis`、`nas_describe` 和该 DSM/套件版本的可靠文档确认，再使用 `nas_request`。未知方法视为写入；发现 API 不能代替参数验证。查不到可信写入参数就停止该项，不猜测。
- `nas_request` 和 `nas_batch` 即使请求内容是查询，也默认只预览，实际调用必须显式 `execute=true` 且写开关开启；不能把预览当成业务结果。优先使用已知只读配方，写开关关闭时报告此通道的限制，不自行开启。
- `nas_batch` 适用于用户请求范围内的多项查询；写操作逐项核对，不能用批处理扩大授权范围。
- 配方不存在、权限不足、应用未安装或写开关关闭时，报告真实原因；不改用其他通道绕过限制。

## 5. 核对结果

变更后重新读取目标，异步任务查询状态至完成或明确失败。只报告本次工具返回的数据。健康检查中不要运行 SMART 检测、删除文件、重启设备、创建下载或定时任务来证明连接成功。
