# ARM64 应用部署记录

更新时间：2026-09-14

目标设备为 OnePlus 8（IN2010），当前系统为 Arch Linux ARM（`aarch64`）与 Plasma。本文记录桌面应用的架构判断、安装状态和复现路径，避免把 x86_64 软件包误装到手机。

## QQ

- 腾讯 Linux ARM64 安装包已下载到主机：`/tmp/QQ_3.2.32_260812_arm64_01.deb`
- SHA-256：`8796ccfd66acc025ef18db37185532d40bc8c58921e17da6d28c295acbcf8f92`
- 版本：`3.2.32-52194`，架构：`arm64`
- 当前状态：已安装到手机 `/opt/QQ`，版本 `3.2.32-52194`。
- 验证结果：`/opt/QQ/qq` 是 `ELF 64-bit LSB pie executable, ARM aarch64`；`ldd` 未报告缺失共享库；`/usr/share/applications/qq.desktop` 已安装。
- 图形界面登录验证：不在无 `DISPLAY/WAYLAND` 的 SSH 会话中强行启动 Electron；应从 Plasma 应用菜单点击 QQ 验证窗口和登录流程。

Arch Linux 不使用 `dpkg` 管理 Debian 包。安装时先用 `pacman` 补齐运行库，再把该包的数据归档解到系统中，随后检查 ARM64 ELF 和桌面启动项。安装结果必须用手机上的 `file`、`pacman -Q` 和启动命令验证。

本次实际部署命令（手机端）：

```sh
sudo pacman -S --needed gtk3 libnotify nss libxss libxtst xdg-utils \
  at-spi2-core util-linux-libs libsecret libappindicator
mkdir -p /tmp/qq-deb-unpack
cd /tmp/qq-deb-unpack
ar x /tmp/QQ_3.2.32_260812_arm64_01.deb data.tar.xz
sudo tar -xJf data.tar.xz -C /
```

## Steam

当前没有可直接安装的原生 ARM64 Steam Linux 客户端。Valve 官方 Steam 仓库的架构范围是 `amd64,i386`，当前稳定包也只有 `amd64`/`all` 组合。因此不能把 PC 版 Steam 包直接装到本机 `aarch64` 系统。

后续若需要 Steam，需要单独评估 Box64/FEX 等 x86_64 兼容层、Steam Runtime、图形驱动和 Proton；这不是原生安装，暂不部署。

## WPS Office

WPS 普通 Linux 下载页的 X64 包不是全部选项；该页明确将 ARM 等架构引导到 WPS 365。WPS 365 当前提供 Linux ARM64 测试包：

- 版本：`12.1.2.28080.AK.preread.sw`，构建 `765470`
- 官方 CDN：`https://pubwps-wps365-obs.wpscdn.cn/download/Linux/28080/wps-office_12.1.2.28080.AK.preread.sw.365_765470_arm64.deb`
- SHA-256：`62c0ee6b69d998b01bcea3112d3d2c40c815c0c107c0a5c06509eaf2adf6c2bd`
- 当前状态：已安装到手机 `/opt/kingsoft/wps-office`，`wps`、`et`、`wpp`、`wpspdf` 均为 ARM64 ELF，桌面入口已刷新。

本次使用项目脚本 [`scripts/install-wps365-arm64.sh`](../scripts/install-wps365-arm64.sh) 解包并运行厂商 `postinst`；由于系统是 Arch Linux ARM，未使用 `dpkg` 注册包。

WPS 365 ARM 包仍标为 testing，首次启动和登录应从 Plasma 应用菜单执行 `/usr/bin/wps`，不要在无图形 SSH 会话中强行启动。

## Blender / OBS Studio

- Arch Linux ARM 当前仓库没有 `blender` 或 `obs-studio` 原生包。
- Blender 官方下载页当前提供 Linux x86_64 包，ARM 下载项主要是 Windows ARM；在本机直接安装官方 Linux 包不可行。后续可评估源码编译，但手机 GPU、内存和编译时间会是主要限制。
- OBS Studio 没有可直接安装的 ARM64 Linux 官方发行包；源码可以尝试编译，浏览器/CEF、硬件编码和采集插件需要单独适配。暂不安装不匹配的 x86_64 包。

## 本次验证清单

```sh
# 手机架构和发行版
ssh xein@172.16.42.1 'uname -m; cat /etc/os-release | sed -n "1,6p"'

# QQ 依赖（手机上执行）
sudo pacman -S --needed gtk3 libnotify nss libxss libxtst xdg-utils \
  at-spi2-core util-linux-libs libsecret libappindicator-gtk3

# 安装后验证（手机上执行）
file /opt/QQ/*/qq 2>/dev/null || true
command -v linuxqq || true
```

安装脚本必须保留在项目或命令记录中，不能依赖主机的 `dpkg` 状态；这样换设备或重新部署时仍可复现。
