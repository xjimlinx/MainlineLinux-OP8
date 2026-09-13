# OnePlus 8 IN2010 — Arch Linux ARM bring-up

目标：原生 Linux + Arch Linux ARM 用户空间，不依赖 Android 运行。

本工程已完成 Linux 7.2 非 EFI 内核、OP8 专用诊断 DTB、RAM-only initramfs、
copy-down bootshim，以及 6 GiB Arch Linux ARM rootfs 镜像。
**真机已进入启动验证，但主线诊断内核尚未成功接管硬件，因此不得跳过诊断门槛直接刷入。**
禁止把 instantnoodlep（8 Pro）或 kebab（8T）的参考 DTB 当成 instantnoodle（8）的成品。
已有 Android/recovery 的恢复文件保留在 `/Work/Data/NX569J`，本工程不修改它们。

## 构建范围

1. 固定 SM8250 社区 Linux 7.2.0 源码与 postmarketOS 内核配置。
2. 在内部 NVMe 上构建 ARM64 Image、模块及上游参考 DTB，验证工具链。
3. 获取 Arch Linux ARM aarch64 rootfs，验证归档完整性并固定本地 SHA-256。
4. 独立核对 OP8 设备树、固件与 USB/initramfs；通过后才制作实验启动镜像。

`scripts/build-kernel.sh` 默认 `-j16`，关闭 DWARF/BTF 调试信息以降低初次构建的磁盘及内存需求。
日志在 `logs/`，内核输出在 `build/kernel/`，基线产物在 `artifacts/baseline/`。
此基线不是可刷写 OP8 的系统。

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
