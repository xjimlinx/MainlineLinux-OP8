#!/usr/bin/env bash
# Fetch reference data only. Never execute another device's boot/install scripts.
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
op8_refs="$op8_project/sources/github-references"
mkdir -p "$op8_refs"
op8_reference() {
    local url=$1 name=$2 digest=$3
    op8_fetch "$url" "$op8_refs/$name"
    printf '%s  %s\n' "$digest" "$op8_refs/$name" | sha256sum --check --status || {
        echo "Reference mismatch: $name; preserved for inspection, not used." >&2
        return 1
    }
    echo "Verified reference: $name"
}
op8_reference \
    'https://raw.githubusercontent.com/ben443/sm8250-mainline/5621501522434c4d7119b50372971899c8f8a77d/arch/arm64/boot/dts/qcom/sm8250-oneplus-instantnoodlep.dts' \
    'ben443-instantnoodlep-56215015.dts' \
    '19ad4db52ca29202a7c19f3bfbf3ba1fea034623c7c087371839bf808244db01'
op8_reference \
    'https://raw.githubusercontent.com/ccc007ccc/sm8250-xiaomi-lmi-initramfs/ca90a154cc10db18ab28d524235ef3f8c8d14e47/README.md' \
    'lmi-initramfs-ca90a154-README.md' \
    '6124b7f24299b4db55795ee4453a1a3a340e0ff40041c646e97096735a79cee4'
echo 'References only: neither file is an OP8 installer or build input.'
