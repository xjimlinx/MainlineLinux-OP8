# IN2010 无 SLPI 冷启动隔离镜像

## 2026-09-15：删除无主机时阻塞的 ttyGS0 写入（冷启动通过）

用户再次确认不插 USB 不能可靠启动。运行中的 `boot_a` 哈希仍为
`8f3d29357d37e772fa9212ab22eccd958e3691b893c6989f0998292f181d299f`，
与此前已刷镜像一致；A 槽 `successful=1`。18:33 这次成功启动的 ABL 参数是
`androidboot.startupmode=pwrkey`，但这不证明启动期间没有 USB 插拔。

该次内核时间线：约 6.96 秒按标签找到根分区，7.08 秒 ext4 挂载完成，
16.87–17.11 秒输出 deferred-probe/sync-state 提示，28.87 秒出现 Type-C
PMIC 中断，29.41 秒才见到 systemd 的第一条消息，33.67 秒 Wi‑Fi PCIe
链路连上。屏幕留在 16 秒的打印处不证明 PCIe 卡死；根分区挂载与 systemd
开始之间约 22 秒无 `/init` 进度日志，需要隔离。

用户确认：无 USB 卡住后，只插线、不重启，启动立即继续。静态分析找到
`/init` 的匹配等待路径：旧脚本在 `exec switch_root` 前同步写
`/newroot/dev/ttyGS0`；`u_serial.c` 的 `gs_write_room()` 在尚未建立 USB
串口连接时返回 0，`n_tty_write()` 随后无超时等待可写事件。插线使
`gserial_connect()` 建立串口并唤醒写入，因此可解释根分区已挂载而
systemd 尚未出现、插线立即放行的现象。`gs_close()` 另有最长 15 秒的
缓冲区排空等待，可能拖慢已接线的路径。已从候选 `/init` 删除同步输出，
并在根分区挂载后向内核消息及 `/var/log/op8-early-boot.log` 同步写入
`root-mounted`、`mounts-moved`、`switch-root` 三个标记，附带 boot ID 和
运行时间。若不接 USB 失败后经 fastboot/USB 恢复，先读取此文件，判断停在
`/init` 还是已进入 systemd。

新候选 A 槽镜像 SHA-256 为
`6979e1c22ad42053c3dcf5c752fbcfbb2f26108bd3a0d83d965675732fa1a3d7`。
已完成本机构建与 round-trip 校验。当前 A 槽镜像及 vbmeta 的只读备份保存
于 `backups/boot-a-pre-ttygs0-fix-20260915/`，哈希分别为
`8f3d29357d37e772fa9212ab22eccd958e3691b893c6989f0998292f181d299f`、
`1240bb219395fc0ceb0df56e61cab5a00aed72607479fc42867c08dfd11b93d0`。
已在 bootloader fastboot 核对目标序列号 `d967403e`、型号 `kona`、BL
解锁、非 fastbootd 后，仅写入 `vbmeta_a`、`boot_a` 并激活 A 槽。手机读回
`boot_a` SHA-256 与候选一致；接 USB 的本次重启中，`root-mounted` 为
6.34 秒，`switch-root` 为 6.40 秒，systemd 首条日志为 6.45 秒，
`graphical.target` 已 active，总启动约 14.07 秒。已按健康检查手动将 A 槽
标为 `successful=1`。随后用户拔掉 USB、完全关机，仅按电源键开机，
确认 **不接 USB 也能直接进入 Linux**。这是一次 USB-free 冷启动实测；
尚未做多次断电循环或不同电量状态的回归，不能据此保证绝对可靠。

## 2026-09-15：USB 不再阻塞根分区启动

此前 initramfs 的 `/init` 在寻找 `arch-root` 前先等待 USB gadget 的 UDC 最多
60 秒；若 cold boot 的 USB 控制器没有及时注册，会进入永久等待，即使 UFS 和
根分区已正常枚举。现在 USB ACM/NCM 初始化是可选步骤：最多等待 UDC 5 秒，
失败会记录 `OP8ARCH: USB gadget unavailable`，仍继续按精确 ext4 标签寻找
并挂载 Arch 根分区。这是针对启动顺序的修复假设，尚不能据此宣称冷启动已解决。

新裸镜像 SHA-256 为
`bb15111a5593416a978a5843cdb73e02f5bcc53943e92f8cb0d4e01dd6565f35`，
已通过 `fastboot boot` 进入 Arch；USB ACM/NCM、SSH 与
`graphical.target` 正常。新 A 槽分区镜像 SHA-256 为
`8f3d29357d37e772fa9212ab22eccd958e3691b893c6989f0998292f181d299f`，
已写入 `boot_a` 并从 A 槽正常重启；Linux 下只读读回哈希相同，A 槽已标记
successful。B 槽、recovery 和 userdata 未写入。

刷写前手机上只读校验过的旧 `boot_a` 已保存到
`backups/boot-a-noslpi-20260915-pre-udc/boot_a.img`，SHA-256 为
`9c083d5c6cbb0d45581efec370a85f07fd857f702c6b0cf276195df0b4f97ff5`。
旧 `vbmeta_a` 与当前刷回的 AOSP vbmeta 均为
`1240bb219395fc0ceb0df56e61cab5a00aed72607479fc42867c08dfd11b93d0`。
在当时阶段仍需完全断电后按键开机，不能用 fastboot 或软件重启的成功
代替冷启动验收；后续实测见本文开头。

## 目的

该变体使用完整的 `sm8250-oneplus-instantnoodle.dts`，只覆盖
`&slpi { status = "disabled"; }`；UFS、显示、USB、ADSP、CDSP 和 Wi‑Fi
保持正常主线配置，另行保留调制解调器 PCIe 的 disabled 状态。

它用于判断约 16 秒处的冷启动卡顿是否来自 SLPI remoteproc，不是最终功能
镜像，也不是 lk2nd 或新的 bootloader。

## 构建

```sh
python3 scripts/build-noslpi-boot.py
```

脚本会编译 DTB、打包 Android boot header v2、做 boot round-trip 校验并生成
带 `boot` 分区 AVB hash footer 的 96 MiB 镜像：

```text
artifacts/boot-images/noslpi/boot-in2010-noslpi.img
artifacts/boot-images/noslpi/boot-in2010-noslpi-avb.img
```

## 写入单个槽位

仅在 bootloader fastboot、型号为 Kona 且 BL 已解锁时执行。流程只写 A 槽的
`vbmeta_a`、`boot_a`，不写 B 槽、recovery 或 userdata：

```sh
python3 scripts/fastboot-op8.py inspect --serial <serial>
python3 scripts/fastboot-op8.py flash-noslpi-a --serial <serial>
```

该命令不会自动重启。确认输出和 USB 线稳定后，再手动重启。进入 Arch 并且
`graphical.target` 正常后，系统内的 `op8-mark-slot-successful.timer` 才会把
A 槽标记为 successful。

## 此前 warm/reboot 阶段的验证边界

主机静态校验已通过；本次设备从 fastboot 重启后成功进入
`7.2.5-op8-mainline`，系统状态为 `running`，DSI 状态为 `connected`，
remoteproc 仅有 `cdsp`、`adsp`，没有 SLPI handover 日志，A 槽已标记 successful。
上述阶段尚不能把一次 warm/reboot 验证当作冷启动结论；后续 USB-free
冷启动的用户实测结果已记录在本文开头。仍需多轮断电回归。
