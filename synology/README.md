# Octop-syno — 群晖原生 SPK

源码：[hhuee/Octop-syno 的 codex/synology-native 分支](https://github.com/hhuee/Octop-syno/tree/codex/synology-native)。`Octop-syno` 是发行名称，现有 SPK 内部标识仍为 `Octop`，数据路径保持一致。

面向 **DS220+ / DSM 7.2 系列（含 7.2.1、7.2.2）** 的原生套件，自带 CPython 3.12、锁定的 Python 依赖和 Web 控制台。NAS 运行时不需要 Docker、Container Manager 或另装 Python。

`0004` 修订接入 DSM 当前登录会话。从 DSM 主菜单或套件中心打开 Octop，使用同一 DSM 地址下的 `/octop/`，例如 `http://NAS_IP:5000/octop/` 或 `https://NAS_IP:5001/octop/`。DSM 自定义端口同样沿用当前端口。后台仅监听 `127.0.0.1:8089`，无需开放该端口。

`0005` 修订修复共享空状态图片的 `/octop/` 路径，覆盖定时任务、知识库等使用该图片的页面。

## 兼容范围与验证边界

| DSM / 硬件 | 当前构建目标 |
|------------|--------------|
| DS220+ / DSM 7.2.1-69057 Update 12 | 已实机验证安装、原生管理员登录及升级后数据保留 |
| 其他 DSM 7.2（64570 起）、7.2.1、7.2.2 + geminilake | 目标范围；仍须逐版本实机验收 |
| DSM 7.3 及后续版本 + geminilake | 无安装上限，但未验证，不保证兼容 |
| DSM 7.0 / 7.1、DSM 6.x | 不支持，需要单独适配运行时与套件生命周期 |
| 其他 x86_64 平台、ARM 平台 | 当前包不声明支持，需要分别构建和验证 |

目标架构为 `geminilake`（DS220+ 使用 Intel Celeron J4025）。DSM 版本与 CPU 架构是两个独立条件，这不是全机型通用 SPK。模型调用仍需配置 LLM 服务；浏览器自动化、宿主桌面控制、Android、Docker 沙箱等可选能力未作为 DSM 原生组件适配。

实机记录（2026-10-21）：DS220+ / DSM 7.2.1-69057 Update 12 已升级至 `1.0.2-0004`。从当前 DSM 会话打开及刷新 `/octop/` 均可直接进入 Octop，用户管理页面可访问，DSM 管理员已同步为 Octop 管理员。同名旧账号及其 1 个专家独立保留，未自动合并；健康接口确认数据库正常、加载 2 个用户及 1 个运行中的 Agent。匿名业务请求返回 `401`，外部内部 MCP 路径返回 `404`，外部 `8089` 已关闭。

普通用户首次登录、DSM 退出/过期/切换账号、管理员降权、长连接失效与 NAS 重启尚未进行实机验收；自动化测试不能替代这些场景或其他 DSM 版本的实机验证。

## 登录与权限

- 完全复用浏览器当前 DSM 会话，不要求输入 Octop 密码或部署 SSO Server。
- 全新安装先由 DSM 管理员打开，自动初始化默认 SQLite 数据库并创建对应账号；已有数据库配置继续沿用。
- DSM `administrators` 组成员同步为 Octop 管理员；离开该组后撤销此身份的管理员角色。其他 DSM 用户按普通用户创建。
- 通过本机 DSM 认证程序取得真实用户名，再查询系统 UID 和组成员。DSM 身份按 UID 与用户名绑定；**不会自动合并已有 Octop 同名账号**，冲突时生成独立用户名。删除并重建相同 UID、相同用户名的 NAS 账号前，管理员需先处理旧 Octop 身份和数据。
- Octop 停用的账号仍不能登录。DSM 用户没有各自独立的系统进程；Agent 工具统一以套件内部用户执行，授权普通用户前应确认其 Octop 工具权限。
- 每次浏览器业务请求校验 DSM 会话；页面、流式响应和 WebSocket 每 5 秒复查（后台标签页计时可能被浏览器延后）。认证程序调用最长等待 5 秒；失效后拒绝新请求并关闭长连接。已完成的操作不会回滚，后台 Agent 和定时任务继续运行。
- 浏览器切换 DSM 账号后，旧页面的令牌不能对新账号执行请求；需重新打开 Octop。菜单“返回 DSM”只返回 DSM，不会登出其他 DSM 应用。
- 原生模式不支持脱离 DSM Cookie 的密码/API 令牌客户端访问。普通 Python、Docker 部署的登录行为保持原样。
- 连接器 OAuth 回调校验一次性 state 与当前 DSM 对应的 Octop 账号；临时下载链接也要求相同账号的有效 DSM 会话。内部 MCP 保留每个连接器自己的凭据，供后台 Agent 从本机调用，DSM 外部入口不开放该路径。

DSM 会话只交给本机 `/usr/syno/synoman/webman/modules/authenticate.cgi` 校验，不保存 DSM 密码或 Cookie。首次打开时通过同源 `/webman/login.cgi` 获取 SynoToken，并仅通过请求头交给 Octop；验证通过后只在服务进程内存保留最多 256 个会话的校验令牌，按会话与客户端 IP 隔离，校验失败立即移除。令牌不会写入数据库、日志、URL 或浏览器存储，也不替代每次请求的 DSM 会话验证。内部 Octop 令牌绑定当前 DSM 会话，仅放在标签页的 sessionStorage；不能代替有效 DSM 会话。请使用可信的 DSM HTTPS 地址。

## 构建

开发电脑需有 Node.js、uv 和正在运行的 Docker：

```bash
bash synology/build-spk.sh
```

脚本构建专用 `/octop/` 前端，再用 `linux/amd64` Debian Bookworm 容器生成 Linux 依赖，复用 `desktop/portable/bootstrap-runtime.sh` 的便携 Python。Docker 仅用于开发电脑构建。Bookworm glibc 2.36 对应 DSM 7.2 的 geminilake 工具链，依赖按 `uv.lock` 安装。

产物位于 `dist/Octop-synology-geminilake-<version>-0005.spk`，附 `.sha256` 文件。构建会以低权限 Linux 用户检查打包后的页面、匿名/伪造会话拒绝、服务启停、重复启动、失效 PID 和重启后数据保留。Linux 检查不模拟成功的 DSM 登录，不能替代 NAS 验收。

## 安装与升级

1. 升级前停止套件并备份整个 `/var/packages/Octop/var/`。从旧版独立账号登录切换时，DSM 身份会新建账号，旧账号数据保留但不会自动迁移所有权。
2. 在 DSM **套件中心 → 手动安装**选择 SPK。这是未签名的第三方包，并非群晖官方套件。
3. 套件的 `web-config` worker 安装 `/octop/` 路由；套件启停/安装会触发 DSM Nginx 服务重载。后台仍以 Octop 系统内部用户运行，不授予 root 或免密 sudo。
4. 使用 DSM 管理员登录 DSM，再从主菜单打开 Octop，配置模型服务。原生模式不再生成 `octop-login.txt`，旧版残留文件不作为登录依据。
5. 不要再使用 `NAS_IP:8089` 或单独域名反向代理；必须使用当前 DSM 会话所属的同源入口。跨域名或额外反向代理需要另行验证 Cookie、来源与客户端 IP。

## 数据与运维

| 内容 | 路径 |
|------|------|
| 程序与 Python | `/var/packages/Octop/target/` |
| 数据库、工作区、密钥、配置 | `/var/packages/Octop/var/.octop/` |
| 启动日志 | `/var/packages/Octop/var/octop-service.log` |

需要访问共享文件夹时，在 DSM 中向 **Octop 系统内部用户**授予所需权限。Agent 工作区路径限制不是操作系统沙箱。套件更新使用 SPK，不使用网页或 CLI 的 `octop update`。

在 NAS 本机可检查：

```bash
curl --fail http://127.0.0.1:8089/api/health
sudo tail -n 100 /var/packages/Octop/var/octop-service.log
```

启动后健康接口应返回 `"ok": true`、`"db": true`；首次 DSM 登录前用户数可为零。旧版日志可能含设置口令，分享前需脱敏。时区沿用 `config.json` 的 `default_timezone`，其他设置见[配置参考](../docs/configuration.md)。

升级保留 DSM 持久化 `var` 目录；卸载前仍必须备份，不依赖卸载后的数据保留。回退旧版本需同时恢复匹配的数据备份，不能假定旧版兼容已迁移数据库。停止时发送 SIGTERM 并最多等待 60 秒，不直接强杀正在写数据库的进程。

真实 NAS 验收需覆盖：低权限账号运行认证程序、Nginx 路由安装与清理、管理员和普通用户首次登录、同名旧账号隔离、DSM 退出/过期/切换账号、管理员降权、聊天/终端连接关闭、NAS 重启及升级后数据保留。

参考：[DSM Web 认证](https://help.synology.com/developer-guide/integrate_dsm/web_authentication.html)、[Nginx 配置 worker](https://help.synology.com/developer-guide/resource_acquisition/web_config.html)、[DSM 套件权限](https://help.synology.com/developer-guide/privilege/privilege_config.html)、[套件数据目录](https://help.synology.com/developer-guide/integrate_dsm/fhs.html)、[群晖 CPU 与架构表](https://kb.synology.com/en-eu/DSM/tutorial/What_kind_of_CPU_does_my_NAS_have)。
