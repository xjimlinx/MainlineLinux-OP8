#!/usr/bin/env bash
# Build a sparse ext4 Arch Linux ARM filesystem. Does not touch a phone.
set -euo pipefail
source "$(dirname -- "$0")/common.sh"
op8_space_check 12884901888
op8_archive="$op8_project/downloads/ArchLinuxARM-aarch64-latest.tar.gz"
op8_expected=$OP8_ROOTFS_SHA256
printf '%s  %s\n' "$op8_expected" "$op8_archive" | sha256sum --check --status
op8_out="$op8_project/artifacts/arch-rootfs"
mkdir -p "$op8_out" "$op8_project/build"
op8_assets="$op8_project/sources/github-references/linux-oneplus-instantnoodle"
op8_firmware="$op8_assets/firmware-oneplus-instantnoodle/usr/lib/firmware"
op8_alsa="$op8_assets/alsa-oneplus-instantnoodle/usr/share/alsa"
[[ -d "$op8_firmware" && -d "$op8_alsa" ]] || {
    echo 'Run scripts/fetch-device-assets.sh first.' >&2
    exit 1
}
test "$(git -C "$op8_assets" rev-parse HEAD)" = "$OP8_DEVICE_ASSETS_COMMIT"
op8_work=$(mktemp -d "$op8_project/build/arch-rootfs.XXXXXX")
op8_cleanup() { chmod -R u+w "$op8_work" 2>/dev/null || true; find "$op8_work" -depth -delete 2>/dev/null || true; }
trap op8_cleanup EXIT
op8_password=$(openssl rand -hex 12)
op8_hash=$(openssl passwd -6 "$op8_password")
op8_kernel_art="$op8_project/artifacts/linux-7.2.5-op8"
if [[ -s "$op8_kernel_art/kernel.release" ]]; then
    op8_module_dir="$op8_kernel_art/modules-root/lib/modules"
else
    op8_kernel_art="$op8_project/artifacts/in2010-kernel"
    [[ -s "$op8_kernel_art/Image" ]] || op8_kernel_art="$op8_project/artifacts/baseline"
    op8_module_dir="$op8_kernel_art/modules/lib/modules"
fi
op8_raw="$op8_out/archlinux-in2010-rootfs.ext4"
op8_sparse="$op8_out/archlinux-in2010-rootfs.sparse.img"

env OP8_ARCHIVE="$op8_archive" OP8_WORK="$op8_work" OP8_HASH="$op8_hash" \
    OP8_OVERLAY="$op8_project/device/instantnoodle/rootfs-overlay" \
    OP8_MODULES="$op8_module_dir" \
    OP8_FIRMWARE="$op8_firmware" OP8_ALSA="$op8_alsa" \
    OP8_RAW="$op8_raw" fakeroot -- bash -euo pipefail -c '
root="$OP8_WORK/root"
mkdir -p "$root"
bsdtar --numeric-owner -xpf "$OP8_ARCHIVE" -C "$root"
cp -a "$OP8_OVERLAY/." "$root/"
chmod 0755 "$root/usr/local/sbin/op8-grow-root"
printf "root:%s\n" "$OP8_HASH" | chpasswd -e -P "$root"
usermod -P "$root" -L alarm
chmod 0600 "$root/etc/shadow"
mkdir -p "$root/usr/lib/modules" "$root/etc/systemd/system/getty.target.wants" \
         "$root/etc/systemd/system/multi-user.target.wants"
cp -a "$OP8_MODULES/." "$root/usr/lib/modules/"
find "$root/usr/lib/modules" -type l -delete
rm -rf "$root/usr/lib/firmware"
install -d "$root/usr/lib/firmware"
cp -a "$OP8_FIRMWARE/." "$root/usr/lib/firmware/"
# The current DT requests the shorter OnePlus/ path; keep upstream OnePlus8/ too.
install -d "$root/usr/lib/firmware/qcom/sm8250/OnePlus"
cp -a "$OP8_FIRMWARE/qcom/sm8250/OnePlus8/." \
    "$root/usr/lib/firmware/qcom/sm8250/OnePlus/"
install -d "$root/usr/share/alsa"
cp -a "$OP8_ALSA/." "$root/usr/share/alsa/"
ln -sf /usr/lib/systemd/system/serial-getty@.service \
    "$root/etc/systemd/system/getty.target.wants/serial-getty@ttyGS0.service"
ln -sf ../op8-grow-root.service \
    "$root/etc/systemd/system/multi-user.target.wants/op8-grow-root.service"
rm -f "$root/etc/systemd/system/network-online.target.wants/systemd-networkd-wait-online.service"
chmod u+w "$root/etc/machine-id"
: >"$root/etc/machine-id"
chmod 0444 "$root/etc/machine-id"
truncate -s 6G "$OP8_RAW"
mke2fs -q -F -t ext4 -b 4096 -m 0 -L arch-root \
    -E root_owner=0:0,lazy_itable_init=0,lazy_journal_init=0 \
    -d "$root" "$OP8_RAW"
'
img2simg "$op8_raw" "$op8_sparse"
e2fsck -fn "$op8_raw"
test "$(blkid -s LABEL -o value "$op8_raw")" = arch-root
op8_raw_sha=$(sha256sum "$op8_raw" | awk '{print $1}')
op8_sparse_sha=$(sha256sum "$op8_sparse" | awk '{print $1}')
printf '%s\n' "$op8_password" >"$op8_out/INITIAL-ROOT-PASSWORD.txt"
chmod 0600 "$op8_out/INITIAL-ROOT-PASSWORD.txt"
{
    printf 'target=OnePlus 8 IN2010 / instantnoodle\n'
    printf 'filesystem_label=arch-root\n'
    printf 'raw_size=%s\n' "$(stat -c %s "$op8_raw")"
    printf 'raw_sha256=%s\n' "$op8_raw_sha"
    printf 'sparse_size=%s\n' "$(stat -c %s "$op8_sparse")"
    printf 'sparse_sha256=%s\n' "$op8_sparse_sha"
    printf 'source_archive_sha256=%s\n' "$op8_expected"
    printf 'device_assets_commit=%s\n' "$OP8_DEVICE_ASSETS_COMMIT"
    printf 'kernel_release=%s\n' "$(<"$op8_kernel_art/kernel.release")"
    printf 'initial_login=root (password stored mode 0600 beside image)\n'
    printf 'alarm_account=locked\n'
    printf 'phone_flash=NOT PERFORMED\n'
} >"$op8_out/rootfs.manifest"
printf '%s  %s\n' "$op8_sparse_sha" "$(basename "$op8_sparse")" >"$op8_out/SHA256SUMS"
echo "Built $op8_sparse"
echo 'Initial root password is stored locally with mode 0600; change it after first login.'
