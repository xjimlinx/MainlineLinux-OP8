# Linux 7.2.5 running on OnePlus 8 IN2010 — 2026-09-14

> 2026-09-15：用户确认不接 USB 的卡住过程，只插线、不重启便立即继续。
> 已定位并删除早期 `/init` 向未连接的 `ttyGS0` 同步写入而无限等待的路径；
> 新 A 槽镜像接线启动约 14 秒、读回哈希一致，A 槽 successful=1。
> 用户随后拔线、完全关机，仅按电源键开机，确认直接进入 Linux；
> **一次 USB-free 冷启动通过**，多轮可靠性回归仍待做。下文旧的
> “正常启动”记录不能当作该验收。
> 隔离证据及刷写记录见
> [`docs/NOSLPI-BOOT.md`](docs/NOSLPI-BOOT.md)。

应用部署记录（QQ / Steam / WPS / Blender / OBS）见 [`docs/APP-DEPLOYMENT.md`](docs/APP-DEPLOYMENT.md)。QQ 与 WPS 365 ARM64 已部署；Steam、Blender、OBS 的架构限制与后续方案已记录。

## 基带 PCIe 已屏蔽

为避免未使用的 SDX55 基带在冷启动时参与 PCIe PHY 链路训练，设备树提交
`be00898d3` 将 `pcie2`/`pcie2_phy`（`1c10000.pcie`）设为 disabled。Wi‑Fi
`pcie0`（`1c00000.pcie`）、USB‑C、显示、UFS 不受影响。新镜像已写入 A 槽并验证
正常启动：仅出现 Wi‑Fi PCIe endpoint，未出现 SDX55/MHI 节点，图形目标约 12 秒达到。

## Latest boot investigation

静态分析确认面板 AVDD 固定稳压器缺少 `enable-active-high`，导致
`regulator-fixed` 将 GPIO61 按低有效处理；同时禁用 bootloader 的 simple-framebuffer，
让 msm_dpu 独立初始化面板。7nm DSI PLL 的实验性三次重试会造成重复时钟关闭警告，已
回退到基线实现。当前镜像 hash 为
`60ff7408d8c5ab70c7bd56aebe9549794781efe180f1b5678704d2d49a6a4a5e`，已写入 A 槽并
完成正常重启验证。

启动日志“卡住”并非 fastboot：实测 `op8-bluetooth-setup.service` 反复等待约 35 秒，
同时 Arch 默认 `archlinux-keyring-wkd-sync.service` 因网络 WKD 查询可持续数分钟。
蓝牙初始化现由 timer + 瞬时 launcher 放到后台，WKD timer 已禁用；当前图形目标约
5 秒达到，蓝牙控制器仍能正常出现并保留稳定地址。

## SDDM touch login

SDDM 0.21 的 OP8-Breeze QML greeter 已替换为默认登录器，`qt6-virtualkeyboard` 已安装，
因此锁屏/登录界面可直接触摸输入密码，并能从会话菜单选择 Plasma Mobile 或 Plasma
Desktop。SDDM greeter 当前固定使用 X11 以避开手机上仍属实验性的 Wayland greeter；登录后
两个 Plasma 会话仍通过 KWin Wayland 启动。没有独立的“SDDM Mobile”软件包，手机布局由
Plasma Mobile 会话和 SDDM QML 主题提供。OP8-Breeze 将 Qt 缩放设为 2 倍，并在
密码框获得焦点后自动打开虚拟键盘；键盘可覆盖屏幕底部，但会话选择入口仍保留在键盘上方。

2026-09-14 13:45 重新启动后运行内核为 `7.2.5-op8-mainline #9`；KMS 抓帧显示登录器
颜色正常，启动日志也未再出现 `dsi_err_worker: status=5`。

## 2026-09-14 A 槽持久启动

IN2010 已从 A 槽的 `boot_a` 正常启动 `7.2.5-op8-mainline`，不是
`fastboot boot` 临时启动。启动参数确认 `androidboot.slot_suffix=_a` 和
`androidboot.mode=normal`；`qbootctl` 已将 A 槽标为 active、successful、bootable，
因此 A/B 的 7 次重试计数不会继续递减。

原始 22,642,688 字节 boot image 直接写入分区时缺少 AVB footer，是此前 ABL 正常
启动返回 fastboot 的原因。实际刷入的是按 96 MiB `boot_a` 分区尺寸添加
`Algorithm: NONE` hash footer 后的镜像，同时使用 flags=3 的 AOSP 17 IN2010
`vbmeta_a`。完整命令、产物 SHA-256 和恢复说明见
[`docs/PERSISTENT-BOOT-A.md`](docs/PERSISTENT-BOOT-A.md)。

已修复：主线内核加入 Kona 的 `qcom,pshold` 节点（`0x0c264000`）、禁用 PM8009 重复
reboot-mode 注册，并移植 Qualcomm SCM `DEASSERT_PS_HOLD` 调用。真机日志确认
`secure PS_HOLD deassertion available`，普通 `sudo reboot` 已自动回到 A 槽 Linux。
AMB655UV01 面板改为参考 vendor 初始化序列，不再加入未经证实的 DCS 反色补偿；DTS
补充 AVDD 有效电平并禁用 simple-framebuffer。最终修复提交为
`cc62123b8`，完整镜像已刷入 A 槽，设备多次正常重启且当前画面由用户确认正常。

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
The upstream containment configuration window remains non-interactive with this
Plasma 6.7.5/Qt 6.11.2 combination: its page is created outside the graphics
scene. `op8-set-wallpaper` and its “选择壁纸” application entry therefore provide
a working native file chooser and apply the selected image through the tested
Plasma scripting API, without depending on that broken internal window.

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
locally administered address derived from the installation machine-id. The setup
is queued by a non-blocking boot timer, and the Arch keyring WKD refresh timer is
disabled so network availability cannot delay the graphical target. BlueZ then
reports BR/EDR and LE support and a live scan discovered nearby devices.
Actual pairing and A2DP playback still need a user-selected peer. RFCOMM and
BNEP have been enabled for the next matched kernel/module build. The flashlight
has also been confirmed working by the user.

## Linux 7.2.5 validation

The IN2010 has successfully booted the persistently installed
`7.2.5-op8-mainline` kernel into the installed Arch Linux ARM root filesystem.
UFS/ext4 root, USB ACM+NCM, SSH, DRM, the Samsung AMB655UV01 panel, freedreno
firmware, KWin Wayland and Plasma Mobile all reached userspace. `boot_a` is the
active persistent slot; `boot_b` remains available as fallback.

The test image is `artifacts/linux-7.2.5-op8/boot-in2010-linux-7.2.5.img`
(SHA-256 `60ff7408d8c5ab70c7bd56aebe9549794781efe180f1b5678704d2d49a6a4a5e`).
Matching 7.2.5 modules are installed under
`/usr/lib/modules/7.2.5-op8-mainline` on the Arch root filesystem.
The corresponding source snapshot is published as branch `7.2.5-op8` at
`https://github.com/xjimlinx/mainline-instantnoodle` (commit
`cc62123b8`).

The panel inversion regression was traced to regulator late cleanup disabling
`panel_avdd_5p5` while the panel was active, followed by an unbalanced disable.
The driver now owns a lifetime regulator reference, restores the vendor F5=87
normal-color latch, uses the vendor 8/4/6 vertical porch, and uses the complete
IN2010 initialization table. The fix is committed in the kernel worktree as
`d51f4884ca39d7e7846329f8f77e13fe09c5cee9` and is present in the 7.2.5 image.

Remaining display work: verify the new 7nm PLL retry with repeated warm reboots and
screen off/on stress before replacing the installed boot image. The previous kernel
still has a probabilistic inversion report; it is not claimed fixed until this test.

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
