# OnePlus 8 IN2010 — Arch Linux ARM bring-up

目标：原生 Linux + Arch Linux ARM 用户空间，不依赖 Android 运行。

本工程已完成并在 IN2010 真机临时启动 Linux 7.2.5、OP8 专用 DTB、
Arch Linux ARM、Plasma Mobile、USB ACM/NCM 及 freedreno GPU。
**目前只验证了 `fastboot boot`；显示休眠、充电和温控回归完成前，不要永久刷写。**
禁止把 instantnoodlep（8 Pro）或 kebab（8T）的参考 DTB 当成 instantnoodle（8）的成品。
本工程的构建脚本不读取或修改工程目录外的 Android/recovery 文件。

## 构建范围

1. 固定已真机启动的 Linux 7.2.5 OP8 源码快照与 postmarketOS 基础配置。
2. 构建 ARM64 Image.gz、IN2010 DTB 和对应模块。
3. 获取 Arch Linux ARM aarch64 rootfs，验证归档完整性并固定本地 SHA-256。
4. 独立核对 OP8 设备树、固件与 USB/initramfs；通过后才制作实验启动镜像。

`scripts/build-linux-7.2.5-op8.sh` 默认 `-j16`。内核输出在
`build/kernel-7.2.5-op8/`，打包输入在 `artifacts/linux-7.2.5-op8/`。

## 从空目录复现 Linux 7.2.5 镜像

Arch Linux 主机需要 Git、Clang/LLVM、make、bc、bison、flex、pahole、
OpenSSL、libelf、Python、cpio、gzip、zstd、fakeroot、libarchive、e2fsprogs、
qemu-user-static、android-tools（`mkbootimg`、`unpack_bootimg`、`img2simg`）和
约 20 GiB 可用空间。Arch Linux 可安装：

```sh
sudo pacman -S --needed base-devel bc clang llvm lld libelf pahole python git curl \
  gnupg libarchive cpio zstd fakeroot dtc e2fsprogs android-tools qemu-user-static
```

一条命令执行完整构建、图形 rootfs 配置和离线校验：

```sh
OP8_JOBS=16 bash scripts/reproduce.sh
```

脚本只生成本地文件，不连接或写入手机；配置 rootfs 时会通过 polkit 请求一次主机权限。
需要逐步排错时使用下面的等价命令。

```sh
git clone https://github.com/xjimlinx/MainlineLinux-OP8.git
cd MainlineLinux-OP8

# 获取并校验精确的真机测试源码快照
bash scripts/fetch-linux-7.2.5-op8.sh

# 获取固定提交的 OP8 固件/ALSA 配置和固定校验和的 Arch rootfs
bash scripts/fetch-device-assets.sh
bash scripts/fetch-qbootctl.sh
bash scripts/fetch-rootfs.sh

# 构建 7.2.5-op8-mainline、DTB 与模块
OP8_JOBS=16 bash scripts/build-linux-7.2.5-op8.sh

# 构建基础 ext4/sparse rootfs，再安装 Plasma Mobile、Firefox、Konsole 等
bash scripts/build-arch-rootfs.sh
pkexec bash "$(pwd)/scripts/provision-arch-deploy.sh"

# 生成匹配该内核的 Arch initramfs
python3 scripts/build-diagnostic-initramfs.py --mode arch

# 生成并回读校验 header-v2 boot.img
python3 scripts/build-linux-7.2.5-boot.py
(cd artifacts/linux-7.2.5-op8 && sha256sum -c SHA256SUMS)
```

root 与图形用户的随机初始密码分别保存在 `artifacts/arch-rootfs/` 下权限为
0600 的文件中。软件包取自构建时的 Arch Linux ARM 仓库，因此流程可复现，软件包集合
并非逐字节冻结；内核源码、配置、固件/ALSA 提交和 rootfs 归档均有固定身份校验。

只做 RAM 临时启动：

```sh
# 如果手机的 Arch rootfs 已存在而内核刚刚重新编译，必须先同步匹配模块。
bash scripts/sync-running-kernel-modules.sh xein@172.16.42.1
fastboot boot artifacts/linux-7.2.5-op8/boot-in2010-linux-7.2.5.img
```

即使 `uname -r` 未变化，重新链接的内核与旧模块也可能因 BTF 身份不同而不兼容；
不得只更新 boot.img。完整 rootfs 配置流程会自动覆盖为本次构建的匹配模块。

要复现当前整机环境，先在 recovery/fastbootd 明确确认设备是 IN2010 且允许清空
`userdata`，然后写入 sparse rootfs；此命令会不可恢复地覆盖手机用户数据：

```sh
fastboot getvar is-userspace
fastboot flash userdata artifacts/arch-rootfs/archlinux-in2010-rootfs.sparse.img
fastboot reboot bootloader
fastboot boot artifacts/linux-7.2.5-op8/boot-in2010-linux-7.2.5.img
```

Git 仓库不存放生成的 rootfs、boot.img、固件或编译目录。内核源码快照位于独立公开
仓库；主仓库跟踪配置片段、rootfs overlay、构建/校验脚本和所有输入提交/哈希。
第三方固件保持原来源下载，不在本仓库重复分发。

## 真机功能状态

Linux 7.2.5 已验证显示、触摸、freedreno、UFS、USB ACM/NCM、Wi-Fi、
扬声器 PCM、双声道麦克风 PCM、QCA6390 蓝牙扫描和手电筒。蓝牙初始化服务从
本机只读 `bluetooth_a` 分区提取与硬件匹配的 `htbtfw20.tlv`/`htnv20.bin`，
并为缺少出厂公共地址的控制器生成随本次安装保持稳定的本地地址；专有固件不会
复制进 Git 仓库。蓝牙配对、A2DP 实际播放以及麦克风长期录音仍需继续回归。

USB-C DisplayPort Alt Mode 的供电、Type-C 能力声明和内核协议驱动已加入；USB-C
转 HDMI 扩展坞由扩展坞将 DP 转换为 HDMI，仍需用新 boot.img 在真机完成 HPD、链路训练、
热插拔及 USB host 共存回归。rootfs 包含固定提交构建的 `qbootctl` 和延迟两分钟的槽位
确认服务；服务只在图形目标启动、根文件系统可写且当前槽等于活动槽时标记 successful。
高通 A/B 的 tries_remaining 字段上限是 7，不能设置“无限次数”；successful 标记才是
正常启动后停止递减的机制。

当前不能直接安装传统 PC 式 GRUB：一加 ABL 需要 Android header-v2 boot.img，而 GRUB
ARM64 需要提供 UEFI Boot Services 的固件和 ESP。若以后完成 ABL -> U-Boot/EDK2 -> GRUB
这一级引导移植，才可把 GRUB 用作二级菜单；现阶段仍使用 ABL 兼容 boot.img。

## 当前诊断组件

2026-09-12：新增独立 OP8 UFS 探测目标，已按原厂 DT 核对供电连接及范围，
并加入故意破坏配置的回归测试。GitHub 参考、差异及复现命令见
[适配记录](device/instantnoodle/GITHUB-ADAPTATION.md)。原 storage-disabled 目标保留。
UFS 版本仍未真机验证，父级连线部分来自 8 Pro 社区推断，不是可安装镜像。

`artifacts/diagnostic/` 保存独立 OP8 诊断设备树、约 6.8 MiB 的 initramfs、
静态核对记录和自动测试结果。设备树保留原机 23 个固定内存预留区间，
关闭 UFS、显示、GPU 及远端处理器，先尝试最小 USB 日志通路。
initramfs 不挂载手机存储、不开放 shell，也不自动重启。

主机测试覆盖 ARM64 用户态工具执行、脚本语法、PID 保护、cpio 内容与设备树约束；
不代表内核或 USB 已在真机工作。制作启动镜像前仍需核对引导器 DTB/DTBO 处理、
供电父级及安全退出路径，充电和温控尚未验证。
具体进度见 `STATUS.md`，限制见 `artifacts/diagnostic/DO-NOT-FLASH.md`。

三个 header-v2 镜像已可重复构建，位于 `artifacts/boot-images/`。它们使用明确标注的
LineageOS recovery ABL 外壳、嵌入式主线 DTB、copy-down shim 和 100 MiB `Algorithm: NONE`
AVB recovery footer。受保护的 fastboot 包装器先做临时启动；尚未写入手机分区。
操作顺序和回滚门槛见适配记录。

## 数据来源

- Kernel: https://gitlab.postmarketos.org/soc/qualcomm-sm8250/linux
- Pmaports: https://gitlab.postmarketos.org/postmarketOS/pmaports
- Rootfs: https://archlinuxarm.org/platforms/armv8/generic
- 工具链：内部系统已有 Clang/LLD/libLLVM 22.1.8，配套 LLVM 工具包单独解包到工程内，校验 SHA-256 与 GPG 签名，不安装/更改系统软件包。

开始时尝试复用 AOSP 工具链，但 SourceCode 外接盘中途掉线，复制未完成。`toolchains/clang-r596125` 是不可用的残留，当前脚本完全不使用它；不删除任何旧工程。

Arch rootfs 的 latest 名称会变化，下载完成后记录 SHA-256。归档的 MD5 仅作传输一致性校验，
不能冒充可信发布签名。未检查 rootfs 默认凭据之前不得对外开放 SSH；正式安装须设置自己的凭据/密钥。
普通用户解包只用于检查，不作为保留 uid/gid、ACL、capabilities 的部署 rootfs。

## 初始容量

2026-09-06 开始时 `/Data` 可用约 102 GiB；首轮预留 30–50 GiB。
构建前检查剩余空间及并发锁。未操作手机、未修改分区或清理旧工程。
