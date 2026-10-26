# Octop-syno 收录申请资料

准备日期：2026-10-26。本文件整理公开源码地址和申请材料；尚未向 SynoCommunity 提交 Issue 或 PR，也未发布 SPK Release。

## 使用方式

- 目标仓库：[SynoCommunity/spksrc](https://github.com/SynoCommunity/spksrc)。
- 申请标题：`[Package Request] Octop-syno`。
- 英文正文：[synocommunity-request.md](synocommunity-request.md)。复制时将第一行作为标题，其余内容作为正文。
- 申请类型：初步 Package Request，后续还需提交 `spksrc` 打包实现。

英文稿包含 Name、Description、Website、Software documentation、Build/Installation documentation、Source code、License 七项，并说明 DSM 登录、运行权限和验证边界。依据：[官方申请要求](https://github.com/SynoCommunity/spksrc/blob/master/CONTRIBUTING.md#package-requests)。

## 源码和文档

| 项目               | 地址或说明                                                                                                       |
| ------------------ | ---------------------------------------------------------------------------------------------------------------- |
| 申请名称           | `Octop-syno`；现有 SPK 内部标识仍为 `Octop`                                                                      |
| 群晖适配源码       | [hhuee/Octop-syno 的 codex/synology-native 分支](https://github.com/hhuee/Octop-syno/tree/codex/synology-native) |
| 群晖构建／安装说明 | [synology/README.md](https://github.com/hhuee/Octop-syno/blob/codex/synology-native/synology/README.md)          |
| 构建脚本           | [synology/build-spk.sh](https://github.com/hhuee/Octop-syno/blob/codex/synology-native/synology/build-spk.sh)    |
| 上游项目           | [TencentCloud/Octop](https://github.com/TencentCloud/Octop)                                                      |
| 上游使用文档       | [README](https://github.com/TencentCloud/Octop/blob/main/README.md)                                              |
| 上游开发文档       | [CONTRIBUTING.md](https://github.com/TencentCloud/Octop/blob/main/CONTRIBUTING.md)                               |
| 上游许可证         | [MIT](https://github.com/TencentCloud/Octop/blob/main/LICENSE)；运行时和依赖保留各自许可证                       |

本分支基于上游提交 `4632d0f4` 整理群晖原生支持、DSM 认证、子路径和图片修复，打包修订号为 `0005`。原工作区的聊天历史发送关联改动不在本分支中；该部分的 `0006` 修订说明也未带入。没有因此重命名现有 NAS 套件或改动其数据路径。

2026-10-26，GitHub 搜索 API 查询 `repo:SynoCommunity/spksrc Octop in:title,body` 返回 0 条，`incomplete_results=false`。这次检索覆盖 Issue 和 PR，提交当天应复查。

## 已有本地产物记录

| 项目         | 结果                                                                                     |
| ------------ | ---------------------------------------------------------------------------------------- |
| 文件名       | `Octop-synology-geminilake-1.0.2-0005.spk`                                               |
| 包内元数据   | `package="Octop"`、`version="1.0.2-0005"`、`arch="geminilake"`、`os_min_ver="7.2-64570"` |
| 文件大小     | 237619200 字节                                                                           |
| SHA-256      | `65b262ab1a3dbef162cc44ee6ba380bc988dcf300f519309500e8f95a305ce53`                       |
| 校验记录     | 2026-10-26 重新计算哈希并与 `.sha256` 比对，结果为 `OK`，同时读取了 SPK 内部 `INFO`      |
| 公共下载地址 | 尚未发布；此仓库提交源码，不将已有 SPK 放入 Git                                          |

这些是先前本地产物的记录，不代表该二进制由当前公开提交重新构建。后续发布测试包时，应从明确的提交重新构建，再填写下载链接、源码提交和新计算的 SHA-256。

## 兼容范围与实机验证

| 事项            | 当前结论                                                                                                               |
| --------------- | ---------------------------------------------------------------------------------------------------------------------- |
| 首期目标        | DS220+ / `geminilake`；NAS 运行时无需 Docker 或 Container Manager                                                      |
| 最低版本字段    | DSM `7.2-64570`，不等于所有 DSM 7.2 版本均通过测试                                                                     |
| 已有实机记录    | 群晖 README 的 2026-10-21 记录：`1.0.2-0004` 在 DSM `7.2.1-69057 Update 12` 上安装／升级、DSM 管理员登录和数据保留通过 |
| `0005` 实机状态 | 先前安装流程未取得完成证据；准备申请资料时没有重新连接 NAS 复测                                                        |
| 其他 DSM／架构  | 未完成验证；不宣称支持全部 DSM、其他 x86-64 平台或 ARM                                                                 |
| 待验收功能      | 普通用户登录、DSM 退出／过期／切换账号、管理员降权、长连接失效、NAS 重启，以及最终投稿包的新装与升级                   |

## 正式收录前剩余工作

- 将 Python、依赖、前端、DSM 路由和生命周期接入 `spksrc`。
- 确定最终内部包标识；若改动现有 `Octop` 标识，需验证安装和数据迁移。
- 完成声明支持架构的 `all-supported` 构建、新安装和升级测试，确认升级保留用户配置。
- 整理运行时和依赖的许可证通知，并补齐实机验证记录。
- 确定后续打包维护人员和更新计划；申请稿没有代替任何人承诺长期维护。

构建、新装和升级测试要求依据：[SynoCommunity PR 指南](https://github.com/SynoCommunity/spksrc/blob/master/CONTRIBUTING.md#pull-requests)。正式包需经审核、合并和仓库激活后发布：[发布流程](https://docs.synocommunity.com/developer-guide/publishing/)。
