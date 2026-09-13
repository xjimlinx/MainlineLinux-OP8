#!/usr/bin/env python3
"""Build an IN2010 header-v2 RAM diagnostic image; performs no phone I/O."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import struct
import subprocess

P = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--variant', choices=('diagnostic', 'storage-probe', 'arch'), default='diagnostic')
args = parser.parse_args()
variant = args.variant
dt_variant = 'storage-probe' if variant == 'arch' else variant

image = (P / 'artifacts/in2010-kernel/Image' if (P / 'artifacts/in2010-kernel/Image').exists()
         else P / 'artifacts/baseline/Image')
ramdisk = P / ('artifacts/arch-rootfs/initramfs-arch.cpio.gz' if variant == 'arch'
               else 'artifacts/diagnostic/initramfs-diagnostic.cpio.gz')
dtb = P / f'artifacts/{dt_variant}/instantnoodle-{dt_variant}.dtb'
out = P / 'artifacts/boot-images' / variant
out.mkdir(parents=True, exist_ok=True)
payload = out / 'Image.text-offset-0x80000'
padded_payload = out / 'Image.text-offset-0x80000.padded'
shim_asm = out / 'bootshim-copydown.S'
shim_obj = out / 'bootshim-copydown.o'
shim_elf = out / 'bootshim-copydown.elf'
shim_payload = out / 'Image.copydown'
boot = out / f'boot-in2010-{variant}.img'
unpacked = out / 'unpacked'

subprocess.run(['bash', str(P / 'scripts/build-diagnostic-dtb.sh'), dt_variant], check=True)
subprocess.run(['python3', str(P / 'scripts/audit-diagnostic-board.py'), '--variant', dt_variant], check=True)
raw = bytearray(image.read_bytes())
assert len(raw) >= 64 and raw[56:60] == b'ARMd'
old_text_offset = struct.unpack_from('<Q', raw, 8)[0]
image_size = struct.unpack_from('<Q', raw, 16)[0]
# image_size is the required in-memory span and may include zero-filled BSS,
# therefore it can legitimately exceed the on-disk Image length.
assert old_text_offset == 0 and 0 < image_size < 100663296
# This changes only the standard arm64 Image header load-offset hint. IN2010's
# captured working kernels use 0x80000; kernel bytes and entry code are intact.
struct.pack_into('<Q', raw, 8, 0x80000)
payload.write_bytes(raw)
# The arm64 header image_size includes the zero-filled in-memory tail.  Pad it
# explicitly so the relocated copy also zeroes that area and the embedded DTB
# can be placed safely beyond the complete Linux image span.
assert len(raw) <= image_size
padded_payload.write_bytes(raw + bytes(image_size - len(raw)))

template = (P / 'device/instantnoodle/bootshim-copydown.S.in').read_text()
assert '@LINUX_IMAGE@' in template and '@RUNTIME_DTB@' in template
shim_asm.write_text(template.replace('@LINUX_IMAGE@', str(padded_payload))
                    .replace('@RUNTIME_DTB@', str(dtb)))
clang = shutil.which('clang')
lld = shutil.which('ld.lld')
objcopy = P / 'toolchains/llvm-22.1.8/usr/bin/llvm-objcopy'
assert clang and lld and objcopy.is_file()
subprocess.run([clang, '--target=aarch64-none-elf', '-c', str(shim_asm), '-o', str(shim_obj)], check=True)
subprocess.run([lld, '--image-base=0', '-Ttext=0', '--entry=_start',
                str(shim_obj), '-o', str(shim_elf)], check=True)
subprocess.run([str(objcopy), '-O', 'binary', str(shim_elf), str(shim_payload)], check=True)
outer = shim_payload.read_bytes()
linux_at = outer.find(padded_payload.read_bytes())
runtime_dtb_at = outer.find(dtb.read_bytes(), linux_at + image_size)
assert outer[:4] != raw[:4] and outer[56:60] == b'ARMd'
assert struct.unpack_from('<Q', outer, 8)[0] == 0x80000
assert linux_at == 0x200000
assert runtime_dtb_at >= linux_at + image_size
assert len(outer) % 0x1000 == 0
assert len(outer) > runtime_dtb_at + dtb.stat().st_size

# Preserve the captured, boot-tested Lineage recovery Qualcomm DTB table and
# recovery DTBO as the ABL-facing shell.  This is not an OxygenOS/stock image;
# Linux itself receives the embedded mainline DTB above.
baseline_recovery = P / 'artifacts/device-baseline/lineage-recovery_a.img'
baseline_sha = 'd3bf874fa1c416d40c5392e31e45ae1c4b426c8b498a40d7a7c3288ef1c6b981'
assert baseline_recovery.is_file()
with baseline_recovery.open('rb') as baseline_file:
    baseline_actual_sha = hashlib.file_digest(baseline_file, 'sha256').hexdigest()
assert baseline_actual_sha == baseline_sha, 'Lineage recovery_a baseline hash changed'
abl_shell = out / 'abl-shell-lineage-recovery-a'
abl_shell.mkdir(exist_ok=True)
for child in abl_shell.iterdir():
    if child.is_file() or child.is_symlink():
        child.unlink()
subprocess.run(['unpack_bootimg', '--boot_img', str(baseline_recovery), '--out', str(abl_shell)],
               check=True, stdout=subprocess.DEVNULL)
abl_dtb = abl_shell / 'dtb'
abl_recovery_dtbo = abl_shell / 'recovery_dtbo'
assert abl_dtb.is_file() and abl_recovery_dtbo.is_file()

cmdline = (
    'androidboot.hardware=qcom androidboot.usbcontroller=a600000.dwc3 '
    f'rdinit=/init {"op8.arch=1" if variant == "arch" else "op8.diag=1"} '
    'loglevel=8 ignore_loglevel printk.devkmsg=on '
    'panic=0 oops=panic swiotlb=2048'
)
cmd = [
    'mkbootimg', '--header_version', '2', '--pagesize', '4096', '--base', '0',
    '--kernel_offset', '0x8000', '--ramdisk_offset', '0x01000000',
    '--second_offset', '0', '--tags_offset', '0x100', '--dtb_offset', '0x01f00000',
    '--os_version', '15.0.0', '--os_patch_level', '2025-07',
    '--kernel', str(shim_payload), '--ramdisk', str(ramdisk), '--dtb', str(abl_dtb),
    '--recovery_dtbo', str(abl_recovery_dtbo),
    '--cmdline', cmdline, '--output', str(boot),
]
subprocess.run(cmd, check=True)
recovery_partition_size = 104857600
subprocess.run([
    'avbtool', 'add_hash_footer', '--image', str(boot),
    '--partition_name', 'recovery', '--partition_size', str(recovery_partition_size),
    '--algorithm', 'NONE', '--salt',
    '173dd217e1466c6f0755391c4a8445934860e961886213c5ef20a135343c9680',
], check=True)
assert boot.stat().st_size == recovery_partition_size
avb_info = subprocess.check_output(['avbtool', 'info_image', '--image', str(boot)], text=True)
assert 'Partition Name:        recovery' in avb_info and 'Algorithm:                NONE' in avb_info

if unpacked.exists():
    # Only generated files inside this precise artifact directory.
    for child in unpacked.iterdir():
        if child.is_file() or child.is_symlink():
            child.unlink()
else:
    unpacked.mkdir()
shown = subprocess.check_output(
    ['unpack_bootimg', '--boot_img', str(boot), '--out', str(unpacked), '--format=mkbootimg'],
    text=True).strip()
for actual, expected in ((unpacked / 'kernel', shim_payload),
                         (unpacked / 'ramdisk', ramdisk), (unpacked / 'dtb', abl_dtb),
                         (unpacked / 'recovery_dtbo', abl_recovery_dtbo)):
    assert actual.read_bytes() == expected.read_bytes(), actual
def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()

manifest = {
    'target': 'OnePlus 8 IN2010 / instantnoodle / project19821',
    'variant': variant,
    'intent': ('boot exact-label Arch rootfs' if variant == 'arch'
               else 'RAM diagnostic; no rootfs installation'),
    'kernel_source_sha256': sha(image),
    'kernel_payload_sha256': sha(payload),
    'kernel_layout': 'copydown-shim-with-embedded-linux',
    'bootshim_source': 'device/instantnoodle/bootshim-copydown.S.in',
    'bootshim_license': 'GPL-2.0-only',
    'bootshim_payload_sha256': sha(shim_payload),
    'embedded_linux_offset': linux_at,
    'embedded_linux_padded_size': image_size,
    'runtime_dtb_offset': runtime_dtb_at,
    'runtime_dtb_outside_linux_span': runtime_dtb_at >= linux_at + image_size,
    'abl_shell_identity': 'LineageOS 22.2 recovery_a backup; not OxygenOS stock',
    'abl_shell_source_sha256': baseline_sha,
    'abl_shell_dtb_sha256': sha(abl_dtb),
    'abl_shell_recovery_dtbo_sha256': sha(abl_recovery_dtbo),
    'kernel_text_offset_original': old_text_offset,
    'kernel_text_offset_packaged': 0x80000,
    'ramdisk_sha256': sha(ramdisk), 'dtb_sha256': sha(dtb),
    'boot_image_sha256': sha(boot), 'boot_image_size': boot.stat().st_size,
    'partition_name': 'recovery',
    'partition_size': recovery_partition_size,
    'mkbootimg_parameters': cmd[1:-2],
    'unpack_bootimg_parameters': shown,
    'recovery_dtbo_included': True,
    'avb_footer_included': True,
    'avb_algorithm': 'NONE',
    'host_payload_roundtrip': 'passed',
    'phone_boot': 'NOT TESTED',
}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
(out / 'SHA256SUMS').write_text(
    f'{sha(boot)}  {boot.name}\n{sha(shim_payload)}  {shim_payload.name}\n'
    f'{sha(payload)}  {payload.name}\n')
print(f'Built {boot} ({boot.stat().st_size} bytes)')
print(f'SHA256 {sha(boot)}')
print('NOT FLASHED: phone hardware has not been tested.')
