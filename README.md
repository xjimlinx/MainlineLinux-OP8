# OnePlus 8 IN2010 — Arch Linux ARM bring-up

目标：原生 Linux + Arch Linux ARM 用户空间，不依赖 Android 运行。

本工程已完成并在 IN2010 真机启动 Linux 7.2.5、OP8 专用 DTB、
Arch Linux ARM、Plasma Mobile、USB ACM/NCM 及 freedreno GPU。
2026-09-14 已验证带 AVB footer 的镜像可以从 A 槽持久启动，并已将 A 槽标记为
active、successful、bootable；完整刷写记录、哈希、验证和恢复入口见
[A 槽持久启动记录](docs/PERSISTENT-BOOT-A.md)。Linux 最终关机/硬件复位偶尔卡住仍是
独立的待修问题，不代表 A 槽镜像未固化。
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
bash scripts/fetch-v2rayn.sh
bash scripts/fetch-wechat.sh

# 构建 7.2.5-op8-mainline、DTB 与模块
OP8_JOBS=16 bash scripts/build-linux-7.2.5-op8.sh

# 构建基础 ext4/sparse rootfs，再安装 Plasma、Firefox、Konsole、Codex CLI 等
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

Plasma Mobile 与 Plasma Desktop 是两个独立的 Wayland 会话，不能在保留窗口的情况下
原地变成类似 DeX 的 PC 模式。现在由 SDDM 的 OP8-Breeze QML greeter 提供触摸友好的图形登录界面，
会列出“Plasma Mobile（手机模式）”和“Plasma（桌面模式）”两个会话，可在登录前点击选择；
系统同时安装两者，并提供“切换手机/桌面模式”应用：它会保存目标模式并让 SDDM 重新建立图形会话，
不重启手机；切换会关闭当前所有窗口，需要先保存工作。SDDM 登录器当前使用 X11 作为稳定的显示层，
登录后的 Plasma 会话仍然是 Wayland。SDDM 没有单独的“Mobile 版”，手机体验由 Plasma Mobile 会话和
可替换的 QML 主题决定。OP8-Breeze 将 greeter 缩放设为 2 倍，安装 Qt Virtual Keyboard，
密码框获得焦点后会自动弹出中文/英文虚拟键盘；键盘顶部保留登录器会话选择入口。命令行也可使用
`sudo /usr/local/sbin/op8-switch-plasma-session mobile|desktop`。

rootfs 同时安装固定版本的 Linux ARM64 Codex CLI、Node.js、Git 与 ripgrep。首次使用时
在 Konsole 中运行 `codex login`（或设置自己的 `OPENAI_API_KEY`）；登录状态属于手机用户，
不会被构建脚本写入镜像或 Git。可在构建时用 `OP8_CODEX_VERSION=x.y.z` 显式选择其他版本。
系统也包含固定版本和 SHA-256 的官方 v2rayN Linux ARM64 便携包，应用菜单可直接启动；
订阅地址、节点和认证信息只保存在用户目录，不进入仓库。
中文输入使用 Fcitx 5、中文扩展与拼音词库，KWin 通过 Wayland 输入法接口启动它；
默认用 `Ctrl+Space` 在英文键盘与拼音之间切换，配置工具为 `fcitx5-configtool`。
会话切换器在 PC 桌面模式选择 Fcitx 5，在 Mobile 模式恢复自带 Plasma Keyboard；
后者包含 Qt Pinyin 插件，因此不会因为安装 Fcitx 而丢失手机触屏键盘。
腾讯官方 Linux ARM64 微信也按版本与 SHA-256 固定安装；首次启动显示二维码，账号数据仅
保存在图形用户的主目录，不会进入构建仓库或生成的公共输入文件。

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
