"""Named DSM request recipes. Parameters remain JSON at this transport boundary.

Sources: Synology File/Download Station API guides, lib/api/*.dart and
lib/providers/virtual_machine/virtual_machine_service.dart. Recipes are not a
claim of successful execution on every DSM/package version.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Operation:
    api: str
    method: str
    summary: str
    version: int | None = 1
    read_only: bool = True
    defaults: dict = field(default_factory=dict)
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()


OPERATIONS: dict[str, Operation] = {}


def add(name, api, method, summary, *, version=1, write=False, defaults=None, required=(), optional=()):
    OPERATIONS[name] = Operation(api, method, summary, version, not write, defaults or {}, required, optional)


add("system.info", "SYNO.Core.System", "info", "系统信息", optional=("type",))
add("system.utilization", "SYNO.Core.System.Utilization", "get", "CPU、内存和网络利用率")
for method, title in [("reboot", "重启 NAS"), ("shutdown", "关闭 NAS")]:
    add("system." + method, "SYNO.Core.System", method, title, write=True, defaults={"force": False, "local": True})
add(
    "storage.volumes",
    "SYNO.Core.Storage.Volume",
    "list",
    "存储空间列表",
    defaults={"offset": 0, "limit": 100, "location": "internal"},
    optional=("option",),
)
add("storage.info", "SYNO.Storage.CGI.Storage", "load_info", "硬盘、存储池和卷的聚合信息")
add("storage.smart", "SYNO.Core.Storage.Disk", "get_smart_info", "硬盘 SMART 信息", required=("device",))
add("storage.smart_log", "SYNO.Core.Storage.Disk", "get_smart_test_log", "硬盘 SMART 检测记录", required=("device",))
add("network.interfaces", "SYNO.Core.Network.Interface", "list", "网络接口列表")
add("shares.list", "SYNO.Core.Share", "list", "共享文件夹列表", defaults={"shareType": "all", "additional": []})
add(
    "users.list",
    "SYNO.Core.User",
    "list",
    "本地用户列表",
    defaults={"offset": 0, "limit": 100},
    optional=("additional",),
)
add(
    "groups.list",
    "SYNO.Core.Group",
    "list",
    "本地群组列表",
    defaults={"offset": 0, "limit": 100},
    optional=("additional",),
)
add(
    "logs.recent",
    "SYNO.Core.SyslogClient.Status",
    "latestlog_get",
    "最近系统日志",
    defaults={"start": 0, "limit": 50, "widget": True, "dir": "desc"},
)
add("security.logins", "SYNO.SecurityAdvisor.LoginActivity", "list", "登录活动", defaults={"offset": 0, "limit": 100})

add("files.info", "SYNO.FileStation.Info", "get", "File Station 能力信息", version=2)
add(
    "files.shares",
    "SYNO.FileStation.List",
    "list_share",
    "可访问共享目录",
    version=2,
    defaults={"offset": 0, "limit": 100},
    optional=("additional", "sort_by", "sort_direction"),
)
add(
    "files.list",
    "SYNO.FileStation.List",
    "list",
    "列出目录",
    version=2,
    required=("folder_path",),
    defaults={"offset": 0, "limit": 100},
    optional=("additional", "sort_by", "sort_direction", "pattern", "filetype"),
)
add(
    "files.stat",
    "SYNO.FileStation.List",
    "getinfo",
    "文件详细信息",
    version=2,
    required=("path",),
    optional=("additional",),
)
add(
    "files.mkdir",
    "SYNO.FileStation.CreateFolder",
    "create",
    "创建目录",
    version=2,
    write=True,
    required=("folder_path", "name"),
    defaults={"force_parent": False},
)
add(
    "files.rename",
    "SYNO.FileStation.Rename",
    "rename",
    "重命名文件或目录",
    version=2,
    write=True,
    required=("path", "name"),
)
add(
    "files.copy_move",
    "SYNO.FileStation.CopyMove",
    "start",
    "复制或移动",
    version=3,
    write=True,
    required=("path", "dest_folder_path"),
    defaults={"remove_src": False, "overwrite": False},
    optional=("accurate_progress",),
)
add(
    "files.delete",
    "SYNO.FileStation.Delete",
    "start",
    "删除文件或目录（可能不可恢复）",
    version=2,
    write=True,
    required=("path",),
    defaults={"accurate_progress": True},
)
add(
    "files.search_start",
    "SYNO.FileStation.Search",
    "start",
    "启动异步文件搜索",
    version=2,
    write=True,
    required=("folder_path",),
    defaults={"recursive": True},
    optional=("pattern", "filetype", "size_from", "size_to", "mtime_from", "mtime_to"),
)
add(
    "files.search_list",
    "SYNO.FileStation.Search",
    "list",
    "读取搜索结果",
    version=2,
    required=("taskid",),
    defaults={"offset": 0, "limit": 100},
    optional=("additional", "sort_by", "sort_direction"),
)
add(
    "files.compress",
    "SYNO.FileStation.Compress",
    "start",
    "压缩文件",
    version=3,
    write=True,
    required=("path", "dest_file_path"),
    defaults={"format": "zip", "level": "normal", "mode": "add"},
    optional=("password",),
)
add(
    "files.extract",
    "SYNO.FileStation.Extract",
    "start",
    "解压文件",
    version=2,
    write=True,
    required=("file_path", "dest_folder_path"),
    defaults={"overwrite": False, "keep_dir": True},
    optional=("password",),
)
add(
    "files.dirsize_start",
    "SYNO.FileStation.DirSize",
    "start",
    "开始计算目录大小",
    version=2,
    write=True,
    required=("path",),
)
for suffix, api in [
    ("copy_move", "CopyMove"),
    ("delete", "Delete"),
    ("compress", "Compress"),
    ("extract", "Extract"),
    ("dirsize", "DirSize"),
]:
    add(f"files.{suffix}_status", "SYNO.FileStation." + api, "status", "查询任务状态", version=2, required=("taskid",))
    add(
        f"files.{suffix}_stop",
        "SYNO.FileStation." + api,
        "stop",
        "停止任务",
        version=2,
        write=True,
        required=("taskid",),
    )
add("files.search_stop", "SYNO.FileStation.Search", "stop", "停止搜索", version=2, write=True, required=("taskid",))
add(
    "files.search_clean",
    "SYNO.FileStation.Search",
    "clean",
    "清理搜索结果",
    version=2,
    write=True,
    required=("taskid",),
)
add(
    "files.share_list",
    "SYNO.FileStation.Sharing",
    "list",
    "文件分享链接",
    version=3,
    defaults={"offset": 0, "limit": 100},
)
add(
    "files.share_create",
    "SYNO.FileStation.Sharing",
    "create",
    "创建对外分享链接",
    version=3,
    write=True,
    required=("path",),
    optional=("password", "date_expired", "date_available"),
)
add("files.share_delete", "SYNO.FileStation.Sharing", "delete", "删除分享链接", version=3, write=True, required=("id",))
add("files.favorites", "SYNO.FileStation.Favorite", "list", "收藏目录", version=2, defaults={"offset": 0, "limit": 100})

add("downloads.info", "SYNO.DownloadStation.Info", "getinfo", "下载服务信息")
add(
    "downloads.list",
    "SYNO.DownloadStation.Task",
    "list",
    "下载任务列表",
    defaults={"offset": 0, "limit": 100, "additional": "detail,transfer"},
)
add(
    "downloads.get",
    "SYNO.DownloadStation.Task",
    "getinfo",
    "下载任务详情",
    required=("id",),
    defaults={"additional": "detail,transfer,file,tracker,peer"},
)
add("downloads.stats", "SYNO.DownloadStation.Statistic", "getinfo", "下载速度统计")
add(
    "downloads.create",
    "SYNO.DownloadStation.Task",
    "create",
    "创建 URL 或磁力下载任务",
    write=True,
    required=("uri",),
    optional=("destination", "username", "password", "unzip_password"),
)
for method, title in [("pause", "暂停下载"), ("resume", "恢复下载"), ("delete", "删除下载任务")]:
    add(
        "downloads." + method,
        "SYNO.DownloadStation.Task",
        method,
        title,
        write=True,
        required=("id",),
        optional=("force_complete",),
    )
add(
    "downloads.web_list",
    "SYNO.DownloadStation2.Task",
    "list",
    "DSM Web 下载任务列表",
    version=2,
    defaults={"offset": 0, "limit": 100, "additional": ["detail", "transfer"], "sort_by": "task_id", "order": "ASC"},
)
add("downloads.web_stats", "SYNO.DownloadStation2.Task.Statistic", "get", "DSM Web 下载统计")

add("containers.list", "SYNO.Docker.Container", "list", "容器列表", defaults={"offset": 0, "limit": 100, "type": "all"})
add("containers.get", "SYNO.Docker.Container", "get", "容器详情（敏感环境变量脱敏）", required=("name",))
add("containers.resources", "SYNO.Docker.Container.Resource", "get", "容器资源使用")
add("containers.processes", "SYNO.Docker.Container", "get_process", "容器进程", required=("name",))
add("containers.stats", "SYNO.Docker.Container", "stats", "容器统计")
add(
    "containers.logs",
    "SYNO.Docker.Container.Log",
    "get",
    "容器日志",
    required=("name",),
    defaults={"offset": 0, "limit": 100, "from": "", "to": "", "level": "", "keyword": "", "sort_dir": "DESC"},
)
add("containers.log_dates", "SYNO.Docker.Container.Log", "get_date_list", "容器日志日期", required=("name",))
for method, title in [("start", "启动容器"), ("stop", "停止容器"), ("restart", "重启容器"), ("delete", "删除容器")]:
    add("containers." + method, "SYNO.Docker.Container", method, title, write=True, required=("name",))
add("containers.images", "SYNO.Docker.Image", "list", "容器映像列表", defaults={"offset": 0, "limit": 100})
add("containers.projects", "SYNO.Docker.Project", "list", "Compose 项目列表")
add("containers.networks", "SYNO.Docker.Network", "list", "容器网络列表")
add("containers.registries", "SYNO.Docker.Registry", "get", "镜像仓库列表", defaults={"offset": 0, "limit": -1})

add(
    "packages.list",
    "SYNO.Core.Package",
    "list",
    "已安装套件",
    version=2,
    defaults={"additional": ["status", "available_operation"]},
)
add(
    "packages.get",
    "SYNO.Core.Package",
    "get",
    "套件详情",
    required=("id",),
    defaults={"additional": ["status", "dsm_apps"]},
)
for method, title in [("start", "启动套件"), ("stop", "停止套件")]:
    add(
        "packages." + method,
        "SYNO.Core.Package.Control",
        method,
        title,
        write=True,
        required=("id",),
        optional=("dsm_apps",),
    )
add(
    "packages.catalog", "SYNO.Core.Package.Server", "list", "synology.packages.catalog",
    version=None, defaults={"updateSprite": True, "blforcereload": False, "blloadothers": False},
)
add("packages.install_settings", "SYNO.Core.Package.Installation", "get", "synology.packages.install_settings")
add(
    "packages.feasibility", "SYNO.Core.Package", "feasibility_check", "synology.packages.feasibility",
    required=("packages",), defaults={"type": "install_check"},
)
add(
    "packages.queue", "SYNO.Core.Package.Installation", "get_queue", "synology.packages.queue",
    required=("pkgs",),
)
add(
    "packages.install", "SYNO.Core.Package.Installation", "install", "synology.packages.install",
    write=True, required=("id", "url", "checksum", "filesize", "volume_path"),
)
add(
    "packages.upgrade", "SYNO.Core.Package.Installation", "upgrade", "synology.packages.upgrade",
    write=True, required=("id", "name", "url", "checksum", "filesize"),
)
add(
    "packages.install_status", "SYNO.Core.Package.Installation", "status", "synology.packages.install_status",
    required=("task_id",),
)
add(
    "packages.download_status", "SYNO.Core.Package.Installation.Download", "check", "synology.packages.download_status",
    required=("taskid",),
)
add(
    "tasks.list",
    "SYNO.Core.TaskScheduler",
    "list",
    "计划任务列表",
    version=2,
    defaults={"offset": 0, "limit": 100, "sort_by": "next_trigger_time", "sort_direction": "ASC"},
)
add(
    "tasks.run",
    "SYNO.Core.TaskScheduler",
    "run",
    "执行指定计划任务（可能执行 root 脚本）",
    write=True,
    required=("task",),
)
add("tasks.get", "SYNO.Core.TaskScheduler", "get", "计划任务详情", version=2, required=("id",))

for method, title in [
    ("get", "集群信息"),
    ("get_host", "集群主机"),
    ("get_guest", "集群虚拟机"),
    ("get_repo", "虚拟机存储库"),
]:
    add("vmm." + method, "SYNO.Virtualization.Cluster", method, title)
add("vmm.hosts", "SYNO.Virtualization.Host", "list", "虚拟机主机列表", version=2)
add("vmm.host", "SYNO.Virtualization.Host", "get", "虚拟机主机详情", version=2, required=("host_id",))
add("vmm.images", "SYNO.Virtualization.Guest.Image", "list", "虚拟机磁盘映像", version=2)
add("vmm.repositories", "SYNO.Virtualization.Repo", "list", "虚拟机映像存储库", version=2)
add(
    "vmm.logs",
    "SYNO.Virtualization.Log",
    "list",
    "虚拟机日志",
    defaults={
        "action": "load",
        "datefrom": 0,
        "dateto": 0,
        "filter_content": "",
        "limit": 100,
        "loglevel": "",
        "offset": 0,
        "sort_by": "time",
        "sort_dir": "DESC",
    },
)
add(
    "vmm.power",
    "SYNO.Virtualization.Guest.Action",
    "pwr_ctl",
    "虚拟机电源操作",
    write=True,
    required=("guest_id", "action"),
)

add(
    "notes.notebooks",
    "SYNO.NoteStation.Notebook",
    "list",
    "笔记本列表",
    version=2,
    defaults={"filter": {"archive": False}},
)
add(
    "notes.list",
    "SYNO.NoteStation.Note",
    "list",
    "笔记列表",
    version=3,
    defaults={"offset": 0, "limit": 100, "filter": {"recycle": False, "archive": False}},
    optional=("field",),
)
add("notes.tags", "SYNO.NoteStation.Tag", "list", "笔记标签")
add("notes.todos", "SYNO.NoteStation.Todo", "list", "笔记待办", version=2, defaults={"filter": {"parent_id": "*"}})
add("notes.get", "SYNO.NoteStation.Note", "get", "笔记详情", version=3, required=("object_id",))
add(
    "notes.recycled", "SYNO.NoteStation.Note", "list", "synology.notes.recycled_list",
    version=3, defaults={"offset": 0, "limit": 100, "filter": {"recycle": True, "archive": False}},
    optional=("field",),
)
add(
    "notes.create", "SYNO.NoteStation.Note", "create", "synology.notes.create",
    version=3, write=True, required=("parent_id", "title"), optional=("content", "brief"),
)
add(
    "notes.update", "SYNO.NoteStation.Note", "set", "synology.notes.update",
    version=3, write=True, required=("object_id", "ver"), optional=("title", "content", "brief", "tag_ids"),
)
add(
    "notes.trash", "SYNO.NoteStation.Note", "delete", "synology.notes.trash",
    version=3, write=True, required=("object_id", "ver"),
)
add(
    "notes.restore", "SYNO.NoteStation.Note", "restore", "synology.notes.restore",
    version=3, write=True, required=("object_id", "ver"),
)
add(
    "audio.search",
    "SYNO.AudioStation.Search",
    "list",
    "音乐搜索",
    required=("keyword",),
    defaults={
        "library": "all",
        "offset": 0,
        "limit": 100,
        "additional": "song_tag,song_audio,song_rating",
        "sort_by": "title",
        "sort_direction": "ASC",
    },
)
add(
    "audio.playlists",
    "SYNO.AudioStation.Playlist",
    "list",
    "音乐播放列表",
    version=2,
    defaults={"library": "all", "offset": 0, "limit": 100, "additional": "sharing_info"},
)
add(
    "audio.playlist",
    "SYNO.AudioStation.Playlist",
    "getinfo",
    "播放列表歌曲",
    version=2,
    required=("id",),
    defaults={
        "library": "all",
        "offset": 0,
        "limit": 100,
        "additional": "songs_song_tag,songs_song_audio,songs_song_rating",
    },
)
add(
    "audio.rate",
    "SYNO.AudioStation.Song",
    "setrating",
    "设置歌曲评分",
    version=3,
    write=True,
    required=("id", "rating"),
)
for prefix, namespace in [("photos", "Foto"), ("photos_shared", "FotoTeam")]:
    add(
        prefix + ".list",
        "SYNO." + namespace + ".Browse.Item",
        "list",
        "个人/共享空间照片列表",
        defaults={"offset": 0, "limit": 100, "additional": ["thumbnail", "resolution", "orientation", "video_meta"]},
        optional=("start_time", "end_time", "type", "folder_id"),
    )

# The full discovered catalog remains accessible through nas_request; recipes
# deliberately avoid guessing undocumented actions or encrypted payloads.
