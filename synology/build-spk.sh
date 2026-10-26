#!/usr/bin/env bash
# Build on a workstation; the resulting DSM package does not use Docker.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "${1:-}" != --inside ]]; then
    mkdir -p "$REPO_ROOT/build/synology" "$REPO_ROOT/dist"
    (
        cd "$REPO_ROOT/dashboard"
        npm ci --replace-registry-host=never
        VITE_DSM_AUTH=1 BASE_URL= npm run build -- \
            --base=/octop/ --outDir ../build/synology/dashboard
    )
    exec docker run --rm --platform linux/amd64 \
        -v "$REPO_ROOT:/src:ro" \
        -v "$REPO_ROOT/build/synology:/build" \
        -v "$REPO_ROOT/dist:/out" \
        -w /src python:3.12-bookworm \
        bash /src/synology/build-spk.sh --inside
fi

# Bookworm uses glibc 2.36, matching the DSM 7.2 geminilake toolchain.
test "$(uname -m)" = x86_64
export CC=gcc CXX=g++ UV_CACHE_DIR=/build/uv-cache PIP_CACHE_DIR=/build/pip-cache
python3 -m pip install --quiet uv==0.9.10
export GREEN_ROOT=/build/portable
# Reuse the repository's pinned, relocatable CPython 3.12 runtime.
bash desktop/portable/bootstrap-runtime.sh linux-amd64
source desktop/portable/_common.sh
VERSION="$(octop_version)-0005"
STAGE=$(mktemp -d /build/spk.XXXXXX)
trap 'rm -rf "$STAGE"' EXIT
PAYLOAD="$STAGE/payload"
mkdir -p "$PAYLOAD/bin" "$PAYLOAD/ui/images" "$PAYLOAD/nginx" "$STAGE/conf" "$STAGE/scripts"
cp -a "$GREEN_RUNTIMES/linux-amd64" "$PAYLOAD/runtime"
uv export --frozen --no-dev --no-emit-project -o /build/requirements.txt >/dev/null
uv build --wheel --out-dir /build/wheels .
uv pip install --python "$PAYLOAD/runtime/bin/python3" --target "$PAYLOAD/packages" \
    --require-hashes --no-deps -r /build/requirements.txt
uv pip install --python "$PAYLOAD/runtime/bin/python3" --target "$PAYLOAD/packages" \
    --no-deps "/build/wheels/octop-$(octop_version)-py3-none-any.whl"
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
displayname="Octop"
description="Native Octop AI assistant for Synology DS220+ (DSM 7.2 series). Bundled Python; no Docker required."
description_chs="Octop 原生 AI 助手，适用于 DS220+ / DSM 7.2 系列，内置 Python，无需 Docker。"
arch="geminilake"
os_min_ver="7.2-64570"
maintainer="Octop contributors"
maintainer_url="https://github.com/TencentCloud/Octop"
ctl_stop="yes"
dsmuidir="ui"
dsmappname="org.octop.Application"
instuninst_restart_services="nginx.service"
startstop_restart_services="nginx.service"
silent_upgrade="yes"
EOF
printf '{"defaults":{"run-as":"package"}}\n' > "$STAGE/conf/privilege"
cat > "$STAGE/conf/resource" <<'EOF'
{"web-config":{"nginx-static-config":{"enable":[{"type":"dsm","relpath":"nginx/octop.conf"}]}}}
EOF
cat > "$PAYLOAD/ui/config" <<'EOF'
{".url":{"org.octop.Application":{"title":"Octop","desc":"Octop AI assistant","icon":"images/icon_256.png","type":"url","url":"/octop/","allUsers":true}}}
EOF

# Exercise the actual bundled interpreter and lifecycle under a low-privilege user.
mv "$PAYLOAD" "$STAGE/relocated"
PAYLOAD="$STAGE/relocated"
chmod -R a+rX "$STAGE"
runuser -u nobody -- env SYNOPKG_PKGDEST="$PAYLOAD" \
    "$PAYLOAD/runtime/bin/python3" /src/synology/smoke-test.py "$PAYLOAD"

tar --format=gnu --owner=0 --group=0 -czf "$STAGE/package.tgz" -C "$PAYLOAD" .
printf 'checksum="%s"\n' "$(md5sum "$STAGE/package.tgz" | cut -d ' ' -f1)" >> "$STAGE/INFO"
printf 'extractsize="%s"\n' "$(du -sk "$PAYLOAD" | cut -f1)" >> "$STAGE/INFO"
OUTPUT="/out/Octop-synology-geminilake-${VERSION}.spk"
tar --format=ustar --owner=0 --group=0 -cf "$OUTPUT" -C "$STAGE" \
    INFO package.tgz scripts conf LICENSE PACKAGE_ICON.PNG PACKAGE_ICON_256.PNG
(cd /out && sha256sum "$(basename "$OUTPUT")" > "$(basename "$OUTPUT").sha256")
echo "Built $OUTPUT"
