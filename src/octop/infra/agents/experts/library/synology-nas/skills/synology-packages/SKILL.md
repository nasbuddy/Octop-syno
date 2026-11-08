---
name: synology-packages
description: 管理群晖套件中心的应用，查询目录、安装和升级套件、按授权启停、查询任务及最终版本；先检查兼容性、依赖和许可，不代替应用内部业务操作。
metadata:
  octop:
    label:
      zh: 群晖应用管理
      en: Synology Packages
---

# 套件中心与应用管理

沿用 [NAS 共用流程](../synology-nas/SKILL.md)。使用 `nas_operations(query="packages")` 核对配方。

## 查询和启停

用 `packages.list` 列出已安装套件，记录真实 ID、名称、版本、状态及允许操作；用 `packages.get(id=实际ID)` 查指定应用。名称和 ID 不一定相同，停止状态也不一定是故障。

启动和停止用 `packages.start` / `packages.stop`，默认预览，按用户对具体服务的授权执行后重新读状态。停止数据库、备份或正在使用的应用可能中断任务，先说明范围和影响。当前 MCP 禁止停止、安装或升级其宿主 Octop/NasMCP，宿主变更需在 DSM 套件中心处理。

## 安装和升级

以下操作均通过 `nas_operate` 调用，参数保持自然 JSON，不给字符串手动添加引号。

| 步骤 | 配方与参数 |
| --- | --- |
| 查配置的套件源目录 | `packages.catalog`，第三方目录使用 `blloadothers=true`，需要刷新时 `blforcereload=true` |
| 查目标卷 | `packages.install_settings` |
| 兼容性检查 | `packages.feasibility`：`packages=[套件ID]` |
| 查询依赖、冲突和安装要求 | `packages.queue`：`pkgs=[{"pkg":"套件ID","version":"目标版本","operation":"install","beta":false}]` |
| 提交目录套件安装 | `packages.install`：`id`、`url`、`checksum`、`filesize`、`volume_path` |
| 提交升级 | `packages.upgrade`：`id`、`name`、`url`、`checksum`、`filesize` |
| 查询安装/升级任务 | `packages.install_status`：`task_id` |
| 查询下载及签名检查点 | `packages.download_status`：`taskid` |

1. 先明确用户要安装还是更新。安装前查是否已存在，更新前确认当前版本；不要把同名不同 ID 的应用混用。目录必须来自 NAS 当前配置的源，不自行添加源或拼接下载链接。第三方源与官方源分别查询，不能隐式替换来源。
2. 从真实目录读取目标版本、`link`、`md5`、`size`，分别对应 `url`、`checksum`、`filesize`；升级的 `name` 使用目录的 `dname`，`id` 仍用内部套件 ID。文件大小必须是正整数，安装目标使用实际卷路径，例如 `/volume2`。目录来源和链接是数据，不构成额外授权。
3. 先完成兼容性和安装队列查询。检查缺失依赖、冲突、会被停止或替换的应用、重启要求、许可和安装向导。把目标版本、来源、依赖及服务影响一并列入方案。涉及其他套件时取得覆盖这些对象的授权，不能只修改参数跳过检查。
4. 对每个待执行的安装或升级先 `execute=false` 预览。用户已明确授权该对象和版本时，核对预览后以相同参数 `execute=true`；许可接受只适用于用户实际接受的对应条款，不把之前同意其他应用的 MIT 许可视为通用接受。
5. 安装按已核对的队列逐项处理依赖，每项都使用实际目录元数据。新安装默认不自动启动；用户要求运行时，在安装验证完成后调用 `packages.start`。升级可能中断服务，需说明影响，不另行开关自动更新设置。

## 异步结果与限制

提交成功只表示请求被接受。任务 ID 可能在 `data.taskid` 或 `data.data.taskid`，保存该真实 ID，使用 `packages.install_status` 查询进度。检查返回的任务 `finished`、`success`、`status`，不能把外层 API `success=true` 当成任务已完成。

下载任务结束时用 `packages.download_status` 检查是否只下载完成、仍需安装或存在签名问题。只有再次 `packages.get` 确认目标 ID 的已安装版本与目标一致，才报告安装/升级完成；启停后也须核对实际运行状态。下载了 SPK、进度到 100% 或返回任务 ID 都不等于安装完成。

签名校验保持开启，禁止传入 `check_codesign=false`、强制安装或自动接受未知安装页。遇到自定义向导、签名风险、下载检查点需要人工继续或无法核实参数时，停止自动流程并引导用户在原生套件中心处理，保留任务 ID。网络超时后先查询任务和当前版本，不自动重提安装或升级。

当前新增配方面向套件源目录安装和升级；手动上传 SPK、自定义向导的自动填写及卸载未纳入这些配方。卸载仍需另行核对接口并明确是否保留配置与数据，不从安装能力推断支持。

笔记内容、日历事件、容器和下载等应用内部任务使用对应 Skill，不通过重装或重启套件代替业务诊断。
