#!/usr/bin/env bash
# Fetch the pinned Qualcomm A/B slot utility used by the Arch rootfs.
set -euo pipefail
source "$(dirname -- "$0")/common.sh"

op8_dest="$op8_project/downloads/qbootctl"
op8_url=https://github.com/linux-msm/qbootctl.git

if [[ ! -d "$op8_dest/.git" ]]; then
	git clone --filter=blob:none "$op8_url" "$op8_dest"
fi
git -C "$op8_dest" fetch --filter=blob:none origin "$OP8_QBOOTCTL_COMMIT"
git -C "$op8_dest" checkout --detach "$OP8_QBOOTCTL_COMMIT"
test "$(git -C "$op8_dest" rev-parse HEAD)" = "$OP8_QBOOTCTL_COMMIT"
git -C "$op8_dest" diff --quiet
git -C "$op8_dest" diff --cached --quiet
test -s "$op8_dest/qbootctl.c"
test -s "$op8_dest/meson.build"
echo "Verified qbootctl: $OP8_QBOOTCTL_COMMIT"
