#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
	echo "run through pkexec" >&2
	exit 1
fi

project=/Work/Data/OnePlus8/MainlineLinux-OP8
export http_proxy=http://127.0.0.1:10808
export https_proxy=http://127.0.0.1:10808
export HTTP_PROXY=$http_proxy
export HTTPS_PROXY=$https_proxy
image="$project/artifacts/arch-6.16.7/archlinux-in2010-6.16.7.ext4"
kernel_apk="$project/build/pmbootstrap/packages/edge/aarch64/linux-oneplus-instantnoodle-6.16.7_p20260913153737-r2.apk"
firmware="$project/sources/github-references/linux-oneplus-instantnoodle/firmware-oneplus-instantnoodle/usr/lib/firmware"
overlay="$project/device/instantnoodle/rootfs-overlay"
qemu="$project/toolchains/qemu-test/usr/bin/qemu-aarch64-static"
mountpoint="$project/build/arch-6.16.7-mnt"

for path in "$image" "$kernel_apk" "$firmware" "$overlay" "$qemu"; do
	[[ -e $path ]] || { echo "missing required input: $path" >&2; exit 1; }
done
mkdir -p "$mountpoint"
mountpoint -q "$mountpoint" && { echo "refusing already-mounted target: $mountpoint" >&2; exit 1; }

loopdev=$(losetup --find --show "$image")
cleanup() {
	set +e
	for procroot in /proc/[0-9]*/root; do
		root_target=$(readlink "$procroot" 2>/dev/null || true)
		case "$root_target" in
			"$mountpoint"*) pid=${procroot#/proc/}; kill "${pid%/root}" 2>/dev/null || true ;;
		esac
	done
	# Reap chrooted gpg-agent processes before detaching the filesystem.  A
	# lazy unmount here can leave a writable namespace alive and corrupt the
	# image while fsck or sparse conversion starts.
	for _ in 1 2 3 4 5; do
		busy=0
		for procroot in /proc/[0-9]*/root; do
			root_target=$(readlink "$procroot" 2>/dev/null || true)
			case "$root_target" in "$mountpoint"*) busy=1;; esac
		done
		[[ $busy -eq 0 ]] && break
		sleep 1
	done
	sync
	findmnt -R -n -o TARGET "$mountpoint" 2>/dev/null | tac | \
		while IFS= read -r target; do umount "$target" 2>/dev/null || true; done
	losetup -d "$loopdev" 2>/dev/null || true
}
trap cleanup EXIT
mount "$loopdev" "$mountpoint"
# The workspace resides below a shared host mount.  Make this staging mount
# private so service mount namespaces cannot retain writable clones of it.
mount --make-private "$mountpoint"
[[ -f "$mountpoint/etc/arch-release" ]] || { echo "target is not an Arch rootfs" >&2; exit 1; }

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
chroot "$mountpoint" /usr/bin/qemu-aarch64-static /bin/bash /usr/bin/pacman-key --init
chroot "$mountpoint" /usr/bin/qemu-aarch64-static /bin/bash /usr/bin/pacman-key --populate archlinux archlinuxarm
chroot "$mountpoint" /usr/bin/qemu-aarch64-static /usr/bin/pacman --disable-sandbox \
	-Syu --noconfirm --needed \
	mesa mesa-utils plasma-mobile plasma-settings kscreen bluedevil \
	noto-fonts-cjk greetd networkmanager sudo \
	firefox firefox-i18n-zh-cn konsole pipewire-audio pipewire-pulse wireplumber plasma-pa \
	alsa-utils rtkit

# Install the exact module tree matching the already boot-tested phone kernel.
module_tmp=$(mktemp -d "$project/build/arch-kernel-apk.XXXXXX")
bsdtar --numeric-owner -xpf "$kernel_apk" -C "$module_tmp"
[[ -d "$module_tmp/lib/modules/6.16.7" ]] || { echo "kernel APK has no 6.16.7 modules" >&2; exit 1; }
rm -rf "$mountpoint/usr/lib/modules"
install -d "$mountpoint/usr/lib/modules"
cp -a "$module_tmp/lib/modules/6.16.7" "$mountpoint/usr/lib/modules/"
rm -rf "$module_tmp"

# Install all extracted device firmware and correct the upstream OnePlus8/
# directory mismatch expected by the current device tree (OnePlus/).
install -d "$mountpoint/usr/lib/firmware"
cp -a "$firmware/." "$mountpoint/usr/lib/firmware/"
install -d "$mountpoint/usr/lib/firmware/qcom/sm8250/OnePlus"
cp -a "$firmware/qcom/sm8250/OnePlus8/." \
	"$mountpoint/usr/lib/firmware/qcom/sm8250/OnePlus/"

cp -a "$overlay/." "$mountpoint/"
# Source files are maintained by the host user, but every overlay node is a
# system path in the target.  Do not leak the host UID into /, /etc or /usr.
while IFS= read -r -d '' source; do
	relative=${source#"$overlay"/}
	[[ $source != "$overlay" ]] || relative=.
	chown root:root "$mountpoint/$relative"
done < <(find "$overlay" -print0)
chmod 0755 "$mountpoint"
chmod 0600 "$mountpoint/etc/NetworkManager/system-connections/usb0.nmconnection"
chmod 0755 "$mountpoint/usr/local/sbin/op8-grow-root"

if ! chroot "$mountpoint" /usr/bin/qemu-aarch64-static /usr/bin/id xein >/dev/null 2>&1; then
	chroot "$mountpoint" /usr/bin/qemu-aarch64-static /usr/bin/useradd -m -s /bin/bash xein
fi
for group in wheel video input render audio; do
	chroot "$mountpoint" /usr/bin/qemu-aarch64-static /usr/bin/getent group "$group" >/dev/null 2>&1 && \
		chroot "$mountpoint" /usr/bin/qemu-aarch64-static /usr/bin/usermod -aG "$group" xein
done
printf 'xein:123456\n' | chroot "$mountpoint" /usr/bin/qemu-aarch64-static /usr/bin/chpasswd
install -Dm440 "$overlay/etc/sudoers.d/10-wheel" "$mountpoint/etc/sudoers.d/10-wheel"
xein_uid=$(chroot "$mountpoint" /usr/bin/qemu-aarch64-static /usr/bin/id -u xein)
xein_gid=$(chroot "$mountpoint" /usr/bin/qemu-aarch64-static /usr/bin/id -g xein)
install -d -o "$xein_uid" -g "$xein_gid" "$mountpoint/home/xein/.config"
printf '[Formats]\nLANG=zh_CN.UTF-8\n' >"$mountpoint/home/xein/.config/plasma-localerc"
chown "$xein_uid:$xein_gid" "$mountpoint/home/xein/.config/plasma-localerc"

sed -i 's/^#zh_CN.UTF-8 UTF-8/zh_CN.UTF-8 UTF-8/' "$mountpoint/etc/locale.gen"
chroot "$mountpoint" /usr/bin/qemu-aarch64-static /usr/bin/locale-gen

chroot "$mountpoint" /usr/bin/qemu-aarch64-static /usr/bin/systemctl enable \
	NetworkManager systemd-resolved sshd greetd bluetooth ModemManager upower
chroot "$mountpoint" /usr/bin/qemu-aarch64-static /usr/bin/systemctl set-default graphical.target
ln -sfn ../run/systemd/resolve/stub-resolv.conf "$mountpoint/etc/resolv.conf"
rm -f "$mountpoint/usr/bin/qemu-aarch64-static"
sync
