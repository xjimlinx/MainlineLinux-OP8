#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
op8_kernel="$op8_project/sources/linux-$OP8_KERNEL_TAG"
op8_variant="${1:-diagnostic}"
case "$op8_variant" in
    diagnostic|storage-probe) ;;
    *) echo 'Usage: build-diagnostic-dtb.sh [diagnostic|storage-probe]' >&2; exit 2 ;;
esac
op8_dts="$op8_project/device/instantnoodle/sm8250-oneplus-instantnoodle-$op8_variant.dts"
mkdir -p "$op8_project/build/board-audit" "$op8_project/artifacts/$op8_variant"
clang -E -P -x assembler-with-cpp -nostdinc -undef -D__DTS__ \
    -I "$op8_kernel/include" -I "$op8_kernel/arch/arm64/boot/dts/qcom" \
    "$op8_dts" -o "$op8_project/build/board-audit/$op8_variant.preprocessed.dts"
"$op8_project/build/kernel/scripts/dtc/dtc" -@ -I dts -O dtb \
    -o "$op8_project/artifacts/$op8_variant/instantnoodle-$op8_variant.dtb" \
    "$op8_project/build/board-audit/$op8_variant.preprocessed.dts"
echo 'DTB syntax compiled only; not bootloader/driver validation. Do not flash this file.'
