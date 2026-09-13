#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
exec 8>"$op8_project/build/kernel-build.lock"
flock -n 8 || { echo 'Kernel build already running.' >&2; exit 1; }
op8_space_check
op8_jobs=${OP8_JOBS:-16}
[[ "$op8_jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'Invalid OP8_JOBS' >&2; exit 2; }
op8_kernel="$op8_project/sources/linux-$OP8_KERNEL_TAG"
op8_out="$op8_project/build/kernel"
op8_tc="$op8_project/toolchains/llvm-22.1.8/usr/bin"
test -s "$op8_kernel/Makefile"
test -x "$op8_tc/llvm-ar"
export PATH="$op8_tc:$PATH"
for op8_tool in clang ld.lld llvm-ar llvm-nm llvm-objcopy llvm-objdump llvm-strip; do command -v "$op8_tool"; done
mkdir -p "$op8_out" "$op8_project/artifacts/baseline"
if [[ ! -f "$op8_out/.config" ]]; then
    cp -- "$op8_project/configs/postmarketos-sm8250.config" "$op8_out/.config"
    "$op8_kernel/scripts/config" --file "$op8_out/.config" \
        -d DEBUG_INFO -d DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT -d DEBUG_INFO_DWARF4 \
        -d DEBUG_INFO_DWARF5 -d DEBUG_INFO_BTF -d DEBUG_INFO_BTF_MODULES \
        -e DEBUG_INFO_NONE -d WERROR --set-str LOCALVERSION '-op8-bringup'
fi
op8_make=(make -C "$op8_kernel" "O=$op8_out" ARCH=arm64 LLVM=1 LLVM_IAS=1)
"${op8_make[@]}" olddefconfig
"${op8_make[@]}" -j"$op8_jobs" Image modules dtbs
cp -- "$op8_out/arch/arm64/boot/Image" "$op8_project/artifacts/baseline/Image"
cp -- "$op8_out/.config" "$op8_project/artifacts/baseline/kernel.config"
cp -- "$op8_out/include/config/kernel.release" "$op8_project/artifacts/baseline/kernel.release"
"${op8_make[@]}" modules_install "INSTALL_MOD_PATH=$op8_project/artifacts/baseline/modules" INSTALL_MOD_STRIP=1
sha256sum "$op8_project/artifacts/baseline/Image" "$op8_project/artifacts/baseline/kernel.config" \
    > "$op8_project/artifacts/baseline/SHA256SUMS"
echo 'BASELINE BUILD COMPLETE — not an OP8 flash image; board bring-up remains unvalidated.'
