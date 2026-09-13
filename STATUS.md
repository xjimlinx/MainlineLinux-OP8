# Linux 7.2.5 running on OnePlus 8 IN2010 — 2026-09-13

## Plasma Mobile configuration crash workaround

On Plasma Mobile 6.7.5 with Qt 6.11.2, opening the Folio desktop configuration
reproducibly crashed `plasmashell` in `QQmlBind::componentComplete`, briefly
leaving a black screen while systemd restarted the shell. KWin stayed alive and
the kernel logged no GPU fault. The rootfs overlay now defers the configuration
window flags and visibility assignments until the attached window is valid.
Both the widget explorer and the containment configuration entry were exercised
over D-Bus afterward without a new coredump or a `plasmashell` PID change.
The wallpaper page also received a guard for Plasma's temporarily empty
wallpaper-plugin model selection. It now falls back to `org.kde.image` instead
of attempting to apply an empty plugin name. A transferred JPEG was applied
through the Plasma scripting API and the patched configuration page reopened
without changing the shell PID or logging another empty-plugin failure.

## Audio and Bluetooth validation

The 7.2.5 port now includes the missing TFA9872/TFA9874 ASoC driver. Both
IN2010 amplifiers identify as revision `0x0c74`; the OnePlus8 ALSA card exposes
three playback and three capture PCMs, and PipeWire exposes the UCM speaker
sink and stereo microphone source. A low-volume speaker PCM completed, five
successive microphone opens produced no QDSP6 allocation/open errors, and a
full-duplex test captured the emitted test tone. Longer recording and physical
earpiece/headset routing remain unvalidated.

QCA6390 Bluetooth now loads the phone-matched firmware and NVM read-only from
the stock `bluetooth_a` partition. Because this NVM exposes the controller
without a usable public address, `op8-bluetooth-setup.service` assigns a stable
locally administered address derived from the installation machine-id. BlueZ
then reports BR/EDR and LE support and a live scan discovered nearby devices.
Actual pairing and A2DP playback still need a user-selected peer. RFCOMM and
BNEP have been enabled for the next matched kernel/module build. The flashlight
has also been confirmed working by the user.

## Linux 7.2.5 validation

The IN2010 has successfully temporary-booted the locally built
`7.2.5-op8-mainline` kernel into the installed Arch Linux ARM root filesystem.
UFS/ext4 root, USB ACM+NCM, SSH, DRM, the Samsung AMB655UV01 panel, freedreno
firmware, KWin Wayland and Plasma Mobile all reached userspace. No phone boot
partition was written; rebooting still falls back to the previously installed
kernel.

The test image is `artifacts/linux-7.2.5-op8/boot-in2010-linux-7.2.5.img`
(SHA-256 `e1a6c42d675fcfad365675e98a9189d893c069642489bce0ae3bdd5518317fa5`).
Matching 7.2.5 modules are installed under
`/usr/lib/modules/7.2.5-op8-mainline` on the Arch root filesystem.
The corresponding source snapshot is published as branch `7.2.5-op8` at
`https://github.com/xjimlinx/mainline-instantnoodle` (commit
`eb5ded2cafbca9e93ad6f6f388d11693cee09d58`).

The panel inversion regression was traced to regulator late cleanup disabling
`panel_avdd_5p5` while the panel was active, followed by an unbalanced disable.
The driver now owns a lifetime regulator reference, restores the vendor F5=87
normal-color latch, uses the vendor 8/4/6 vertical porch, and uses the complete
IN2010 initialization table. The fix is committed in the kernel worktree as
`d51f4884ca39d7e7846329f8f77e13fe09c5cee9` and is present in the 7.2.5 image.

Remaining display work: the first modeset still records a recovered DSI PLL
lock retry and one `dsi_err_worker: status=5`. The desktop remains running, but
screen off/on and longer suspend stress must pass before replacing the installed
boot image.

## Running Arch deployment

The IN2010 now boots Arch Linux ARM with the device-specific 6.16.7 kernel and
Plasma Mobile. Display, freedreno GPU acceleration, touch, Wi-Fi, USB networking,
SSH, battery reporting and basic speaker playback are operational. Firefox,
Simplified Chinese localization, Konsole, PipeWire, WirePlumber, plasma-pa and
RealtimeKit are installed by the reproducible deployment recipe.

OnePlus 8 UCM routing is included in the rootfs overlay. PipeWire exposes a real
speaker sink and microphone source; a short speaker sample completes without a
new kernel error. Microphone capture is not stable: the QDSP6 driver reports
`Buffer already allocated` and `q6asm_open_write failed`, after which PipeWire
must restart. Do not treat microphone input as working yet.

The 7.2.0 SM8250 community tree has now been updated with the official stable
7.2.5 patch and the IN2010 DTS/panel port. It has passed its first temporary
boot, but must not replace the boot-tested fallback until display power-state,
audio, charging/thermal and rollback tests are complete.

## Latest work

GitHub-based adaptation added a separate `storage-probe` DTS, preserving the diagnostic target.
OP8 UFS supply phandles/current limits and eight additional rail bounds are checked against
the original merged DT; the L17 consumer range is 2504000–2950000 uV, not the 8 Pro range.
Six corrupted-DTB negative tests pass. USB logs now include block-device metadata only.
See `device/instantnoodle/GITHUB-ADAPTATION.md` for pinned references and remaining gates.
Phone-side temporary-boot testing has started; Arch installation and hardware
power-sequencing validation have not occurred.

The direct EFI and non-EFI mainline payloads both remained in fastboot without a USB
disconnect. A copy-down payload with a mainline DTB embedded beyond the padded Linux
image was then built. A 100 MiB Lineage recovery_a control image boots successfully;
an EvolutionX boot_a control image is rejected by this ABL temporary-boot path.
The current diagnostic image now mirrors the working recovery container size and has
an `Algorithm: NONE` AVB hash footer. It still requires a phone-side temporary boot test.
No phone partition has been written.

An Arch Linux ARM ext4 image is also complete: 6 GiB expanded, approximately 1.9 GiB
Android sparse, label `arch-root`, with matching modules and a private randomized root
credential. `e2fsck`, sparse-header, credential, systemd/getty and boot-image linkage tests pass.
The Arch boot image must be regenerated with the validated container after diagnostic
and storage-probe gates pass. `userdata` has not been written.

Current project root: `/Work/Data/OnePlus8/MainlineLinux-OP8`.
Additional host tests: `bash scripts/build-diagnostic-dtb.sh storage-probe && python3 scripts/test-storage-probe.py`.

The baseline pipeline completed successfully at 02:56:44. No baseline build remains running.
Subsequent work authored and compiled an OP8-specific headless diagnostic DTS and built a RAM-only
diagnostic initramfs. See `artifacts/diagnostic/test-results.json` for current host-side tests.
There is still no boot.img, no phone boot test, and no installed Arch system.

- Diagnostic DTB compiles; all 23 fixed reserved-memory ranges from the selected
  original Android DTB/overlay are covered, with no overlapping prototype ranges.
- RAM-only diagnostic initramfs: approximately 6.8 MiB compressed, 42 cpio entries.
  USB ACM is log-only and requires explicit `op8.diag=1`; no shell or block mounts.
- ARM64 BusyBox, mount and kmod execute under qemu-user; shell syntax, PID guard,
  cpio ownership/payload hashes, and static board invariants pass host-side tests.
- qemu-user does not test the kernel, PID 1 startup path, or actual phone hardware.
- Before boot-image packaging: review bootloader DTB/DTBO handling, parent power
  rails and a safe exit/reset path. Charging/thermal behavior is not validated.

Rebuild/test diagnostic components:

```sh
cd /Work/Data/OnePlus8/MainlineLinux-OP8
bash scripts/build-diagnostic-dtb.sh
python3 scripts/build-diagnostic-initramfs.py
python3 scripts/test-diagnostic.py
```

The following records describe the original launch, not current running jobs.

- Internal disk: `/Data`, initially 102 GiB available; approximately 99 GiB remaining when compilation started.
- Rootfs: downloaded, gzip/tar integrity passed. SHA-256 pinned in `sources.env`.
  MD5 `23eec86365b24f7913c403e8f4e8719b` also matched the de3 Arch Linux ARM mirror.
  This is not a publisher-signature verification of the rootfs.
- Kernel source/config: downloaded, SHA-512 matches pinned pmaports metadata.
- LLVM utilities: downloaded, SHA-256 and Arch packager GPG signature verified, extracted locally.
- Actual ARM64 `make -j16 Image modules dtbs` started using Clang/LLVM 22.1.8.
- Build managed session: 73999; supervisor PID at launch: 689555. These are historical identifiers, not proof of current liveness.
- At original launch, OP8-specific device tree and diagnostic initramfs were pending;
  these components have since been implemented as unvalidated prototypes above.
- No ADB/fastboot, no writes to phone, no firmware changes, no deletion of AOSP or backups.

Check live status with `bash scripts/status.sh` from the project root.
Detailed build log: `logs/build-kernel.log`.
The final pipeline message indicates only the host baseline has finished, not OP8 boot validation.

To rerun the baseline pipeline after it exits:

```sh
cd /Work/Data/OnePlus8/MainlineLinux-OP8
set -o pipefail
bash scripts/start-build.sh 2>&1 | tee -a logs/pipeline.log
```

The project lock rejects concurrent pipeline runs. Existing source/output is preserved for incremental rebuilds.
