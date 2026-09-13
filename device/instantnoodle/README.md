# OP8 board bring-up gate

Target: OnePlus 8 / IN2010 / instantnoodle / project 19821 (DDR4).
Reference files were copied from existing offline evidence, not read from the phone in this task.

`reference/android-selected-base.dtb` is entry 6 of the original bootable recovery's concatenated DTB;
`reference/android-selected-overlay.dtbo` is entry 2. Those indices came from its recorded kernel command line.
They are **downstream Android trees**, not valid drop-in mainline device trees.

Known panel node name:
`qcom,mdss_dsi_oppo19101samsung_amb655uv01_1080_2400_cmd`, 1080x2400.

Upstream `sm8250-7.2.0` has instantnoodlep (8 Pro) and kebab (8T) references, but no instantnoodle build target.
Before generating an OP8 boot image, explicitly resolve these gates:

1. Diff reserved RAM, PMIC regulators, UFS power/PHY, and USB wiring against the actual OP8 tree.
2. Author `sm8250-oneplus-instantnoodle.dts` with supported mainline bindings; don't rename an 8 Pro DTB.
3. Prepare a minimal initramfs with early logging/ramoops and a USB diagnostic transport before UI startup.
4. Verify bootloader DTB/DTBO selection and compatibility. Do not apply arbitrary Android overlays to mainline trees.
5. Establish a hardware recovery path before the first test. Keep the existing original recovery untouched.
6. Only after base boot works, integrate Arch rootfs, matching kernel modules/firmware, then systemd/SSH.
7. Provision non-default credentials, package signing keys, and a device-specific kernel update hook before deployment.

The baseline has `CONFIG_USB_CONFIGFS=m`: a standalone diagnostic initramfs must include/load its matching modules
and dependencies, or a separately reviewed early-bring-up config must build the needed gadget pieces into Image.
Do not assume the baseline Image alone can expose USB networking.

No phone partitions or external storage are accessed by the host baseline build scripts.
No candidate OP8 boot.img is produced until this board-specific work exists and has been reviewed.

## 2026-09-06 diagnostic prototype

`sm8250-oneplus-instantnoodle-diagnostic.dts` now exists and compiles independently of 8 Pro DTS.
It is intentionally headless/storage-disabled. All 23 fixed carveouts from the original merged DT
are covered without overlap; downstream L2/L5/L12 USB HS rail voltage constraints match.
`diagnostic-init` and the cpio builder include matching, decompressed USB serial gadget modules.
These statements are offline invariants, not hardware or bootloader validation.
