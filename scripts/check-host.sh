#!/usr/bin/env bash
# Verify host-side commands needed by the documented Arch Linux build path.
set -euo pipefail

required=(
	bc blkid bsdtar bison clang cpio curl debugfs dtc e2fsck fakeroot flex
	git gpgv gzip img2simg ld.lld make mkbootimg openssl pahole python3
	sha256sum unpack_bootimg zstd
)
missing=()
for command_name in "${required[@]}"; do
	command -v "$command_name" >/dev/null 2>&1 || missing+=("$command_name")
done
project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if ! command -v qemu-aarch64-static >/dev/null 2>&1 && \
	[[ ! -x "$project/toolchains/qemu-test/usr/bin/qemu-aarch64-static" ]]; then
	missing+=(qemu-aarch64-static)
fi
if ((${#missing[@]})); then
	printf 'Missing host commands: %s\n' "${missing[*]}" >&2
	cat >&2 <<'EOF'
On Arch Linux install: base-devel bc clang llvm lld pahole python git curl
gnupg libarchive cpio zstd fakeroot dtc e2fsprogs android-tools qemu-user-static
EOF
	exit 1
fi
echo 'Host dependency check passed.'
