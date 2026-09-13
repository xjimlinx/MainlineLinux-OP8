#!/usr/bin/env bash
# ABL-facing non-EFI kernel build, kept separate from the reproducible baseline.
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
exec 8>"$op8_project/build/in2010-kernel-build.lock"
flock -n 8 || { echo 'IN2010 kernel build already running.' >&2; exit 1; }
op8_space_check
op8_jobs=${OP8_JOBS:-16}
[[ "$op8_jobs" =~ ^[1-9][0-9]*$ ]] || { echo 'Invalid OP8_JOBS' >&2; exit 2; }
op8_kernel="$op8_project/sources/linux-$OP8_KERNEL_TAG"
op8_out="$op8_project/build/in2010-kernel"
op8_art="$op8_project/artifacts/in2010-kernel"
op8_tc="$op8_project/toolchains/llvm-22.1.8/usr/bin"
export PATH="$op8_tc:$PATH"
mkdir -p "$op8_out" "$op8_art"
if [[ ! -f "$op8_out/.config" ]]; then
    cp "$op8_project/artifacts/baseline/kernel.config" "$op8_out/.config"
fi
# EFI selects EFI_STUB on arm64, so disabling EFI_STUB alone is undone by
# olddefconfig.  ABL on the IN2010 rejects the PE/COFF (MZ) Image before the
# kernel gets control; build a plain arm64 Image for this boot path.
"$op8_kernel/scripts/config" --file "$op8_out/.config" -d EFI
op8_make=(make -C "$op8_kernel" "O=$op8_out" ARCH=arm64 LLVM=1 LLVM_IAS=1)
"${op8_make[@]}" olddefconfig
"${op8_make[@]}" -j"$op8_jobs" Image modules dtbs
cp "$op8_out/arch/arm64/boot/Image" "$op8_art/Image"
cp "$op8_out/.config" "$op8_art/kernel.config"
cp "$op8_out/include/config/kernel.release" "$op8_art/kernel.release"
"${op8_make[@]}" modules_install "INSTALL_MOD_PATH=$op8_art/modules" INSTALL_MOD_STRIP=1
sha256sum "$op8_art/Image" "$op8_art/kernel.config" >"$op8_art/SHA256SUMS"
python3 - "$op8_art/Image" <<'PY'
import struct, sys
from pathlib import Path
b = Path(sys.argv[1]).read_bytes()[:64]
assert b[56:60] == b'ARMd' and b[:2] != b'MZ'
print(f'IN2010 non-EFI Image: code0=0x{struct.unpack_from("<I", b)[0]:08x}, text_offset=0x{struct.unpack_from("<Q", b, 8)[0]:x}')
PY
