# nas-local-mcp

Source: user-provided `nas-local-mcp` source, version 0.1.0.

Repository HEAD: `5f8b8f9f5825bd7588b48b1f34c07da7c997c557`. This is a source snapshot, including the existing working-tree content. Original license: Apache-2.0, retained in LICENSE.md.

Original source SHA-256:

- `nas_mcp.py`: `3e23ef78c510a15c8cf6ba1e1eaf83825331037dbb6a7b04206d2a160cf2957b`
- `operations.py`: `7aedf728c75ff316fbbf647d6d82be15d91c2f28a953afa2e9ae10de0e977170`
- `LICENSE`: `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`

Octop adaptations: package-relative imports; MCP 1.x FastMCP compatibility; request-local configuration and HTTP transport injection. Standalone HTTP/OAuth, CLI and self-test entry points are omitted from this embedded runtime. No credentials or NAS-specific state are bundled.

Octop adds Note Station create/edit/trash/restore workflows in `notes.py`, with JSON parameter encoding, revision checks, read-back verification and localized results. Request formats follow the user-provided my-nas client's `lib/api/note_api.dart`; attachment mutations and encrypted-note writes are not enabled by these workflows.

Package Center recipes and `packages.py` follow `my-nas/lib/api/api.dart` for catalog/preflight, installation, upgrades and task queries. The adapter preserves per-field JSON encoding, signature checks and the write gate, and blocks self-stop/self-upgrade of Octop/NasMCP. Installation wizard completion and final state checks remain explicit expert steps.
