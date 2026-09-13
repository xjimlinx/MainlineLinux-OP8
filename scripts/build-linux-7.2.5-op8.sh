#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "$0")/common.sh"

op8_space_check
op8_jobs=${OP8_JOBS:-16}
[[ "$op8_jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'Invalid OP8_JOBS' >&2; exit 2; }

op8_kernel="$op8_project/sources/linux-sm8250-7.2.5-op8"
op8_out="$op8_project/build/kernel-7.2.5-op8"
op8_art="$op8_project/artifacts/linux-7.2.5-op8"
op8_base="$op8_project/configs/postmarketos-sm8250.config"
op8_fragment="$op8_project/configs/linux-7.2.5-op8.fragment"

test "$(git -C "$op8_kernel" rev-parse HEAD)" = "$OP8_LINUX_7_2_5_SNAPSHOT" || {
	echo 'Run scripts/fetch-linux-7.2.5-op8.sh first.' >&2
	exit 1
}
mkdir -p "$op8_out" "$op8_art"

KCONFIG_CONFIG="$op8_out/.config" \
	"$op8_kernel/scripts/kconfig/merge_config.sh" -m -O "$op8_out" \
	"$op8_base" "$op8_fragment"

op8_make=(make -C "$op8_kernel" "O=$op8_out" ARCH=arm64 LLVM=1 LOCALVERSION=)
"${op8_make[@]}" olddefconfig
"${op8_make[@]}" -j"$op8_jobs" Image.gz dtbs modules

op8_release=$(<"$op8_out/include/config/kernel.release")
test "$op8_release" = 7.2.5-op8-mainline
op8_modules="$op8_art/modules-root"
if [[ -d "$op8_modules/lib/modules/$op8_release" ]]; then
	find "$op8_modules/lib/modules/$op8_release" -depth -delete
fi
"${op8_make[@]}" modules_install INSTALL_MOD_PATH="$op8_modules" INSTALL_MOD_STRIP=1

install -m 0644 "$op8_out/arch/arm64/boot/Image.gz" "$op8_art/Image.gz"
install -m 0644 \
	"$op8_out/arch/arm64/boot/dts/qcom/sm8250-oneplus-instantnoodle.dtb" \
	"$op8_art/sm8250-oneplus-instantnoodle.dtb"
install -m 0644 "$op8_out/.config" "$op8_art/kernel.config"
printf '%s\n' "$op8_release" >"$op8_art/kernel.release"
sha256sum "$op8_art/Image.gz" \
	"$op8_art/sm8250-oneplus-instantnoodle.dtb" >"$op8_art/SHA256SUMS"
echo "Built $op8_release"
