#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"

op8_dest="$op8_project/sources/linux-sm8250-7.2.5-op8"
op8_url=https://github.com/xjimlinx/mainline-instantnoodle.git

if [[ ! -d "$op8_dest/.git" ]]; then
	git clone --filter=blob:none --single-branch --branch 7.2.5-op8 \
		"$op8_url" "$op8_dest"
fi

test "$(git -C "$op8_dest" rev-parse HEAD)" = "$OP8_LINUX_7_2_5_SNAPSHOT" || {
	echo 'Linux 7.2.5 source identity mismatch; refusing to build.' >&2
	exit 1
}
git -C "$op8_dest" diff --quiet
git -C "$op8_dest" diff --cached --quiet
echo "Verified Linux 7.2.5 OP8 source: $OP8_LINUX_7_2_5_SNAPSHOT"
