---
name: synology-audio
description: 查询群晖 Audio Station 音乐、播放列表和歌曲信息，按授权设置歌曲评分；不用于 Jellyfin 等独立媒体服务。
metadata:
  octop:
    label:
      zh: 群晖音乐
      en: Synology Audio
---

# Audio Station

沿用 [NAS 共用流程](../synology-nas/SKILL.md)。先用 `nas_operations(query="audio")` 检查 Audio Station 的真实 API、版本和权限，未安装时不能从 NAS 有音乐文件推断存在音乐服务。

搜索用 `audio.search(keyword=用户关键词)`，播放列表用 `audio.playlists`、`audio.playlist(id=实际ID)`，按用户请求分页和筛选。歌曲 ID、播放列表 ID 与文件路径不能互换；同名歌曲需按实际歌手、专辑等返回字段区分。

评分用 `audio.rate`，核对当前版本允许的评分值，预览选中歌曲与新值，按授权执行后重新查询。播放控制、创建或修改播放列表、转码与媒体下载没有专用配方时先核对当前 API，不能把列出歌曲说成已经播放或发送音频。

NAS 上的 Jellyfin、Plex 等独立服务不等于 Audio Station，使用其对应连接器；不要用文件删除或改名替代音乐库整理。
