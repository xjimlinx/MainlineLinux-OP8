#!/usr/bin/env bash
# Fetch the pinned OP8 firmware and ALSA configuration used by the tested rootfs.
set -euo pipefail
source "$(dirname -- "$0")/common.sh"

op8_dest="$op8_project/sources/github-references/linux-oneplus-instantnoodle"
op8_url=https://github.com/Xo666/linux-oneplus-instantnoodle.git

if [[ ! -d "$op8_dest/.git" ]]; then
	git clone --filter=blob:none "$op8_url" "$op8_dest"
fi
git -C "$op8_dest" fetch --filter=blob:none origin "$OP8_DEVICE_ASSETS_COMMIT"
git -C "$op8_dest" checkout --detach "$OP8_DEVICE_ASSETS_COMMIT"
test "$(git -C "$op8_dest" rev-parse HEAD)" = "$OP8_DEVICE_ASSETS_COMMIT"
git -C "$op8_dest" diff --quiet
git -C "$op8_dest" diff --cached --quiet
test -s "$op8_dest/firmware-oneplus-instantnoodle/usr/lib/firmware/qcom/sm8250/OnePlus8/a650_zap.mbn"
test -s "$op8_dest/alsa-oneplus-instantnoodle/usr/share/alsa/ucm2/OnePlus/OnePlus8.conf"
echo "Verified OP8 firmware/ALSA assets: $OP8_DEVICE_ASSETS_COMMIT"
