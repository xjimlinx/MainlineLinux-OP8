#!/usr/bin/env python3
"""Package the reproducible OP8 Linux 7.2.5 temporary-boot image."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

P = Path(__file__).resolve().parents[1]
art = P / "artifacts/linux-7.2.5-op8"
kernel = art / "Image.gz"
dtb = art / "sm8250-oneplus-instantnoodle.dtb"
ramdisk = P / "artifacts/arch-rootfs/initramfs-arch.cpio.gz"
boot = art / "boot-in2010-linux-7.2.5.img"
for path in (kernel, dtb, ramdisk):
    if not path.is_file():
        raise SystemExit(f"missing build input: {path}")

cmdline = (
    "quiet splash clk_ignore_unused pd_ignore_unused rootwait rdinit=/init "
    "op8.arch=1 androidboot.hardware=qcom "
    "androidboot.usbcontroller=a600000.dwc3 loglevel=7 printk.devkmsg=on "
    "panic=0 swiotlb=2048"
)
subprocess.run([
    "mkbootimg", "--header_version", "2", "--pagesize", "4096", "--base", "0",
    "--kernel_offset", "0x8000", "--ramdisk_offset", "0x01000000",
    "--second_offset", "0", "--tags_offset", "0x100",
    "--dtb_offset", "0x01f00000", "--kernel", str(kernel),
    "--ramdisk", str(ramdisk), "--dtb", str(dtb), "--cmdline", cmdline,
    "--output", str(boot),
], check=True)
if boot.stat().st_size >= 96 * 1024 * 1024:
    raise SystemExit("boot image exceeds the IN2010 boot partition")

verify = P / "build/linux-7.2.5-boot-verify"
shutil.rmtree(verify, ignore_errors=True)
verify.mkdir(parents=True)
subprocess.run(["unpack_bootimg", "--boot_img", str(boot), "--out", str(verify)],
               check=True, stdout=subprocess.DEVNULL)
for name, source in (("kernel", kernel), ("dtb", dtb), ("ramdisk", ramdisk)):
    if (verify / name).read_bytes() != source.read_bytes():
        raise SystemExit(f"boot image round-trip mismatch: {name}")

sha = lambda path: hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
manifest = {
    "target": "OnePlus 8 IN2010 / instantnoodle",
    "kernel_release": "7.2.5-op8-mainline",
    "kernel_sha256": sha(kernel),
    "dtb_sha256": sha(dtb),
    "ramdisk_sha256": sha(ramdisk),
    "boot_sha256": sha(boot),
    "boot_size": boot.stat().st_size,
    "cmdline": cmdline,
    "validation": "fastboot boot only; do not flash before hardware testing",
}
(art / "boot-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
(art / "SHA256SUMS").write_text(
    f"{sha(boot)}  {boot.name}\n{sha(kernel)}  {kernel.name}\n"
    f"{sha(dtb)}  {dtb.name}\n"
)
print(json.dumps(manifest, indent=2))
