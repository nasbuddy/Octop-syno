---
name: synology-photos
description: 查询和整理群晖 Synology Photos 的个人或共享空间照片资料；用于照片浏览、时间范围筛选和整理方案，不把照片原文件目录当作相册 API。
metadata:
  octop:
    label:
      zh: 群晖照片
      en: Synology Photos
---

# Synology Photos

沿用 [NAS 共用流程](../synology-nas/SKILL.md)。先搜索 `nas_operations(query="photos")`，确认 Photos 及账号权限。个人空间使用 `photos.list` / `SYNO.Foto.*`，共享空间使用 `photos_shared.list` / `SYNO.FotoTeam.*`；先确定用户要操作哪个空间，不能用另一空间权限代替。

按用户要求限制时间、类型或目录并分页，返回照片 ID、名称及实际时间信息。列表元数据或缩略图不能支持“已经看过原图内容”的说法；无法读取图像时明确依据仅是元数据，不凭文件名推断人物或场景。

目前专用配方提供照片列表。相册、人物、标签、分享、上传和删除须另查当前版本的真实 API 与参数。文件 API 移动原图不等于编辑 Photos 相册，可能影响索引或引用，不能混用。

整理先给目标空间和具体对象的方案；删除、移动原图或对外分享要确认范围与影响。不要自动合并所谓重复照片、开放共享空间或创建公开链接；完成后在对应空间重新查询验证。
