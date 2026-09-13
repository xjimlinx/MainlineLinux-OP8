#!/usr/bin/env python3
"""Build a recovery-container ABL handoff checkpoint; performs no phone I/O."""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import subprocess

P = Path(__file__).resolve().parents[1]
source = P / 'device/instantnoodle/bootshim-entry-reset.S'
baseline = P / 'artifacts/device-baseline/lineage-recovery_a.img'
baseline_sha = 'd3bf874fa1c416d40c5392e31e45ae1c4b426c8b498a40d7a7c3288ef1c6b981'
out = P / 'artifacts/boot-images/checkpoint-entry-reset'
out.mkdir(parents=True, exist_ok=True)

with baseline.open('rb') as f:
    assert hashlib.file_digest(f, 'sha256').hexdigest() == baseline_sha
shell = out / 'abl-shell'
shell.mkdir(exist_ok=True)
for child in shell.iterdir():
    if child.is_file() or child.is_symlink():
        child.unlink()
subprocess.run(['unpack_bootimg', '--boot_img', str(baseline), '--out', str(shell)],
               check=True, stdout=subprocess.DEVNULL)

obj = out / 'bootshim-entry-reset.o'
elf = out / 'bootshim-entry-reset.elf'
kernel = out / 'Image.entry-reset'
boot = out / 'boot-in2010-entry-reset.img'
clang = shutil.which('clang')
lld = shutil.which('ld.lld')
objcopy = P / 'toolchains/llvm-22.1.8/usr/bin/llvm-objcopy'
assert clang and lld and objcopy.is_file()
subprocess.run([clang, '--target=aarch64-none-elf', '-c', str(source), '-o', str(obj)], check=True)
subprocess.run([lld, '--image-base=0', '-Ttext=0', '--entry=_start', str(obj), '-o', str(elf)], check=True)
subprocess.run([str(objcopy), '-O', 'binary', str(elf), str(kernel)], check=True)
header = kernel.read_bytes()[:64]
assert len(kernel.read_bytes()) == 4096 and header[56:60] == b'ARMd'
assert struct.unpack_from('<Q', header, 8)[0] == 0x80000

cmdline = 'androidboot.hardware=qcom panic=0 op8.checkpoint=entry-reset'
subprocess.run([
    'mkbootimg', '--header_version', '2', '--pagesize', '4096', '--base', '0',
    '--kernel_offset', '0x8000', '--ramdisk_offset', '0x01000000',
    '--second_offset', '0', '--tags_offset', '0x100', '--dtb_offset', '0x01f00000',
    '--os_version', '15.0.0', '--os_patch_level', '2025-07',
    '--kernel', str(kernel), '--ramdisk', str(shell / 'ramdisk'),
    '--dtb', str(shell / 'dtb'), '--recovery_dtbo', str(shell / 'recovery_dtbo'),
    '--cmdline', cmdline, '--output', str(boot),
], check=True)
subprocess.run([
    'avbtool', 'add_hash_footer', '--image', str(boot), '--partition_name', 'recovery',
    '--partition_size', '104857600', '--algorithm', 'NONE', '--salt',
    '173dd217e1466c6f0755391c4a8445934860e961886213c5ef20a135343c9680',
], check=True)
with boot.open('rb') as f:
    digest = hashlib.file_digest(f, 'sha256').hexdigest()
manifest = {
    'target': 'OnePlus 8 IN2010 / instantnoodle / project19821',
    'stage': 'ABL entry -> PSCI reset; no Linux entry and no partition writes',
    'baseline': 'LineageOS recovery_a; not OxygenOS stock',
    'baseline_sha256': baseline_sha,
    'boot_image_size': boot.stat().st_size,
    'boot_image_sha256': digest,
    'avb_partition_name': 'recovery',
    'avb_algorithm': 'NONE',
    'phone_test': 'NOT TESTED',
}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
