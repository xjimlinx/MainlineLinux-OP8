#!/usr/bin/env bash
# Update an already-installed OP8 rootfs before booting a rebuilt kernel.
set -euo pipefail
source "$(dirname -- "$0")/common.sh"

target=${1:-xein@172.16.42.1}
release=$(<"$op8_project/artifacts/linux-7.2.5-op8/kernel.release")
modules="$op8_project/artifacts/linux-7.2.5-op8/modules-root/lib/modules/$release"
[[ -d $modules/kernel ]] || { echo "missing modules: $modules" >&2; exit 1; }
remote_release=$(ssh "$target" uname -r)
[[ $remote_release = "$release" ]] || {
	echo "running kernel is $remote_release, expected $release" >&2
	exit 1
}

bundle=$(mktemp --tmpdir="$op8_project/build" "$release-modules.XXXXXX.tar.zst")
trap 'rm -f "$bundle"' EXIT
tar --zstd --exclude="$release/build" --exclude="$release/source" \
	-C "$(dirname -- "$modules")" -cf "$bundle" "$release"
scp "$bundle" "$target:/tmp/$release-modules.tar.zst"
ssh -t "$target" "sudo tar --zstd -xf /tmp/$release-modules.tar.zst -C /usr/lib/modules && sudo depmod -a $release && rm -f /tmp/$release-modules.tar.zst"
echo "Installed matching modules for $release on $target"
