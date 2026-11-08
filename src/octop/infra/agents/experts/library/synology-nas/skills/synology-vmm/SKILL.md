---
name: synology-vmm
description: 查询群晖 Virtual Machine Manager 的集群、主机、虚拟机、存储库和日志，按授权处理虚拟机电源操作；不用于 Docker 容器。
metadata:
  octop:
    label:
      zh: 群晖虚拟机
      en: Synology Virtual Machines
---

# Virtual Machine Manager

沿用 [NAS 共用流程](../synology-nas/SKILL.md)。先搜索 `nas_operations(query="vmm")`，确认 VMM 已安装、相关 API 已注册且当前账号可访问。

用 `vmm.get`、`vmm.get_guest`、`vmm.hosts`、`vmm.host`、`vmm.repositories`、`vmm.images` 或 `vmm.logs` 查询本次问题需要的对象。虚拟机 `guest_id`、主机 `host_id`、映像和存储库是不同标识，从真实返回中选择，不能只按显示名推断 ID。

电源操作用 `vmm.power`，其 `action` 必须从对应版本的可信资料核对，不能猜枚举。预览应说明目标虚拟机、当前电源状态、操作以及是否可能丢失未保存数据；明确区分正常关机、强制断电、重启和删除虚拟机，不把它们互相替代。

仅执行用户授权的具体动作，再读回状态。迁移、磁盘扩容、快照恢复、导入和删除不能从电源配方推断支持；没有已验证接口与参数时先给方案，不触及虚拟磁盘或宿主机存储池。
