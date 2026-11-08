---
name: synology-downloads
description: 查询和管理群晖 Download Station 下载任务，包括状态、速度、创建、暂停、恢复和删除；独立的 Aria2、qBittorrent 等服务不走此技能的 DSM 配方。
metadata:
  octop:
    label:
      zh: 群晖下载管理
      en: Synology Downloads
---

# Download Station 下载管理

沿用 [NAS 共用流程](../synology-nas/SKILL.md)。先搜索 `nas_operations(query="downloads")`，用 `downloads.info`、`downloads.list`、`downloads.get` 和 `downloads.stats` 查服务和指定任务。不同 Download Station API 的任务 ID 和参数不能混用。

创建前核对用户提供的 URL、磁力链接或种子文件、目标共享目录及重名任务；只在指定目录创建。`downloads.create` 和其他修改配方先预览，再按授权执行。私有下载链接可能含令牌，汇报时隐藏其敏感部分。

暂停、恢复、重试和删除前列出实际任务 ID 及当前状态。删除任务与删除已下载文件是不同后果，不能从“移除任务”推断同意删除文件。批量操作只覆盖用户选定范围，不自动重试失败任务。

创建后查新任务 ID，区分排队、下载中、完成和失败；“创建成功”不能报告为“下载完成”。网络超时先查已有任务，避免重复添加。用户使用独立 Aria2 或 qBittorrent 时说明需要对应连接器，不用 Download Station API 冒充支持。
