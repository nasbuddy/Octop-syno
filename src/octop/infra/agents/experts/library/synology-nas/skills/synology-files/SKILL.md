---
name: synology-files
description: 通过群晖 File Station 列目录、查找和读取文件、上传下载、复制移动、改名及整理；用于 NAS 文件操作，不把服务端路径当成用户电脑路径。
metadata:
  octop:
    label:
      zh: 群晖文件管理
      en: Synology Files
---

# File Station 文件管理

沿用 [NAS 共用流程](../synology-nas/SKILL.md)。先用 `nas_operations(query="files")` 核对配方，用 `files.shares`、`files.list`、`files.stat` 确定可访问共享目录、目标路径和文件属性。

- NAS 路径使用 File Station 返回的 `/共享名/目录`；不能把 `/volume1/...`、用户电脑路径或 Octop 工作区路径直接替换进去。查询按目录和分页收窄；不要无故遍历全部私人文件。
- 小型文本用 `nas_read_text`；二进制文件用 `nas_download`，保存到当前用户的隔离传输目录，不覆盖已有文件。`nas_upload` 的源文件也必须在服务端允许的传输目录内；下载到服务端不等于已发送给用户电脑。
- 整理前列出具体源、目标、重名和覆盖风险。`files.mkdir`、`files.rename`、`files.copy_move` 等先预览；复制默认保留源、默认不覆盖，不把“整理”解释为删除重复文件。
- 搜索、目录大小计算、复制移动、删除和压缩解压可能返回异步任务 ID。使用相应配方查询状态，保留任务 ID；已接受不代表完成。发起搜索和大小计算在当前配方中也受写开关保护。
- 删除、覆盖、外部分享和批量修改需确认实际范围。分享链接要核对权限及有效期；不要无意公开文件。变更后读回目录或文件属性验证结果。
