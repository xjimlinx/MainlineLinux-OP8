# GitHub 参考与 OP8 适配记录 — 2026-09-12

目标为 IN2010 / instantnoodle / project19821，不是 instantnoodlep 或 kebab。
尚不能确认以下仓库就是用户所说 B 站视频作者的工程；这是本轮实际查到并核对的来源。

## 可复现来源

- [ben443/sm8250-mainline 的 8 Pro DTS](https://github.com/ben443/sm8250-mainline/blob/5621501522434c4d7119b50372971899c8f8a77d/arch/arm64/boot/dts/qcom/sm8250-oneplus-instantnoodlep.dts)，
  固定提交 `5621501522434c4d7119b50372971899c8f8a77d`（sm8250/v6.10）。
  阅读其 USB HS、RPMh 和 UFS 配置；不是 OP8 硬件验证记录。
- [ccc007ccc/sm8250-xiaomi-lmi-initramfs](https://github.com/ccc007ccc/sm8250-xiaomi-lmi-initramfs/tree/ca90a154cc10db18ab28d524235ef3f8c8d14e47)，
  固定提交 `ca90a154cc10db18ab28d524235ef3f8c8d14e47`。
  参考其“内核/DTS 管硬件，initramfs 负责早期日志和 rootfs 交接”的分层。
  没有复制/执行它的启动脚本、分区扫描、重启入口或相机服务。
- [sm8250-mainline/linux](https://github.com/sm8250-mainline/linux) 的默认分支 sm8250/v6.2
  已归档；该分支提交 `4fa4fe25ab35ea69b63006418217e38835fa379d` 的 qcom 目录没有 8 Pro DTS。
  因此不将现有 7.2 基线换成这个旧默认分支。
- 本地实际构建基线仍由 `sources.env` 锁定：社区 `sm8250-7.2.0`，
  `71f4068cb254730bcf334cde9bdd6ca183e4fcd0`。不是宣称上游 vanilla 已支持 OP8。

`bash scripts/fetch-github-references.sh` 获取两份只读参考快照并核验 SHA-256。
保留原始文件内容，代码许可仍随原项目；快照不参与编译，不作为本工程重新许可的代码。
哈希是本次 HTTPS 获取的内容锁定，不是发布者签名。

## 本轮实际修改

新增 `sm8250-oneplus-instantnoodle-storage-probe.dts`，包含既有 OP8 diagnostic DTS，
单独输出 `artifacts/storage-probe/instantnoodle-storage-probe.dtb`。
原 diagnostic 目标仍禁用 UFS；新目标启用 UFS HC/PHY，其他显示/无线/充电设备仍关闭。

原厂 DT 的消费者 phandle 已逐项核对：

| 消费者 | OP8 原厂供电 | 新目标 |
| --- | --- | --- |
| UFS VCC | PM8150 L17 | 2.504–2.950 V，取原厂消费者要求与供电约束交集 |
| UFS VCCQ | PM8150 L6 | 1.200 V |
| UFS VCCQ2 | PM8150 S4 | 1.800–1.920 V，使用真实 RPMh 节点 |
| UFS PHY | PM8150 L5 | 0.880 V，和 USB 共用 |
| UFS PHY PLL | PM8150 L9 | 1.200 V |

8 Pro 参考 L17 是 2.856–3.008 V，BOB 上限 4.000 V；OP8 原厂 BOB 上限 3.960 V。
这些值没有照搬。主线 UFS 不解析 Android 的 `vcc-voltage-level`，因此将交集写入 L17
主线 regulator 约束，而不是塞入无效的 Android 属性。

USB 和 UFS 的父级供电拓扑采用 8 Pro 社区树作为**待验证推断**：BOB→L2/L17、
S6A→L5、S8C→L6/L9、S5A→L12。OP8 原厂树确认了这些电源资源及电压范围，
但没有提供完整的物理父子连线证据。不能把静态链接一致说成电路已确认。
S5A/S6A/S8C 候选范围来自社区方案且落在 OP8 原厂允许范围内，未验证负载/压降/时序。
VPH 的 3.7 V 是电池总线的名义模型，不是设置电池充电电压。

诊断 initramfs 增加 `/proc/partitions` 与 `/sys/class/block` 元数据日志。
不打开块设备、不自动挂载 rootfs、不写 next-boot 标记；没有照搬 lmi 的 `/dev/sda34`。
但**启用 UFS 驱动本身不是硬件写保护**，探测可能发送配置/电源管理命令。

## 主机验证与复现

在项目根目录运行：

```sh
bash scripts/fetch-github-references.sh
bash scripts/build-diagnostic-dtb.sh
bash scripts/build-diagnostic-dtb.sh storage-probe
python3 scripts/build-diagnostic-initramfs.py
python3 scripts/test-diagnostic.py
python3 scripts/test-storage-probe.py
```

检查原机 23 个固定内存区间的覆盖/无重叠、USB 约束、5 组 UFS 消费者供电连接、
8 个新增电源范围、UFS 电流与 lane 数、父级链接、UFS/SCSI/PHY/RPMh 内建配置。
负向测试主动破坏电压、供电 phandle、电流、显示状态、机型 ID、父供电链接，必须被拒绝。
构建仍有 SoC 公共节点的 dtc 警告；未执行完整 DT schema 验证。
ARM64 工具测试使用 qemu-user，不是模拟手机内核启动。

## 距离实际安装仍有的门槛

1. 核对实际 ABL 对 boot header、DTB/DTBO 的选择和覆盖，再生成实验 boot.img。
2. 核对 OP8 UFS reset pin 的主线映射/复位时序；没有凭其他机型的 GPIO 数字补写。
   原厂 `ufs_reset` assert/deassert 状态已找到，现有社区 8 Pro HC 节点也没有明确 reset-gpios。
3. 核对原厂 UFS 的 vccq-parent、vddp-ref-clk 等辅助供电投票，不能默认主线完全等价。
4. 确认供电父级、安全复位/退出路径，做短时 RAM 诊断，先看真实 USB/UFS 日志。
5. 再接 Arch rootfs、准确的 PARTUUID/分区方案、匹配模块/固件和 systemd；然后是屏幕、
   触摸、GPU、无线、音频、充电和温控。没有验证的显示分辨率和面板命令不复制。

本轮没有连接/重启/刷写手机，也没有生成可安装镜像。不得把新 DTB 当作已完成的 ROM。

## 实验 boot image 打包

`scripts/build-boot-image.py` 现在可以生成两个 Android boot header v2 镜像：

```sh
python3 scripts/build-boot-image.py --variant diagnostic
python3 scripts/build-boot-image.py --variant storage-probe
```

参数来自本机备份的 LineageOS recovery（并非 OxygenOS 原厂镜像）：page size 4096、
kernel offset `0x8000`、ramdisk offset `0x01000000`、tags offset `0x100`、DTB offset
`0x01f00000`。ABL 外层保留已启动验证的 Lineage DTB 表与 recovery DTBO；Linux 使用
bootshim 内嵌的 OP8 主线 DTB。输出固定为 100 MiB recovery 容器，并加入可解析的
`Algorithm: NONE` AVB hash footer；解包后逐字节核对各负载。

主线 Image 原始 `text_offset=0`，原厂可启动 Image 是 `0x80000`。打包脚本只在副本的标准
ARM64 Image header 写入 `0x80000`，原始编译产物不变；这是结合 ARM64 boot protocol 和
同平台启动工程得到的兼容措施，仍需 ABL 真机测试。命令行设置 `panic=0`，不沿用原厂
`reboot=panic_warm`，以减少启动失败后的 logo 自动循环。

连接目标序列号 `d967403e` 后，先检查、再临时启动 diagnostic：

```sh
python3 scripts/fastboot-op8.py inspect
python3 scripts/fastboot-op8.py boot --variant diagnostic
```

只有临时启动拿到 USB ACM 日志、确认可恢复后，才运行：

```sh
python3 scripts/fastboot-op8.py flash-recovery --variant diagnostic
```

包装器只允许已记录的设备序列号和解锁状态，只写当前槽 `recovery_a/b`，写完不自动重启。
当前已固定并临时启动验证 `recovery_a` 回滚文件。B 槽备份的 AVB footer 后有额外尾部，
在重新规范化和验证之前，包装器拒绝写 B 槽。
`storage-probe` 必须在 diagnostic 真机启动成功后再临时启动，不能跳过阶段。

## Arch rootfs 镜像

`bash scripts/build-arch-rootfs.sh` 生成 6 GiB ext4 及 Android sparse 版本，文件系统标签
固定为 `arch-root`。它安装匹配的 `7.2.0-op8-bringup` 模块、USB `ttyGS0` getty 和首次
扩容服务。通用 Arch rootfs 的默认 root 密码会被随机密码替换，`alarm` 被锁定；新密码
只保存在权限 0600 的 `artifacts/arch-rootfs/INITIAL-ROOT-PASSWORD.txt`，首次登录后应修改。

`arch-init` 只接受命令行 `op8.arch=1`，只按 ext4 标签选择根设备，然后切换到 systemd；
它不会依赖其他机型的分区号。对应镜像由以下命令生成和验证：

```sh
python3 scripts/build-diagnostic-initramfs.py --mode arch
python3 scripts/build-boot-image.py --variant arch
python3 scripts/test-arch-rootfs.py
```

若决定用 `userdata` 承载 Arch，必须先在 recovery fastbootd 确认 `is-userspace=yes`。
下列包装命令会校验序列号、解锁状态、镜像哈希和 userdata 容量，然后**覆盖 userdata 内容**：

```sh
python3 scripts/fastboot-op8.py flash-arch-userdata --variant arch
```

写 rootfs 后返回 bootloader fastboot；只有当前槽存在已固定回滚镜像时才写 recovery：

```sh
python3 scripts/fastboot-op8.py flash-recovery --variant arch
```

包装器均不会自动重启。推荐的真机顺序仍是 diagnostic 临时启动 → storage-probe 临时启动
→ 检查日志 → 写 userdata → 写有回滚保护的当前槽 recovery → 手动进入 recovery 启动 Arch。
