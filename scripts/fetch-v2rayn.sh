#!/usr/bin/env bash
# Fetch the pinned official v2rayN Linux ARM64 portable release.
set -euo pipefail
source "$(dirname -- "$0")/common.sh"

name=v2rayN-linux-arm64.zip
directory="$op8_project/downloads/v2rayN/$OP8_V2RAYN_VERSION"
archive="$directory/$name"
url="https://github.com/2dust/v2rayN/releases/download/$OP8_V2RAYN_VERSION/$name"

mkdir -p "$directory"
op8_fetch "$url" "$archive"
printf '%s  %s\n' "$OP8_V2RAYN_LINUX_ARM64_SHA256" "$archive" | sha256sum -c -
bsdtar -tf "$archive" >/dev/null
echo "Verified v2rayN $OP8_V2RAYN_VERSION Linux ARM64 archive"
