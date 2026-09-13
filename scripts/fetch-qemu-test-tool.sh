#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
op8_pkg=qemu-user-static-11.1.1-1-x86_64.pkg.tar.zst
op8_url="https://mirrors.tuna.tsinghua.edu.cn/archlinux/extra/os/x86_64/$op8_pkg"
op8_fetch "$op8_url" "$op8_project/downloads/$op8_pkg"
printf '%s  %s\n' b6ad9e60c0d920f46acc54eba8dda715b427d0def86e2b6746c6f012187ece7b \
    "$op8_project/downloads/$op8_pkg" | sha256sum -c -
op8_fetch "$op8_url.sig" "$op8_project/downloads/$op8_pkg.sig"
gpgv --keyring /etc/pacman.d/gnupg/pubring.gpg "$op8_project/downloads/$op8_pkg.sig" "$op8_project/downloads/$op8_pkg"
mkdir -p "$op8_project/toolchains/qemu-test"
bsdtar -xf "$op8_project/downloads/$op8_pkg" -C "$op8_project/toolchains/qemu-test" usr/bin/qemu-aarch64-static
"$op8_project/toolchains/qemu-test/usr/bin/qemu-aarch64-static" --version
