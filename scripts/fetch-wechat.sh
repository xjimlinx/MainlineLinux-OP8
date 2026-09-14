#!/usr/bin/env bash
# Fetch the pinned Tencent Linux ARM64 WeChat package.
set -euo pipefail
source "$(dirname -- "$0")/common.sh"

name=WeChatLinux_arm64.deb
archive="$op8_project/downloads/wechat/$name"
url="https://dldir1v6.qq.com/weixin/Universal/Linux/$name"

mkdir -p "$(dirname -- "$archive")"
op8_fetch "$url" "$archive"
printf '%s  %s\n' "$OP8_WECHAT_LINUX_ARM64_SHA256" "$archive" | sha256sum -c -
test "$(ar p "$archive" debian-binary)" = 2.0
control_member=$(ar t "$archive" | grep -m1 '^control\.tar')
version=$(ar p "$archive" "$control_member" | bsdtar -xOf - ./control | sed -n 's/^Version: //p')
architecture=$(ar p "$archive" "$control_member" | bsdtar -xOf - ./control | sed -n 's/^Architecture: //p')
test "$version" = "$OP8_WECHAT_VERSION"
test "$architecture" = arm64
echo "Verified WeChat $version Linux ARM64 package"
