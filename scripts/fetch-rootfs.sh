#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
exec 9>"$op8_project/build/fetch-rootfs.lock"
flock -n 9 || { echo 'Rootfs fetch already running.' >&2; exit 1; }
op8_space_check
op8_name=ArchLinuxARM-aarch64-latest.tar.gz
op8_fetch "https://mirrors.tuna.tsinghua.edu.cn/archlinuxarm/os/$op8_name" "$op8_project/downloads/$op8_name"
printf '%s  %s\n' "$OP8_ROOTFS_SHA256" "$op8_project/downloads/$op8_name" | sha256sum -c -
gzip -t "$op8_project/downloads/$op8_name"
bsdtar -tf "$op8_project/downloads/$op8_name" > "$op8_project/artifacts/rootfs-file-list.txt"
sha256sum "$op8_project/downloads/$op8_name" > "$op8_project/artifacts/rootfs-SHA256SUMS"
echo 'Rootfs downloaded and gzip/tar integrity checked; SHA-256 recorded, not a publisher signature.'
echo 'Rootfs not yet deployed: privileged ownership/ACL extraction and credential provisioning remain.'
