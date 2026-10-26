# [Package Request] Octop-syno

### Software Name

Octop-syno

### Brief Description

A proposed native Synology DSM distribution of Octop, an open-source, self-hosted AI assistant platform with multiple users, multiple agents, a web dashboard, scheduled tasks, and configurable LLM providers. The NAS runtime does not require Docker or Container Manager. Users configure their own LLM provider; the package does not include a language model.

### Website

[Octop-syno](https://github.com/nasbuddy/Octop-syno/tree/feat/synology-native), a Synology adaptation of [upstream Octop](https://github.com/TencentCloud/Octop).

### Documentation

[Octop README and quick start](https://github.com/TencentCloud/Octop/blob/main/README.md)

### Build/Installation Documentation

[Synology SPK build and installation guide](https://github.com/nasbuddy/Octop-syno/blob/feat/synology-native/synology/README.md) and [build script](https://github.com/nasbuddy/Octop-syno/blob/feat/synology-native/synology/build-spk.sh). The guide is in Chinese; the main requirements are summarized below. General development instructions are in the [upstream build guide](https://github.com/TencentCloud/Octop/blob/main/CONTRIBUTING.md).

### Source Code

[nasbuddy/Octop-syno, branch feat/synology-native](https://github.com/nasbuddy/Octop-syno/tree/feat/synology-native), containing the application, Synology packaging, DSM authentication integration, and tests. The application and packaging snapshot under review is [0281cf35](https://github.com/nasbuddy/Octop-syno/commit/0281cf35c0fdb3b3723f3c2db436e0bd0479ecab), based on upstream commit `4632d0f4` and application version `1.0.2`. This is an initial package request, before submission of a `spksrc` implementation; it is an independent adaptation, not an upstream-endorsed Synology release.

### First Public Release / Development

- Upstream Octop: the earliest commit currently visible in its public repository is dated [2026-07-09](https://github.com/TencentCloud/Octop/commit/748d998cf2c5b4724faa8d0f13be7abcea9b9a42). This is repository-history evidence, not independent verification of when the repository first became public. The first 1.0 release, [v1.0.0](https://github.com/TencentCloud/Octop/releases/tag/v1.0.0), was published on 2026-09-14.
- Octop-syno adaptation: first published in this public fork on 2026-10-26. It is a prototype and has no published stable SPK release yet.

### Upstream Project Maturity

Upstream has several months of visible development history and releases including [v1.0.0](https://github.com/TencentCloud/Octop/releases/tag/v1.0.0) (2026-09-14), [v1.0.1](https://github.com/TencentCloud/Octop/releases/tag/v1.0.1) (2026-09-19), and [v1.0.2](https://github.com/TencentCloud/Octop/releases/tag/v1.0.2) (2026-10-18). Recent maintenance includes a [chat-model fix merged on 2026-10-26](https://github.com/TencentCloud/Octop/pull/2407) and an [upstream collaborator response to a PDF issue](https://github.com/TencentCloud/Octop/issues/2412#issuecomment-6414804547) on the same day.

The Synology adaptation is much newer. Its source, tests, build script, and limited prototype device results are available for feasibility review. The published application snapshot passed local `make all PYTEST_JOBS=4` checks (5,109 passed, 35 skipped), along with frontend typechecking/build and nine focused DSM frontend tests on 2026-10-26. These are local checks, not SynoCommunity CI or complete NAS acceptance. This request starts a packaging discussion; it does not claim the package is ready for release.

### Ongoing Maintenance and Support

A dedicated long-term SynoCommunity package maintainer is not yet confirmed, and no maintenance SLA or release schedule is promised. This request provides the prototype implementation and test evidence for review. The proposed responsibility split is to handle DSM packaging, service lifecycle, and DSM authentication issues in the adaptation, and report reproducible application bugs to upstream. Agreeing on a maintainer, update workflow, dependency/license review, and supported DSM/architecture test coverage remains necessary before a release-ready PR.

### Open Source License

MIT

### Other License

The application license is [MIT](https://github.com/nasbuddy/Octop-syno/blob/feat/synology-native/LICENSE), inherited from [upstream Octop](https://github.com/TencentCloud/Octop/blob/main/LICENSE). The bundled runtime and dependencies have their own licenses; their redistribution notices still need review as part of packaging.

## Motivation and naming

The requested integration would let users install and update Octop through DSM Package Center, manage its service through DSM, and open it using their existing DSM browser session.

`Octop-syno` is the proposed name for this Synology distribution. The upstream application remains Octop. The current prototype still uses `Octop` as its internal SPK package ID; repository naming and migration from that ID would need to be settled during packaging review.

## Initial target and prototype

- Initial hardware: Synology DS220+, `geminilake` / x86-64.
- Package metadata minimum: DSM `7.2-64570`. Recorded device testing is limited to DSM `7.2.1-69057 Update 12`; other DSM versions and CPU architectures are not claimed as tested.
- Runtime: bundled CPython 3.12, Python dependencies resolved from `uv.lock`, and the React dashboard. SQLite is the default database; no separate database service is required for that configuration.
- Build workstation: Node.js/npm, uv, and Docker with Linux amd64 support. In the checkout containing the Synology changes, `bash synology/build-spk.sh` builds the `/octop/` frontend, assembles the Python runtime and dependencies, and creates the SPK. Docker is a build-time tool only.
- Installation: use DSM Package Center's manual installation flow, then open `/octop/` on the same DSM origin while signed in as a DSM administrator. This is the prototype workflow, not an existing SynoCommunity package.

## DSM integration

- The service runs as a DSM package user, listens on `127.0.0.1:8089`, and is exposed through the package-managed `/octop/` Nginx route.
- Persistent application data is stored under `/var/packages/Octop/var/.octop/`. Package upgrades are designed to retain that directory.
- The local DSM authentication program validates the current browser session. DSM administrators map to Octop administrators; other DSM users map to ordinary accounts. Existing same-name Octop accounts are not automatically merged.
- Agent tools share the package's operating-system identity. DSM user mapping does not provide a separate OS sandbox for each user.

## Validation status and remaining work

Local test notes dated 2026-10-21 record installation/upgrade, DSM administrator login, and retained data for prototype `1.0.2-0004` on the DS220+ above. These are historical prototype results, not acceptance results for a future `spksrc` build. A later local `1.0.2-0005` SPK exists, but its NAS installation has not been confirmed in those records.

Before a release-ready PR, the work includes adapting the integration to `spksrc`, building all declared supported architectures, and completing fresh-install and upgrade tests. Ordinary-user login, session expiration/account switching, administrator demotion, long-lived connection invalidation, and NAS reboot still require device validation. Browser automation, host desktop/Android control, and Docker sandbox features are outside the initial native DSM validation scope.

Feedback on the proposed scope, package name, and preferred Python packaging approach would be helpful before preparing the implementation PR.
