#!/usr/bin/env bash
# Reproduce the tested Linux 7.2.5 + Arch/Plasma images from a clean checkout.
set -euo pipefail

project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
jobs=${OP8_JOBS:-16}

bash "$project/scripts/check-host.sh"
bash "$project/scripts/fetch-linux-7.2.5-op8.sh"
bash "$project/scripts/fetch-device-assets.sh"
bash "$project/scripts/fetch-qbootctl.sh"
bash "$project/scripts/fetch-rootfs.sh"
bash "$project/scripts/fetch-v2rayn.sh"
bash "$project/scripts/fetch-wechat.sh"
OP8_JOBS="$jobs" bash "$project/scripts/build-linux-7.2.5-op8.sh"
bash "$project/scripts/build-arch-rootfs.sh"

if ((EUID == 0)); then
	bash "$project/scripts/provision-arch-deploy.sh"
else
	command -v pkexec >/dev/null 2>&1 || {
		echo 'pkexec is required to mount and provision the rootfs image.' >&2
		exit 1
	}
	pkexec bash "$project/scripts/provision-arch-deploy.sh"
fi

python3 "$project/scripts/build-diagnostic-initramfs.py" --mode arch
python3 "$project/scripts/build-linux-7.2.5-boot.py"
python3 "$project/scripts/test-arch-rootfs.py"
(cd "$project/artifacts/linux-7.2.5-op8" && sha256sum -c SHA256SUMS)
(cd "$project/artifacts/arch-rootfs" && sha256sum -c SHA256SUMS)
echo "Reproduction complete: $project/artifacts/linux-7.2.5-op8/boot-in2010-linux-7.2.5.img"
