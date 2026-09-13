#!/usr/bin/env bash
# Install the graphical userspace into the locally generated rootfs image.
# This mounts only an image file in this project; it never accesses a phone.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
	echo "run through pkexec: pkexec bash $(realpath "$0")" >&2
	exit 1
fi
source "$(dirname -- "$0")/common.sh"

image="$op8_project/artifacts/arch-rootfs/archlinux-in2010-rootfs.ext4"
sparse="$op8_project/artifacts/arch-rootfs/archlinux-in2010-rootfs.sparse.img"
overlay="$op8_project/device/instantnoodle/rootfs-overlay"
assets="$op8_project/sources/github-references/linux-oneplus-instantnoodle"
firmware="$assets/firmware-oneplus-instantnoodle/usr/lib/firmware"
qemu="$op8_project/toolchains/qemu-test/usr/bin/qemu-aarch64-static"
mountpoint="$op8_project/build/arch-rootfs-mnt"
release_file="$op8_project/artifacts/linux-7.2.5-op8/kernel.release"

for path in "$image" "$overlay" "$firmware" "$qemu" "$release_file"; do
	[[ -e $path ]] || { echo "missing required input: $path" >&2; exit 1; }
done
release=$(<"$release_file")
[[ $release = 7.2.5-op8-mainline ]]
mkdir -p "$mountpoint"
mountpoint -q "$mountpoint" && { echo "refusing already-mounted target: $mountpoint" >&2; exit 1; }

loopdev=$(losetup --find --show "$image")
stop_chroot_processes() {
	for procroot in /proc/[0-9]*/root; do
		root_target=$(readlink "$procroot" 2>/dev/null || true)
		case "$root_target" in "$mountpoint"*) pid=${procroot#/proc/}; kill "${pid%/root}" 2>/dev/null || true;; esac
	done
	for _ in 1 2 3 4 5; do
		busy=0
		for procroot in /proc/[0-9]*/root; do
			root_target=$(readlink "$procroot" 2>/dev/null || true)
			case "$root_target" in "$mountpoint"*) busy=1;; esac
		done
		((busy == 0)) && return
		sleep 1
	done
}
cleanup() {
	set +e
	stop_chroot_processes
	sync
	findmnt -Rrn -o TARGET "$mountpoint" 2>/dev/null | tac | \
		while IFS= read -r target; do umount "$target" 2>/dev/null || true; done
	losetup -d "$loopdev" 2>/dev/null || true
}
trap cleanup EXIT
mount "$loopdev" "$mountpoint"
mount --make-private "$mountpoint"
[[ -f "$mountpoint/etc/arch-release" ]]
[[ -d "$mountpoint/usr/lib/modules/$release" ]]
[[ -s "$mountpoint/usr/lib/firmware/qcom/sm8250/OnePlus/a650_zap.mbn" ]]

install -Dm755 "$qemu" "$mountpoint/usr/bin/qemu-aarch64-static"
mount -t proc proc "$mountpoint/proc"
mount --bind /sys "$mountpoint/sys"
mount --bind /dev "$mountpoint/dev"
mount --bind /run "$mountpoint/run"
mount --make-rslave "$mountpoint/sys"
mount --make-rslave "$mountpoint/dev"
mount --make-rslave "$mountpoint/run"
rm -f "$mountpoint/etc/resolv.conf"
cp -L /etc/resolv.conf "$mountpoint/etc/resolv.conf"

op8_chroot=(chroot "$mountpoint" /usr/bin/qemu-aarch64-static)
# qemu-user executes AArch64 ELF files; interpreter scripts must be passed to
# an AArch64 shell explicitly when binfmt_misc is not configured on the host.
"${op8_chroot[@]}" /bin/bash /usr/bin/pacman-key --init
"${op8_chroot[@]}" /bin/bash /usr/bin/pacman-key --populate archlinux archlinuxarm
# The generic kernel and multi-platform firmware from the base archive are not
# used on this phone. Remove their package records before -Syu so pacman does
# not download several GiB or overwrite the pinned OP8 modules/firmware.
generic_packages=(linux-aarch64 linux-firmware linux-firmware-amdgpu linux-firmware-atheros
	linux-firmware-broadcom linux-firmware-cirrus linux-firmware-intel
	linux-firmware-mediatek linux-firmware-nvidia linux-firmware-other
	linux-firmware-radeon linux-firmware-realtek linux-firmware-whence)
installed_generic=()
for package in "${generic_packages[@]}"; do
	"${op8_chroot[@]}" /usr/bin/pacman -Q "$package" >/dev/null 2>&1 && installed_generic+=("$package")
done
if ((${#installed_generic[@]})); then
	"${op8_chroot[@]}" /usr/bin/pacman -Rdd --noconfirm "${installed_generic[@]}"
fi
"${op8_chroot[@]}" /usr/bin/pacman --disable-sandbox -Syu --noconfirm --needed \
	mesa mesa-utils plasma-mobile plasma-settings kscreen bluedevil \
	noto-fonts-cjk greetd networkmanager sudo openssh \
	firefox firefox-i18n-zh-cn konsole pipewire-audio pipewire-pulse \
	wireplumber plasma-pa alsa-utils rtkit modemmanager upower bluez

# Package removal above intentionally clears generic firmware. Restore the
# exact pinned device set and its DT-compatible path alias afterward.
rm -rf "$mountpoint/usr/lib/firmware"
install -d "$mountpoint/usr/lib/firmware/qcom/sm8250/OnePlus"
cp -a "$firmware/." "$mountpoint/usr/lib/firmware/"
cp -a "$firmware/qcom/sm8250/OnePlus8/." \
	"$mountpoint/usr/lib/firmware/qcom/sm8250/OnePlus/"
cp -a "$overlay/." "$mountpoint/"
chown -R root:root "$mountpoint/etc" "$mountpoint/usr/local" "$mountpoint/usr/share/alsa/ucm2/OnePlus"
chmod 0600 "$mountpoint/etc/NetworkManager/system-connections/usb0.nmconnection"
chmod 0755 "$mountpoint/usr/local/sbin/op8-grow-root"

user_name=${OP8_USER:-xein}
if ! "${op8_chroot[@]}" /usr/bin/id "$user_name" >/dev/null 2>&1; then
	"${op8_chroot[@]}" /usr/bin/useradd -m -s /bin/bash "$user_name"
fi
for group in wheel video input render audio; do
	"${op8_chroot[@]}" /usr/bin/getent group "$group" >/dev/null 2>&1 && \
		"${op8_chroot[@]}" /usr/bin/usermod -aG "$group" "$user_name"
done
user_password=$(openssl rand -hex 8)
printf '%s:%s\n' "$user_name" "$user_password" | "${op8_chroot[@]}" /usr/bin/chpasswd
password_file="$op8_project/artifacts/arch-rootfs/INITIAL-USER-PASSWORD.txt"
printf '%s:%s\n' "$user_name" "$user_password" >"$password_file"
chmod 0600 "$password_file"
caller_uid=${PKEXEC_UID:-${SUDO_UID:-0}}
[[ $caller_uid =~ ^[0-9]+$ ]]
caller_gid=$(getent passwd "$caller_uid" | cut -d: -f4)
chown "$caller_uid:$caller_gid" "$password_file"
packages_file="$op8_project/artifacts/arch-rootfs/packages.lock"
"${op8_chroot[@]}" /usr/bin/pacman -Q >"$packages_file"

sed -i 's/^#zh_CN.UTF-8 UTF-8/zh_CN.UTF-8 UTF-8/' "$mountpoint/etc/locale.gen"
"${op8_chroot[@]}" /bin/bash /usr/bin/locale-gen
"${op8_chroot[@]}" /usr/bin/systemctl enable \
	NetworkManager systemd-resolved sshd greetd bluetooth ModemManager upower
"${op8_chroot[@]}" /usr/bin/systemctl set-default graphical.target
ln -sfn ../run/systemd/resolve/stub-resolv.conf "$mountpoint/etc/resolv.conf"
rm -f "$mountpoint/usr/bin/qemu-aarch64-static"

stop_chroot_processes
sync
findmnt -Rrn -o TARGET "$mountpoint" | tac | while IFS= read -r target; do umount "$target"; done
losetup -d "$loopdev"
trap - EXIT
e2fsck -fy "$image"
img2simg "$image" "$sparse"
raw_sha=$(sha256sum "$image" | awk '{print $1}')
sparse_sha=$(sha256sum "$sparse" | awk '{print $1}')
packages_sha=$(sha256sum "$packages_file" | awk '{print $1}')
{
	printf 'target=OnePlus 8 IN2010 / instantnoodle\n'
	printf 'kernel_release=%s\n' "$release"
	printf 'device_assets_commit=%s\n' "$OP8_DEVICE_ASSETS_COMMIT"
	printf 'raw_sha256=%s\n' "$raw_sha"
	printf 'sparse_sha256=%s\n' "$sparse_sha"
	printf 'packages_lock_sha256=%s\n' "$packages_sha"
} >"$op8_project/artifacts/arch-rootfs/provision.manifest"
printf '%s  %s\n%s  %s\n' "$raw_sha" "$(basename "$image")" \
	"$sparse_sha" "$(basename "$sparse")" \
	>"$op8_project/artifacts/arch-rootfs/SHA256SUMS"
echo "Provisioned Plasma Mobile rootfs for $release"
echo "Initial graphical login is stored in $password_file (mode 0600)."
