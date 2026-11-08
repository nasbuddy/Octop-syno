# Octop-syno — 群晖原生 SPK

源码：[nasbuddy/Octop-syno 的 feat/synology-native 分支](https://github.com/nasbuddy/Octop-syno/tree/feat/synology-native)。`Octop-syno` 是发行名称，现有 SPK 内部标识仍为 `Octop`，数据路径保持一致。

面向 **64 位 x86（Intel / AMD）与 ARM64 群晖 NAS、DSM 7.0 正式版及以上** 的原生套件，自带 CPython 3.12、锁定的 Python 依赖、独立 Linux 运行库和 Web 控制台。NAS 运行时不需要 Docker、Container Manager 或另装 Python。

`0004` 修订接入 DSM 当前登录会话。从 DSM 主菜单或套件中心打开 Octop，使用同一 DSM 地址下的 `/octop/`，例如 `http://NAS_IP:5000/octop/` 或 `https://NAS_IP:5001/octop/`。DSM 自定义端口同样沿用当前端口。后台仅监听 `127.0.0.1:8089`，无需开放该端口。

`0005` 修订修复共享空状态图片的 `/octop/` 路径，覆盖定时任务、知识库等使用该图片的页面。

`0006` 修订新增 x86_64、aarch64 两种构建，最低安装版本改为 DSM `7.0-41890`。现代 Python 扩展所需的 glibc、加载器及 C++ 运行库保存在套件内部，不替换 DSM 系统库，也不向 DSM 子进程传递 `LD_LIBRARY_PATH`。同包附带对应的 glibc 源码、Debian 补丁与运行库许可文件。

`0007` 修订基于源码 `1.0.3b1`，DSM 数值版本为 `1.0.3-0007`，并设置 `beta="yes"`。这是预发布测试包，不是 `1.0.3` 正式版。欢迎页图片与预设头像沿用 `/octop/` 子路径，重复代理前缀的请求在 DSM 认证入口被拒绝。

`0008` 修订为 x86 套件锁定 NumPy 2.3.5 的官方 SSE3 wheel，保留 OpenBLAS 与动态 SIMD 分派。NumPy 2.4 起的官方 x86 wheel 要求 x86-64-v2，不能覆盖缺少 SSE4.2 的 Cedarview；`0007` 的 x86 包存在这一限制。ARM64 继续使用 `uv.lock` 中的 NumPy。构建检查实际 CPU baseline 及所有已安装依赖的有效 NumPy 版本约束，避免未来上游提高最低版本后静默不兼容。

HTTPS 客户端默认使用包内 certifi 信任根，不依赖 NAS 系统证书包；已有 `SSL_CERT_FILE` 覆盖值继续保留。两个架构的产物均为第三方测试包，Linux 运行库验证与 NAS 实机验收分别记录。

套件同时安装锁文件中的 `tzdata`，在系统没有标准 IANA 时区目录时提供回退数据；时区设置仍沿用 `config.json` 的 `default_timezone`。

## 兼容范围与验证边界

| DSM / 硬件 | 当前构建目标 |
|------------|--------------|
| DS220+ / DSM 7.2.1-69057 Update 12 | 旧版 `1.0.2-0004` 的安装、原生管理员登录及升级后数据保留历史记录 |
| DS220+ / DSM 7.4.1-90080 Update 1 | 已升级 `1.0.3-0008` 并启动；原生管理员登录、自动化页面图片与认证门禁通过 |
| DSM 7.0（41890 起）、7.1、7.2 系列 + 下列 64 位架构 | `0008` 构建目标；系统版本与具体机型仍需实机验收 |
| DSM 7.3 及后续版本 + 下列 64 位架构 | 无安装上限；后续系统变更仍需验证 |
| DSM 6.x、32 位 ARM / Intel、PowerPC | 不声明支持 |

两个包分别声明以下架构；不能跨 CPU 家族安装：

- x86_64：apollolake、avoton、braswell、broadwell、broadwellnk、broadwellnkv2、broadwellntbap、bromolow、cedarview、denverton、epyc7002、geminilake、geminilakenk、grantley、purley、v1000、v1000nk、r1000、r1000nk、x86_64、kvmx64。
- aarch64：armada37xx、rtd1296、rtd1619b。

DSM 版本与 CPU 架构是两个独立条件。模型调用仍需配置 LLM 服务；浏览器自动化、宿主桌面控制、Android、Docker 沙箱等可选能力未作为 DSM 原生组件适配。

实机记录（2026-10-21）：DS220+ / DSM 7.2.1-69057 Update 12 已升级至 `1.0.2-0004`。从当前 DSM 会话打开及刷新 `/octop/` 均可直接进入 Octop，用户管理页面可访问，DSM 管理员已同步为 Octop 管理员。同名旧账号及其 1 个专家独立保留，未自动合并；健康接口确认数据库正常、加载 2 个用户及 1 个运行中的 Agent。匿名业务请求返回 `401`，外部内部 MCP 路径返回 `404`，外部 `8089` 已关闭。

实机记录（2026-10-31）：通过 Edge 已有 DSM 会话升级至 `1.0.3-0007`。健康接口确认服务重新启动、数据库正常，升级前后的 2 个用户、3 个运行中的 Agent 数量一致。新标签页直接进入自动化与用户管理页面，当前 DSM 身份仍为管理员，同名旧账号独立保留；自动化空状态图片正常显示。匿名及伪造请求返回 `401`，重复 `/octop` 代理前缀返回 `404`。这些检查没有发送聊天消息或执行已有任务。

实机记录（2026-11-01）：同一 DS220+ 已升级至 `1.0.3-0008`，套件中心确认安装版本与“已启动”状态。重新加载自动化与用户管理页面可直接复用 DSM 会话，管理员角色和两份同名身份保持独立。数据库健康、2 个用户与 3 个运行中 Agent 数量保持一致；匿名/伪造请求及重复前缀门禁再次通过。

`0008` 的通用旧内核运行验证也已完成：x86 在 Linux 3.10.11、无 SSE4.2/AVX 的 qemu64 上运行；ARM64 在 Linux 4.4、Cortex-A53 上运行。两者均通过私有加载器、字体、NumPy 矩阵/FFT、时区、服务启停、认证和持久化检查。两种公开下载文件均已完整取回，与本地已验证包逐成员一致，仅追加服务端签名。这些内核验证不是 DSM 7.0 系统镜像或 ARM NAS 实机认证，仍需按具体设备验收。

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
# 也可以单独构建一个 CPU 家族
bash synology/build-spk.sh x86_64
bash synology/build-spk.sh aarch64
```

脚本构建专用 `/octop/` 前端，再用对应架构的 Debian Bookworm 容器生成 Linux 依赖，复用 `desktop/portable/bootstrap-runtime.sh` 的 CPython。除 x86 NumPy 使用 `synology/numpy-x86_64.txt` 的精确版本与哈希外，其余依赖按 `uv.lock` 安装。Docker 仅用于开发电脑构建。

每个架构的 CPython 展开目录、依赖缓存和打包暂存目录保存在 `octop-synology-build-x86_64`、`octop-synology-build-aarch64` 两个 Docker 卷中，以保留 Linux 的大小写和符号链接语义。依赖使用复制模式安装，随后只修补套件内的 ELF 文件，保持缓存中的原始 wheel 内容。

当前构建版本为 `1.0.3-0013 Beta`，产物为 `dist/Octop-synology-x86_64-1.0.3-0013.spk` 和 `dist/Octop-synology-aarch64-1.0.3-0013.spk`，均附 `.sha256` 文件。运行库清单记录在包内 `runtime-compatibility.json`。

DSM 的 `version` 各段只能包含数字，因此构建将源码版本中的 `aN`、`bN`、`rcN` 后缀移除，并用 `beta="yes"` 标记预发布。源码版本仍保留在包描述中，Python wheel 版本保持原样。`SPK_BUILD` 是脚本内的包修订号，每次发布都必须递增，包括 beta、rc 和正式版；例如下一包至少为 `1.0.3-0014`，未来 `1.0.3` 正式版必须使用比此前所有测试包更大的修订号，不能继续使用 `0013` 或更早修订号。参见 [DSM 版本字段](https://help.synology.com/developer-guide/synology_package/INFO_necessary_fields.html)与 [beta 标记](https://help.synology.com/developer-guide/synology_package/INFO_optional_fields.html)。

Beta 包同时提供 `report_url`，供 spkrepo v0.9.0 正确识别测试版。使用该版本套件源发布时，测试构建保持未激活，通过源站网页提供手动下载；[该服务不会向 DSM 7 订阅返回 Beta 包](https://github.com/SynoCommunity/spkrepo/blob/02d47df2a622ee92b112e2576f77d20e190e3f12/spkrepo/views/nas.py#L357-L361)。正式版生成时不写入 `report_url`。

包内 ELF 使用 DSM 的稳定路径 `/var/packages/Octop/target/runtime/lib/` 加载私有运行库；因此不能把构建后的 Python 单独复制到任意目录执行。容器验证时须将完整程序挂载到 `/var/packages/Octop/target/`。

构建会以低权限 Linux 用户检查原生扩展、子解释器、页面、匿名/伪造会话拒绝、服务启停、重复启动、失效 PID 和重启后数据保留。Linux 检查不模拟成功的 DSM 登录，不能替代 NAS 验收。

## 安装与升级

1. 升级前停止套件并备份整个 `/var/packages/Octop/var/`。从旧版独立账号登录切换时，DSM 身份会新建账号，旧账号数据保留但不会自动迁移所有权。
2. 在 DSM **套件中心 → 手动安装**选择对应 CPU 家族的 SPK。本地构建产物未签名；套件源发布时另行签名，均属于第三方包。
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

## 内置群晖管家（0011）

`1.0.3-0011` 内置 NAS MCP 和“群晖管家”。原生 DSM 登录后自动为该用户创建私有连接器，并把专家加入“我的专家”；原有专家、会话和当前默认选择保留。无需单独安装 NAS MCP 或复制令牌。实际操作使用当前 DSM 身份，业务 API 只请求 NAS 本机；每次工具调用重新校验 DSM 会话，不保存密码、Cookie 或 SID 到磁盘。

写操作默认预览，确认具体目标与影响后再执行；连接器可以通过 `allow_writes=false` 限制为只读。服务重启后重新打开已登录的 Octop 页面以恢复内存会话。新能力的验证记录见本次构建与验收报告，不能将此前 0008 的验证等同于 0011 实机验收。参见 [连接器说明](../docs/connectors.md)。

自动创建会避开已有的同名专家；创建失败不会阻断正常 DSM 登录，且不会打印异常中的凭据内容。已创建的专家、绑定和用户修改会在后续升级中保留。

0011 验收：`make all` 为 5377 项通过、34 项跳过；x86_64 与 ARM64 的构建、完整归档核对、依赖加载及 Linux 原生启动／重启检查通过。DS220+（DSM 7.4.1-90080 Update 1）已升级并实测原生登录、私有连接器、10 个工具探测和系统信息读取，原有专家、对话与任务保留。ARM64 尚未实机验收；未为验收执行 NAS 业务写入。

## 应用技能（0012 起）

`1.0.3-0012 Beta` 为“群晖管家”新增 9 个独立应用技能：Note Station 笔记、Synology Calendar 日历、套件中心应用管理、File Station 文件、Download Station 下载、Container Manager / Docker 容器、Virtual Machine Manager、Synology Photos 和 Audio Station。原有 `synology-nas` 负责共用连接检查、授权、DSM 系统、存储和网络巡检；专家按本次需求加载对应技能。

`1.0.3-0013 Beta` 补齐笔记创建、编辑、移入回收站和恢复，以及套件目录、兼容性和依赖查询、安装、升级与进度查询。启动、停止和新建下载继续使用已有操作。写入默认先预览，执行需连接器写入权限；笔记冲突检查和套件签名检查保持启用。特殊安装向导和宿主套件自身升级仍需在 DSM 套件中心完成。上述业务写入尚未完成 NAS 实机验收。

技能共用原生 NAS MCP 的 10 个工具，实际能力仍取决于当前账号权限、已安装套件与接口版本。Calendar 附只读请求参考，写入参数需按实际版本核实；没有可靠参数时只提供草稿或方案，不报告为已执行。应用内部业务读写尚未逐项实机验收。

升级继续保留已有专家工作区，不覆盖用户修改或自动重建专家；新建群晖管家使用新版模板。当前验收账号已有的群晖管家已通过应用技能接口追加并启用上述 9 个技能，未改动原有对话和定时任务。
