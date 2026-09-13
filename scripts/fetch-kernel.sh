#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
exec 9>"$op8_project/build/fetch-kernel.lock"
flock -n 9 || { echo 'Kernel fetch already running.' >&2; exit 1; }
op8_space_check
op8_archive="$op8_project/downloads/linux-$OP8_KERNEL_TAG.tar.gz"
op8_cfg="$op8_project/configs/postmarketos-sm8250.config"
op8_fetch "https://gitlab.postmarketos.org/soc/qualcomm-sm8250/linux/-/archive/$OP8_KERNEL_TAG/linux-$OP8_KERNEL_TAG.tar.gz" "$op8_archive"
printf '%s  %s\n' "$OP8_KERNEL_SHA512" "$op8_archive" | sha512sum -c -
op8_fetch "https://gitlab.postmarketos.org/postmarketOS/pmaports/-/raw/$OP8_PMAPORTS_COMMIT/device/testing/linux-postmarketos-qcom-sm8250/config-postmarketos-qcom-sm8250.aarch64" "$op8_cfg"
printf '%s  %s\n' "$OP8_CONFIG_SHA512" "$op8_cfg" | sha512sum -c -
if [[ ! -d "$op8_project/sources/linux-$OP8_KERNEL_TAG" ]]; then
    op8_unpack=$(mktemp -d "$op8_project/sources/unpack.XXXXXX")
    bsdtar -xf "$op8_archive" -C "$op8_unpack"
    test -s "$op8_unpack/linux-$OP8_KERNEL_TAG/Makefile"
    mv -- "$op8_unpack/linux-$OP8_KERNEL_TAG" "$op8_project/sources/"
    rmdir -- "$op8_unpack"
fi
echo 'Pinned kernel source and configuration verified.'
