#!/usr/bin/env python3
"""Build an Arch boot image from the exact kernel/DTB already validated on IN2010."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

P = Path(__file__).resolve().parents[1]
baseline = P / "artifacts/postmarketos-instantnoodle-6.16.7-20260913/boot.img"
source_root = P / "build/arch-initramfs/root"
work = P / "build/arch-6.16.7-initramfs"
root = work / "root"
unpacked = work / "validated-boot"
out = P / "artifacts/arch-6.16.7"
out.mkdir(parents=True, exist_ok=True)

assert baseline.is_file() and source_root.is_dir()
shutil.rmtree(root, ignore_errors=True)
shutil.rmtree(unpacked, ignore_errors=True)
shutil.copytree(source_root, root, symlinks=True)
(root / "init").write_bytes((P / "device/instantnoodle/arch-init").read_bytes())
(root / "init").chmod(0o755)
shutil.rmtree(root / "modules", ignore_errors=True)
(root / "modules").mkdir()

entries = []
for path in sorted(root.rglob("*")):
    rel = "/" + str(path.relative_to(root))
    if path.is_symlink():
        entries.append(f"slink {rel} {os.readlink(path)} 777 0 0")
    elif path.is_dir():
        entries.append(f"dir {rel} 755 0 0")
    else:
        mode = "755" if path.stat().st_mode & 0o111 else "644"
        entries.append(f"file {rel} {path} {mode} 0 0")
entries += ["nod /dev/console 600 0 0 c 5 1", "nod /dev/null 666 0 0 c 1 3"]
manifest = work / "cpio.list"
manifest.parent.mkdir(parents=True, exist_ok=True)
manifest.write_text("\n".join(entries) + "\n")
cpio = out / "initramfs-arch-6.16.7.cpio"
cpio_gz = out / "initramfs-arch-6.16.7.cpio.gz"
gen_init = P / "build/xo666-6.16.7/usr/gen_init_cpio"
with cpio.open("wb") as stream:
    subprocess.run([str(gen_init), "-t", "0", str(manifest)], stdout=stream, check=True)
with cpio_gz.open("wb") as stream:
    subprocess.run(["gzip", "-n", "-9", "-c", str(cpio)], stdout=stream, check=True)

unpacked.mkdir()
subprocess.run(["unpack_bootimg", "--boot_img", str(baseline), "--out", str(unpacked)],
               check=True, stdout=subprocess.DEVNULL)
kernel = unpacked / "kernel"
dtb = unpacked / "dtb"
assert hashlib.sha256(kernel.read_bytes()).hexdigest() == "65b472bcd79469ae409b98c0048ca1a1369ce1161694138d616c921344a682ce"
assert hashlib.sha256(dtb.read_bytes()).hexdigest() == "6f86e4bec3b244b22482d33d53edf8b0b5090718adc24951b2307c5af75dd185"

boot = out / "boot-in2010-arch-6.16.7.img"
cmdline = (
    "quiet splash clk_ignore_unused pd_ignore_unused rootwait rdinit=/init op8.arch=1 "
    "androidboot.hardware=qcom androidboot.usbcontroller=a600000.dwc3 "
    "loglevel=7 printk.devkmsg=on panic=0 swiotlb=2048"
)
subprocess.run([
    "mkbootimg", "--header_version", "2", "--pagesize", "4096", "--base", "0",
    "--kernel_offset", "0x8000", "--ramdisk_offset", "0x01000000",
    "--second_offset", "0", "--tags_offset", "0x100", "--dtb_offset", "0x01f00000",
    "--kernel", str(kernel), "--ramdisk", str(cpio_gz), "--dtb", str(dtb),
    "--cmdline", cmdline, "--output", str(boot),
], check=True)
assert boot.stat().st_size < 96 * 1024 * 1024

verify = work / "verify"
shutil.rmtree(verify, ignore_errors=True)
verify.mkdir()
shown = subprocess.check_output(
    ["unpack_bootimg", "--boot_img", str(boot), "--out", str(verify), "--format=mkbootimg"],
    text=True,
).strip()
assert (verify / "kernel").read_bytes() == kernel.read_bytes()
assert (verify / "ramdisk").read_bytes() == cpio_gz.read_bytes()
assert (verify / "dtb").read_bytes() == dtb.read_bytes()

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

record = {
    "target": "OnePlus 8 IN2010 / instantnoodle",
    "kernel_release": "6.16.7",
    "kernel_source": str(baseline.relative_to(P)),
    "kernel_sha256": sha(kernel),
    "dtb_sha256": sha(dtb),
    "ramdisk_sha256": sha(cpio_gz),
    "boot_sha256": sha(boot),
    "boot_size": boot.stat().st_size,
    "cmdline": cmdline,
    "roundtrip": "passed",
    "unpack_parameters": shown,
}
(out / "boot-manifest.json").write_text(json.dumps(record, indent=2) + "\n")
(out / "SHA256SUMS").write_text(f"{sha(boot)}  {boot.name}\n")
print(json.dumps(record, indent=2))
