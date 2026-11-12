#!/usr/bin/env bash
# Build on a workstation; the resulting DSM package does not use Docker.

spk_version_metadata() {
    local upstream_version="$1" build="$2" beta=no
    if [[ ! "$upstream_version" =~ ^([0-9]+\.[0-9]+\.[0-9]+)([ab][0-9]+|rc[0-9]+)?$ ]]; then
        echo "Unsupported Octop version for DSM: $upstream_version" >&2
        return 2
    fi
    local feature="${BASH_REMATCH[1]}" prerelease="${BASH_REMATCH[2]}"
    if [[ ! "$build" =~ ^[0-9]+$ ]]; then
        echo "Invalid DSM build number: $build" >&2
        return 2
    fi
    [[ -z "$prerelease" ]] || beta=yes
    printf '%s-%s %s\n' "$feature" "$build" "$beta"
}

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    return
fi

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "${1:-}" != --inside ]]; then
    case "${1:-all}" in
        all) TARGETS=(x86_64 aarch64) ;;
        x86_64|aarch64) TARGETS=("$1") ;;
        *) echo "Usage: bash synology/build-spk.sh [all|x86_64|aarch64]" >&2; exit 2 ;;
    esac
    mkdir -p "$REPO_ROOT/build/synology" "$REPO_ROOT/dist"
    (
        cd "$REPO_ROOT/dashboard"
        npm ci --replace-registry-host=never
        VITE_DSM_AUTH=1 BASE_URL= npm run build -- \
            --base=/octop/ --outDir ../build/synology/dashboard --emptyOutDir
    )
    for target in "${TARGETS[@]}"; do
        docker_arch=amd64
        [[ "$target" != aarch64 ]] || docker_arch=arm64
        docker run --rm --platform "linux/$docker_arch" \
            -v "$REPO_ROOT:/src:ro" \
            -v "$REPO_ROOT/build/synology:/build" \
            --mount "type=volume,src=octop-synology-build-${target},dst=/build/${target},volume-nocopy" \
            -v "$REPO_ROOT/dist:/out" \
            -w /src python:3.12-bookworm \
            bash /src/synology/build-spk.sh --inside "$target"
    done
    exit 0
fi

TARGET="${2:?missing build target}"
case "$TARGET" in
    x86_64)
        PORTABLE=linux-amd64
        ARCHS="apollolake avoton braswell broadwell broadwellnk broadwellnkv2 broadwellntbap bromolow cedarview denverton epyc7002 geminilake geminilakenk grantley purley v1000 v1000nk r1000 r1000nk x86_64 kvmx64"
        ;;
    aarch64)
        PORTABLE=linux-arm64
        ARCHS="armada37xx rtd1296 rtd1619b"
        ;;
    *) echo "Unsupported build target: $TARGET" >&2; exit 2 ;;
esac
test "$(uname -m)" = "$TARGET"
BUILD="/build/$TARGET"
mkdir -p "$BUILD"
export CC=gcc CXX=g++ UV_CACHE_DIR="$BUILD/uv-cache" PIP_CACHE_DIR="$BUILD/pip-cache"
python3 -m venv "$BUILD/build-tools"
"$BUILD/build-tools/bin/python" -m pip install --quiet uv==0.9.10 patchelf==0.17.2.4
export PATH="$BUILD/build-tools/bin:$PATH"
export GREEN_ROOT="$BUILD/portable"
# Reuse the repository's pinned, relocatable CPython 3.12 runtime.
bash desktop/portable/bootstrap-runtime.sh "$PORTABLE"
source desktop/portable/_common.sh
UPSTREAM_VERSION="$(octop_version)"
# Increase for every published SPK, including prereleases and final releases.
SPK_BUILD=0015
SPK_METADATA="$(spk_version_metadata "$UPSTREAM_VERSION" "$SPK_BUILD")"
read -r VERSION BETA <<<"$SPK_METADATA"
STAGE=$(mktemp -d "$BUILD/spk.XXXXXX")
trap 'rm -rf "$STAGE"' EXIT
PAYLOAD="$STAGE/payload"
mkdir -p "$PAYLOAD/bin" "$PAYLOAD/ui/images" "$PAYLOAD/nginx" "$STAGE/conf" "$STAGE/scripts"
cp -a "$GREEN_RUNTIMES/$PORTABLE" "$PAYLOAD/runtime"
EXPORT_ARGS=()
if [[ "$TARGET" == x86_64 ]]; then
    EXPORT_ARGS+=(--no-emit-package numpy)
fi
uv export --frozen --no-dev --no-emit-project "${EXPORT_ARGS[@]}" \
    -o "$BUILD/requirements.txt" >/dev/null
if [[ "$TARGET" == x86_64 ]]; then
    cat synology/numpy-x86_64.txt >> "$BUILD/requirements.txt"
fi
uv build --wheel --out-dir "$BUILD/wheels" .
# Bundle the lock's IANA database so scheduling also works without system zoneinfo.
python3 - <<'PY' >> "$BUILD/requirements.txt"
import tomllib
from pathlib import Path

packages = tomllib.loads(Path("uv.lock").read_text())["package"]
package = next(item for item in packages if item["name"] == "tzdata")
hashes = " ".join("--hash=" + wheel["hash"] for wheel in package["wheels"])
print(f"tzdata=={package['version']} {hashes}")
PY
uv pip install --python "$PAYLOAD/runtime/bin/python3" --target "$PAYLOAD/packages" \
    --link-mode=copy --require-hashes --no-deps -r "$BUILD/requirements.txt"
uv pip install --python "$PAYLOAD/runtime/bin/python3" --target "$PAYLOAD/packages" \
    --link-mode=copy --no-deps "$BUILD/wheels/octop-$(octop_version)-py3-none-any.whl"
rm -rf "$PAYLOAD/packages/octop/dashboard"
cp -a /build/dashboard "$PAYLOAD/packages/octop/dashboard"
# Native DSM shares an origin with other apps; do not install a root-scoped PWA.
sed -i '/rel="manifest"/d' "$PAYLOAD/packages/octop/dashboard/index.html"
cp desktop/portable/templates/launch.py synology/native/service.py "$PAYLOAD/"
cp synology/native/nginx.conf "$PAYLOAD/nginx/octop.conf"
install -m 755 synology/native/bin/octop "$PAYLOAD/bin/octop"
install -m 755 synology/native/start-stop-status "$STAGE/scripts/start-stop-status"
for script in preinst postinst preuninst postuninst preupgrade postupgrade; do
    printf '#!/bin/sh\nexit 0\n' > "$STAGE/scripts/$script"
    chmod 755 "$STAGE/scripts/$script"
done
cp fnos/native/app/ui/images/icon_64.png "$STAGE/PACKAGE_ICON.PNG"
cp fnos/native/app/ui/images/icon_256.png "$STAGE/PACKAGE_ICON_256.PNG"
cp fnos/native/app/ui/images/*.png "$PAYLOAD/ui/images/"
cp LICENSE "$STAGE/LICENSE"
cat > "$STAGE/INFO" <<EOF
package="Octop"
version="$VERSION"
beta="$BETA"
displayname="Octop-syno"
description="Native Octop AI assistant from source $UPSTREAM_VERSION for 64-bit Synology NAS, DSM 7.0 or later. Bundled Python and runtime libraries; no Docker required. Third-party test package; device validation pending."
description_chs="Octop 原生 AI 助手，源码版本 $UPSTREAM_VERSION，适用于 64 位群晖 NAS、DSM 7.0 起，内置 Python 和运行库，无需 Docker。第三方测试包，具体机型尚待实机验收。"
arch="$ARCHS"
os_min_ver="7.0-41890"
maintainer="Octop contributors"
maintainer_url="https://github.com/TencentCloud/Octop"
ctl_stop="yes"
dsmuidir="ui"
dsmappname="org.octop.Application"
instuninst_restart_services="nginx.service"
startstop_restart_services="nginx.service"
silent_upgrade="yes"
EOF
if [[ "$BETA" == yes ]]; then
    printf 'report_url="https://github.com/nasbuddy/Octop-syno/issues"\n' >> "$STAGE/INFO"
fi
printf '{"defaults":{"run-as":"package"}}\n' > "$STAGE/conf/privilege"
cat > "$STAGE/conf/resource" <<'EOF'
{"web-config":{"nginx-static-config":{"enable":[{"type":"dsm","relpath":"nginx/octop.conf"}]}}}
EOF
cat > "$PAYLOAD/ui/config" <<'EOF'
{".url":{"org.octop.Application":{"title":"Octop","desc":"Octop AI assistant","icon":"images/icon_256.png","type":"url","url":"/octop/","allUsers":true}}}
EOF

# Exercise the actual bundled interpreter and lifecycle under a low-privilege user.
python3 /src/synology/bundle-runtime.py "$PAYLOAD"
mv "$PAYLOAD" "$STAGE/relocated"
PAYLOAD="$STAGE/relocated"
chmod -R a+rX "$STAGE"
# The private ELF interpreter uses DSM's stable package path, only inside this container.
mkdir -p /var/packages/Octop
ln -s "$PAYLOAD" /var/packages/Octop/target
runuser -u nobody -- env SYNOPKG_PKGDEST="$PAYLOAD" PYTHONTZPATH= \
    "$PAYLOAD/runtime/bin/python3" /src/synology/smoke-test.py "$PAYLOAD"

tar --format=gnu --owner=0 --group=0 -czf "$STAGE/package.tgz" -C "$PAYLOAD" .
printf 'checksum="%s"\n' "$(md5sum "$STAGE/package.tgz" | cut -d ' ' -f1)" >> "$STAGE/INFO"
printf 'extractsize="%s"\n' "$(du -sk "$PAYLOAD" | cut -f1)" >> "$STAGE/INFO"
OUTPUT="/out/Octop-synology-${TARGET}-${VERSION}.spk"
tar --format=ustar --owner=0 --group=0 -cf "$OUTPUT" -C "$STAGE" \
    INFO package.tgz scripts conf LICENSE PACKAGE_ICON.PNG PACKAGE_ICON_256.PNG
(cd /out && sha256sum "$(basename "$OUTPUT")" > "$(basename "$OUTPUT").sha256")
echo "Built $OUTPUT"
