---
name: synology-containers
description: 查询和管理群晖 Container Manager 或 Docker 的容器、映像、项目、资源和日志，按授权启停容器；不用于 Virtual Machine Manager 虚拟机。
metadata:
  octop:
    label:
      zh: 群晖容器管理
      en: Synology Containers
---

# Container Manager / Docker

沿用 [NAS 共用流程](../synology-nas/SKILL.md)。先用 `nas_operations(query="containers")` 和 API 发现确认当前版本；显示名称是 Container Manager 不代表可擅自改写 `SYNO.Docker.*` 命名空间。

用 `containers.list`、`containers.get` 确定实际容器名，按问题选择资源、进程和日志配方。项目、映像、网络和仓库分别查询，不把 Compose 项目名当作容器名。日志只取相关时间和必要行数，输出中隐藏令牌、连接串和敏感环境变量。

启停与重启先预览，说明关联服务和挂载数据的影响；不把重启当成默认诊断。不要中断承载当前 Octop/MCP 的容器。变更后重新读取运行状态，必要时核对日志，不能把运行状态等同于应用健康。

创建、更新映像、修改挂载、重建项目、容器终端和删除并非现有配方都支持。须核实当前接口、请求参数和数据保留方式；没有可靠方法就报告限制，不转用 Shell 执行 Docker 命令，不自动清理卷或挂载目录。
