#!/usr/bin/env bash
# Keep a foreground supervisor alive so all work belongs to one managed session.
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
exec 7>"$op8_project/build/pipeline.lock"
flock -n 7 || { echo 'Pipeline already running.' >&2; exit 1; }
op8_space_check
date -Is
bash "$op8_project/scripts/fetch-toolchain.sh"
bash "$op8_project/scripts/fetch-rootfs.sh" > "$op8_project/logs/fetch-rootfs.log" 2>&1 &
op8_rootfs_pid=$!
bash "$op8_project/scripts/fetch-kernel.sh" > "$op8_project/logs/fetch-kernel.log" 2>&1 &
op8_kernel_pid=$!
wait "$op8_kernel_pid"
echo 'Source verified. Starting ARM64 baseline compilation.'
bash "$op8_project/scripts/build-kernel.sh" 2>&1 | tee "$op8_project/logs/build-kernel.log"
wait "$op8_rootfs_pid"
date -Is
echo 'Host baseline pipeline complete. OP8 board validation and rootfs deployment are still pending.'
