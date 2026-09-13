#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
op8_pkg=llvm-22.1.8-2-x86_64.pkg.tar.zst
op8_url="https://mirrors.tuna.tsinghua.edu.cn/archlinux/extra/os/x86_64/$op8_pkg"
op8_fetch "$op8_url" "$op8_project/downloads/$op8_pkg"
printf '%s  %s\n' df30290f4af86681bd06a5a48ffda1e78ce6d9abd911fb62faa053a750759ea5 \
    "$op8_project/downloads/$op8_pkg" | sha256sum -c -
op8_fetch "$op8_url.sig" "$op8_project/downloads/$op8_pkg.sig"
gpgv --keyring /etc/pacman.d/gnupg/pubring.gpg \
    "$op8_project/downloads/$op8_pkg.sig" "$op8_project/downloads/$op8_pkg"
if [[ ! -f "$op8_project/toolchains/llvm-22.1.8/.extract-complete" ]]; then
    mkdir -p "$op8_project/toolchains/llvm-22.1.8"
    bsdtar -xf "$op8_project/downloads/$op8_pkg" -C "$op8_project/toolchains/llvm-22.1.8"
    touch "$op8_project/toolchains/llvm-22.1.8/.extract-complete"
fi
"$op8_project/toolchains/llvm-22.1.8/usr/bin/llvm-ar" --version
clang --version
echo 'Using system Clang/LLD/libLLVM 22.1.8 and verified project-local LLVM utilities.'
