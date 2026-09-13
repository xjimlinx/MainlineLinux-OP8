#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
	echo "run through pkexec" >&2
	exit 1
fi

project=/Work/Data/OnePlus8/MainlineLinux-OP8
image="$project/artifacts/arch-6.16.7/archlinux-in2010-6.16.7.ext4"
firmware="$project/sources/github-references/linux-oneplus-instantnoodle/firmware-oneplus-instantnoodle/usr/lib/firmware"
mountpoint="$project/build/arch-finalize-mnt"

[[ -f $image ]] || { echo "missing image: $image" >&2; exit 1; }
[[ -d $firmware ]] || { echo "missing firmware: $firmware" >&2; exit 1; }
mkdir -p "$mountpoint"
mountpoint -q "$mountpoint" && { echo "target is already mounted" >&2; exit 1; }

loopdev=$(losetup --find --show "$image")
cleanup() {
	set +e
	sync
	if mountpoint -q "$mountpoint"; then
		umount "$mountpoint"
	fi
	losetup -d "$loopdev" 2>/dev/null || true
}
trap cleanup EXIT
mount "$loopdev" "$mountpoint"
mount --make-private "$mountpoint"
[[ -f "$mountpoint/etc/arch-release" ]] || { echo "not an Arch rootfs" >&2; exit 1; }

# Android's boot partition supplies the exact 6.16.7 kernel and initramfs.
# Remove the unused generic kernel artifacts and the package download cache.
rm -rf "$mountpoint/boot/"* "$mountpoint/var/cache/pacman/pkg/"* \
	"$mountpoint/var/lib/pacman/sync/"*

# The generic firmware meta-package consumes several GiB and is not useful on
# this phone.  Keep only firmware extracted for instantnoodle, including Wi-Fi,
# modem/DSP, Venus and Adreno blobs.
rm -rf "$mountpoint/usr/lib/firmware"
install -d "$mountpoint/usr/lib/firmware"
cp -a "$firmware/." "$mountpoint/usr/lib/firmware/"
install -d "$mountpoint/usr/lib/firmware/qcom/sm8250/OnePlus"
cp -a "$firmware/qcom/sm8250/OnePlus8/." \
	"$mountpoint/usr/lib/firmware/qcom/sm8250/OnePlus/"
chown -R root:root "$mountpoint/usr/lib/firmware"

# Avoid reinstalling the unused generic kernel/firmware during routine -Syu.
if ! grep -q '^IgnorePkg = linux-aarch64 ' "$mountpoint/etc/pacman.conf"; then
	sed -i '/^#IgnorePkg/a IgnorePkg = linux-aarch64 linux-firmware linux-firmware-amd linux-firmware-amdgpu linux-firmware-atheros linux-firmware-broadcom linux-firmware-cirrus linux-firmware-intel linux-firmware-mediatek linux-firmware-nvidia linux-firmware-other linux-firmware-radeon linux-firmware-realtek linux-firmware-ti' "$mountpoint/etc/pacman.conf"
fi

# Grow the 6 GiB staging filesystem to the full userdata partition on first boot.
install -d "$mountpoint/etc/systemd/system/multi-user.target.wants"
ln -sfn ../op8-grow-root.service \
	"$mountpoint/etc/systemd/system/multi-user.target.wants/op8-grow-root.service"

rm -f "$mountpoint/etc/ssh/ssh_host_"*
: >"$mountpoint/etc/machine-id"
sync
umount "$mountpoint"
losetup -d "$loopdev"
trap - EXIT
