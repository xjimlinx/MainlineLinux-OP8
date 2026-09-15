#!/usr/bin/env python3
"""Build a persistent OP8 boot image with only SLPI disabled.

This is a cold-boot isolation image, not a generic recovery image.  It keeps
the normal instantnoodle DTB (UFS/display/USB/ADSP/Wi-Fi) and changes only the
SLPI remoteproc node before packaging the existing Arch initramfs.
"""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

P = Path(__file__).resolve().parents[1]
kernel_tree = P / "sources/linux-sm8250-7.2.5-op8"
kernel_art = P / "artifacts/linux-7.2.5-op8"
rootfs_art = P / "artifacts/arch-rootfs"
build = P / "build/noslpi-boot"
out = P / "artifacts/boot-images/noslpi"
preprocessed = build / "instantnoodle-noslpi.pre.dts"
dtb = out / "instantnoodle-noslpi.dtb"
boot = out / "boot-in2010-noslpi.img"
persistent = out / "boot-in2010-noslpi-avb.img"

for path in (kernel_tree / "arch/arm64/boot/dts/qcom/sm8250-oneplus-instantnoodle.dts",
             kernel_art / "Image.gz", rootfs_art / "initramfs-arch.cpio.gz",
             P / "device/instantnoodle/sm8250-oneplus-instantnoodle-noslpi.dts"):
    if not path.is_file():
        raise SystemExit(f"missing build input: {path}")

clang = shutil.which("clang")
dtc = P / "build/kernel/scripts/dtc/dtc"
for tool in (clang, dtc, shutil.which("mkbootimg"), shutil.which("avbtool"),
             shutil.which("unpack_bootimg")):
    if not tool or not Path(tool).exists():
        raise SystemExit(f"missing host tool: {tool}")

build.mkdir(parents=True, exist_ok=True)
out.mkdir(parents=True, exist_ok=True)
subprocess.run([
    clang, "-E", "-P", "-x", "assembler-with-cpp", "-nostdinc", "-undef",
    "-D__DTS__", "-I", str(kernel_tree / "include"),
    "-I", str(kernel_tree / "arch/arm64/boot/dts/qcom"),
    str(P / "device/instantnoodle/sm8250-oneplus-instantnoodle-noslpi.dts"),
    "-o", str(preprocessed),
], check=True)
subprocess.run([str(dtc), "-@", "-I", "dts", "-O", "dtb", "-o", str(dtb),
                str(preprocessed)], check=True)

def fdtget(*args):
    return subprocess.check_output(["fdtget", "-t", "s", str(dtb), *args], text=True).strip()

slpi_path = fdtget("/__symbols__", "slpi")
if fdtget(slpi_path, "status") != "disabled":
    raise SystemExit("noslpi DTB did not disable the SLPI remoteproc")
pcie2_path = fdtget("/__symbols__", "pcie2")
if fdtget(pcie2_path, "status") != "disabled":
    raise SystemExit("noslpi DTB unexpectedly enabled modem PCIe")

cmdline = (
    "quiet splash clk_ignore_unused pd_ignore_unused rootwait rdinit=/init "
    "op8.arch=1 androidboot.hardware=qcom "
    "androidboot.usbcontroller=a600000.dwc3 loglevel=8 "
    "ignore_loglevel printk.devkmsg=on panic=0 swiotlb=2048"
)
subprocess.run([
    "mkbootimg", "--header_version", "2", "--pagesize", "4096", "--base", "0",
    "--kernel_offset", "0x8000", "--ramdisk_offset", "0x01000000",
    "--second_offset", "0", "--tags_offset", "0x100", "--dtb_offset", "0x01f00000",
    "--kernel", str(kernel_art / "Image.gz"),
    "--ramdisk", str(rootfs_art / "initramfs-arch.cpio.gz"), "--dtb", str(dtb),
    "--cmdline", cmdline, "--output", str(boot),
], check=True)
if boot.stat().st_size >= 96 * 1024 * 1024:
    raise SystemExit("noslpi boot image exceeds the IN2010 boot partition")

verify = build / "unpacked"
shutil.rmtree(verify, ignore_errors=True)
verify.mkdir(parents=True)
subprocess.run(["unpack_bootimg", "--boot_img", str(boot), "--out", str(verify)],
               check=True, stdout=subprocess.DEVNULL)
for name, source in (("kernel", kernel_art / "Image.gz"),
                     ("ramdisk", rootfs_art / "initramfs-arch.cpio.gz"),
                     ("dtb", dtb)):
    if (verify / name).read_bytes() != source.read_bytes():
        raise SystemExit(f"boot image round-trip mismatch: {name}")

shutil.copyfile(boot, persistent)
salt = hashlib.sha256(boot.read_bytes()).hexdigest()
subprocess.run([
    "avbtool", "add_hash_footer", "--image", str(persistent),
    "--partition_name", "boot", "--partition_size", str(96 * 1024 * 1024),
    "--algorithm", "NONE", "--salt", salt,
], check=True, stdout=subprocess.DEVNULL)
info = subprocess.check_output(["avbtool", "info_image", "--image", str(persistent)], text=True)
if "Image size:               100663296 bytes" not in info or \
        "Partition Name:        boot" not in info:
    raise SystemExit("persistent noslpi image failed AVB footer validation")

sha = lambda p: hashlib.file_digest(p.open("rb"), "sha256").hexdigest()
manifest = {
    "target": "OnePlus 8 IN2010 / instantnoodle",
    "variant": "noslpi",
    "intent": "persistent cold-boot isolation; normal storage/display/USB/ADSP/Wi-Fi",
    "kernel_sha256": sha(kernel_art / "Image.gz"),
    "dtb_sha256": sha(dtb),
    "ramdisk_sha256": sha(rootfs_art / "initramfs-arch.cpio.gz"),
    "boot_sha256": sha(boot),
    "persistent_boot_sha256": sha(persistent),
    "persistent_boot_size": persistent.stat().st_size,
    "slpi_status": "disabled",
    "modem_pcie_status": "disabled",
    "cmdline": cmdline,
    "host_roundtrip": "passed",
    "phone_boot": "NOT TESTED",
}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
(out / "SHA256SUMS").write_text(
    f"{sha(boot)}  {boot.name}\n{sha(persistent)}  {persistent.name}\n"
    f"{sha(dtb)}  {dtb.name}\n"
)
print(json.dumps(manifest, indent=2))
