# OnePlus 8 IN2010：A 槽持久启动记录

最后验证：2026-09-14，设备序列号 `d967403e`。

当前最新修复尚未写入分区：7nm DSI PLL 三次重试和非阻塞蓝牙/WKD 启动修复已在工作树
和临时 rootfs 上验证，需下一次 fastboot 临时启动确认反色后，才允许更新 A 槽。

后续修复提交：`df767446842a25bdcc0bef14cb94df4f76c38f1d`（PS_HOLD 安全调用、
PM8009 重复 PON），以及 `527a6d9f3d1bd1c69f5239fa877cd43d16a47249`（面板 DCS
反色状态清理），`ecc4a6c728da2ec35d984e0131dbe3678d1a80c2`（7nm DSI PLL warm-reboot 重试）。

2026-09-14 13:45 已重新编译并将包含上述面板修复的 7.2.5 内核写入 `boot_a`；
设备随后从 A 槽重新启动，屏幕通过 KMS 抓帧确认颜色正常。新的带 AVB 尾部镜像
SHA-256 为 `3390a3de52ee14b7b5ea78e7bd8a053a6fd61d45eb7735b0f76a14e5ba00b688`。

## 结果

OnePlus 8 IN2010 已经从 A 槽的 `boot_a` 正常启动 Linux
`7.2.5-op8-mainline`，不再依赖主机执行 `fastboot boot`。启动后的
`/proc/cmdline` 同时包含：

```text
androidboot.slot_suffix=_a
androidboot.mode=normal
```

`qbootctl` 的最终状态为：

```text
Current slot: _a
SLOT _a:
        Active      : 1
        Successful  : 1
        Bootable    : 1
SLOT _b:
        Active      : 0
        Successful  : 0
        Bootable    : 1
```

其中 `Successful: 1` 很重要：高通 A/B metadata 的重试计数最大只有 7，
successful 标记会停止正常启动时继续扣减计数。

## 根因与修复

最初能用 `fastboot boot` 临时启动的 boot image 只有 Android boot header-v2，
文件末尾没有 AVB footer。直接写进 `boot_a`/`boot_b` 后，正常 ABL 分区启动会在
进入 Linux 前返回 fastboot。Linux journal 显示此前系统能够完整执行关机流程，
因此该失败不是 rootfs 或 systemd 启动错误。

已验证的原始临时启动镜像：

```text
artifacts/linux-7.2.5-op8/boot-in2010-linux-7.2.5.img
size:   22642688 bytes
sha256: ca545c7230f8ec7b5b44897cb3ab4cbadc99ee076f264094b2a719a8a26aa068
```

IN2010 的 `boot_a` 大小为 `0x6000000`（96 MiB）。使用以下方式制作带 footer 的
分区镜像：

```sh
mkdir -p artifacts/linux-7.2.5-op8/persistent
cp artifacts/linux-7.2.5-op8/boot-in2010-linux-7.2.5.img \
  artifacts/linux-7.2.5-op8/persistent/boot-in2010-linux-7.2.5-avb.img
avbtool add_hash_footer \
  --image artifacts/linux-7.2.5-op8/persistent/boot-in2010-linux-7.2.5-avb.img \
  --partition_name boot \
  --partition_size 100663296 \
  --algorithm NONE
avbtool info_image \
  --image artifacts/linux-7.2.5-op8/persistent/boot-in2010-linux-7.2.5-avb.img
```

此前生成并实际刷写的完整分区镜像：

```text
size:   100663296 bytes
sha256: 3390a3de52ee14b7b5ea78e7bd8a053a6fd61d45eb7735b0f76a14e5ba00b688
```

最新未刷写镜像（包含 7nm PLL 重试）hash：

```text
sha256: bfdca81f1f4b9d1b85a44b2bce080fb6cea6663cbb709861aea1c9ba75368231
```

## 本次实际刷写步骤

警告：下面的命令会覆盖 A 槽 boot/vbmeta，只适用于已解锁 BL 的 IN2010。
执行前必须逐项确认型号、解锁状态和 boot 分区尺寸。

```sh
fastboot devices
fastboot getvar product
fastboot getvar unlocked
fastboot getvar partition-size:boot_a

fastboot flash vbmeta_a /Work/Data/OnePlus8/AOSP-OP8/out/target/product/instantnoodle/vbmeta.img
fastboot flash boot_a artifacts/linux-7.2.5-op8/persistent/boot-in2010-linux-7.2.5-avb.img
fastboot set_active a
fastboot reboot
```

本次使用的 `vbmeta_a` 来自本机 AOSP 17 IN2010 构建，AVB flags 为 3
（disable verification + disable hashtree）：

```text
size:   65536 bytes
sha256: 1240bb219395fc0ceb0df56e61cab5a00aed72607479fc42867c08dfd11b93d0
```

进入 Linux 后立即确认并停止 A/B 重试计数：

```sh
sudo /usr/local/bin/qbootctl -m a
sudo /usr/local/bin/qbootctl
cat /proc/cmdline
```

## 恢复入口

如果 A 槽无法启动，按键进入 bootloader 后，可先用未经 footer 扩展的已验证镜像
临时启动并维修系统：

```sh
fastboot boot artifacts/linux-7.2.5-op8/boot-in2010-linux-7.2.5.img
```

不要盲目切换到 B 槽：截至本记录，B 槽虽然仍标为 bootable，但没有标为
successful，也没有被确认为可靠救援系统。

## 尚未解决的问题

持久启动已经解决。修复版已通过 Qualcomm SCM deassert PS_HOLD，普通重启可自动回到
A 槽 Linux；完整回归与 ABL 模式选择说明见下节。不要把此前的关机卡住误判成 A 槽
boot image 没有固化。

## 复位与反色修复回归

修复版日志为 `msm-restart c264000.restart: secure PS_HOLD deassertion available`。
普通 `sudo reboot` 已自动回到 A 槽 Linux；`reboot bootloader` 的 PS_HOLD 复位也成功，
但 OnePlus ABL 对 PON magic 的解释仍可能继续选择 normal boot。面板初始化序列在
vendor 解锁和 normal mode 后各加入一次 `MIPI_DCS_EXIT_INVERT_MODE (0x20)`，用于清理
warm reboot 后偶发的反色锁存；完整镜像重新刷入后当前画面已确认正常。
