#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
df -h "$op8_project"
for op8_log in pipeline fetch-kernel fetch-rootfs build-kernel; do
    if [[ -f "$op8_project/logs/$op8_log.log" ]]; then
        printf '\n%s\n' "$op8_log"
        tail -c 1400 "$op8_project/logs/$op8_log.log" | tr '\r' '\n' | tail -8
    fi
done
printf '\nActive pipeline lock: '
if flock -n "$op8_project/build/pipeline.lock" true; then
    echo 'not held (inspect logs for success/failure)'
else
    echo 'held'
fi
