#!/usr/bin/env python3
"""Build the copy-down then PSCI-reset checkpoint; performs no phone I/O."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

P = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--stage', choices=('tail-reset', 'copy-reset'), default='copy-reset')
args = parser.parse_args()
diag = P / 'artifacts/boot-images/diagnostic'
out = P / 'artifacts/boot-images' / f'checkpoint-{args.stage}'
out.mkdir(parents=True, exist_ok=True)
template = (P / 'device/instantnoodle/bootshim-copydown.S.in').read_text()
linux = diag / 'Image.text-offset-0x80000.padded'
dtb = P / 'artifacts/diagnostic/instantnoodle-diagnostic.dtb'
asm = out / 'bootshim-copy-reset.S'
asm.write_text(template.replace('@LINUX_IMAGE@', str(linux)).replace('@RUNTIME_DTB@', str(dtb)))
obj, elf = out / f'bootshim-{args.stage}.o', out / f'bootshim-{args.stage}.elf'
kernel, boot = out / f'Image.{args.stage}', out / f'boot-in2010-{args.stage}.img'
clang, lld = shutil.which('clang'), shutil.which('ld.lld')
objcopy = P / 'toolchains/llvm-22.1.8/usr/bin/llvm-objcopy'
assert clang and lld and objcopy.is_file() and linux.is_file() and dtb.is_file()
macro = '-DOP8_TAIL_RESET' if args.stage == 'tail-reset' else '-DOP8_COPY_RESET'
subprocess.run([clang, '--target=aarch64-none-elf', macro, '-c', str(asm), '-o', str(obj)], check=True)
subprocess.run([lld, '--image-base=0', '-Ttext=0', '--entry=_start', str(obj), '-o', str(elf)], check=True)
subprocess.run([str(objcopy), '-O', 'binary', str(elf), str(kernel)], check=True)
shell = diag / 'abl-shell-lineage-recovery-a'
subprocess.run([
    'mkbootimg', '--header_version', '2', '--pagesize', '4096', '--base', '0',
    '--kernel_offset', '0x8000', '--ramdisk_offset', '0x01000000',
    '--second_offset', '0', '--tags_offset', '0x100', '--dtb_offset', '0x01f00000',
    '--os_version', '15.0.0', '--os_patch_level', '2025-07', '--kernel', str(kernel),
    '--ramdisk', str(shell / 'ramdisk'), '--dtb', str(shell / 'dtb'),
    '--recovery_dtbo', str(shell / 'recovery_dtbo'),
    '--cmdline', f'androidboot.hardware=qcom panic=0 op8.checkpoint={args.stage}', '--output', str(boot),
], check=True)
subprocess.run([
    'avbtool', 'add_hash_footer', '--image', str(boot), '--partition_name', 'recovery',
    '--partition_size', '104857600', '--algorithm', 'NONE', '--salt',
    '173dd217e1466c6f0755391c4a8445934860e961886213c5ef20a135343c9680',
], check=True)
with boot.open('rb') as f:
    digest = hashlib.file_digest(f, 'sha256').hexdigest()
manifest = {'target': 'OnePlus 8 IN2010 / instantnoodle / project19821',
            'stage': ('dispatch to tail, then PSCI reset' if args.stage == 'tail-reset'
                      else 'copy padded Linux Image, clean caches, then PSCI reset'),
            'boot_image_size': boot.stat().st_size, 'boot_image_sha256': digest,
            'phone_test': 'NOT TESTED'}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest, indent=2))
