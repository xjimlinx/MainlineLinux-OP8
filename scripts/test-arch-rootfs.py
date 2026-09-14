#!/usr/bin/env python3
"""Offline ext4/sparse/credential/boot linkage checks; no mount or phone I/O."""
from pathlib import Path
import hashlib
import json
import os
import stat
import struct
import subprocess

P = Path(__file__).resolve().parents[1]
out = P / 'artifacts/arch-rootfs'
raw = out / 'archlinux-in2010-rootfs.ext4'
sparse = out / 'archlinux-in2010-rootfs.sparse.img'
password_file = out / 'INITIAL-ROOT-PASSWORD.txt'
user_password_file = out / 'INITIAL-USER-PASSWORD.txt'
assert stat.S_IMODE(password_file.stat().st_mode) == 0o600
assert stat.S_IMODE(user_password_file.stat().st_mode) == 0o600
password = password_file.read_text().strip()
assert len(password) == 24 and all(c in '0123456789abcdef' for c in password)
assert subprocess.check_output(['blkid', '-s', 'LABEL', '-o', 'value', str(raw)], text=True).strip() == 'arch-root'
subprocess.run(['e2fsck', '-fn', str(raw)], check=True, stdout=subprocess.DEVNULL)

def debugfs(command):
    return subprocess.check_output(['debugfs', '-R', command, str(raw)], text=True, stderr=subprocess.DEVNULL)

shadow = debugfs('cat /etc/shadow')
accounts = {line.split(':', 1)[0]: line.split(':')[1] for line in shadow.splitlines()}
assert accounts['root'].startswith('$6$') and accounts['alarm'].startswith('!')
parts = accounts['root'].split('$')
verified = subprocess.check_output(['openssl', 'passwd', '-6', '-salt', parts[2], password], text=True).strip()
assert verified == accounts['root']
user_name, user_password = user_password_file.read_text().strip().split(':', 1)
assert len(user_password) == 16 and accounts[user_name].startswith('$')
assert 'Type: symlink' in debugfs('stat /sbin/init')
assert 'Type: symlink' in debugfs('stat /etc/systemd/system/getty.target.wants/serial-getty@ttyGS0.service')
assert 'Type: symlink' in debugfs('stat /etc/systemd/system/timers.target.wants/op8-bluetooth-setup.timer')
assert 'Type: regular' in debugfs('stat /etc/systemd/system/op8-bluetooth-setup-launch.service')
assert 'Type: regular' in debugfs('stat /usr/local/sbin/op8-bluetooth-setup')
assert 'Type: regular' in debugfs('stat /usr/local/bin/qbootctl')
assert 'Type: regular' in debugfs('stat /usr/local/sbin/op8-mark-slot-successful')
assert 'Type: regular' in debugfs('stat /usr/local/sbin/op8-typec-monitor')
assert 'Type: symlink' in debugfs('stat /etc/systemd/system/timers.target.wants/op8-mark-slot-successful.timer')
assert 'Type: regular' in debugfs('stat /usr/local/bin/op8-set-wallpaper')
assert 'Type: regular' in debugfs('stat /usr/share/applications/op8-set-wallpaper.desktop')
assert 'Type: regular' in debugfs('stat /usr/local/bin/op8-plasma-session')
assert 'Type: regular' in debugfs('stat /usr/local/sbin/op8-switch-plasma-session')
assert 'Type: regular' in debugfs('stat /opt/v2rayN/v2rayN')
assert 'Type: regular' in debugfs('stat /usr/share/applications/v2rayN.desktop')
assert 'Type: regular' in debugfs('stat /opt/wechat/wechat')
assert 'Type: symlink' in debugfs('stat /usr/bin/wechat')
assert 'Type: regular' in debugfs('stat /usr/share/applications/wechat.desktop')
assert 'Type: symlink' in debugfs('stat /usr/bin/codex')
assert 'Type: regular' in debugfs('stat /usr/share/plasma/shells/org.kde.plasma.mobileshell/contents/configuration/AppletConfiguration.qml')
assert 'Type: regular' in debugfs('stat /usr/share/plasma/shells/org.kde.plasma.mobileshell/contents/configuration/private/ChangeWallpaperModule.qml')
release = (P / 'artifacts/linux-7.2.5-op8/kernel.release').read_text().strip()
assert 'Type: directory' in debugfs(f'stat /usr/lib/modules/{release}')
assert 'Type: regular' in debugfs('stat /usr/lib/firmware/qcom/sm8250/OnePlus/a650_zap.mbn')
for path in ('/usr/bin/firefox', '/usr/bin/konsole', '/usr/bin/plasmashell'):
    assert 'Type: regular' in debugfs(f'stat {path}')
assert any(line.startswith('bluez-utils ') for line in (out / 'packages.lock').read_text().splitlines())
assert any(line.startswith('kdialog ') for line in (out / 'packages.lock').read_text().splitlines())

header = sparse.read_bytes()[:28]
magic, _, _, _, _, block_size, total_blocks, _, _ = struct.unpack('<I4H4I', header)
assert magic == 0xED26FF3A and block_size * total_blocks == raw.stat().st_size
manifest = dict(line.split('=', 1) for line in (out / 'provision.manifest').read_text().splitlines())
assert hashlib.file_digest(sparse.open('rb'), 'sha256').hexdigest() == manifest['sparse_sha256']
boot_manifest = json.loads((P / 'artifacts/linux-7.2.5-op8/boot-manifest.json').read_text())
assert boot_manifest['kernel_release'] == release and 'op8.arch=1' in boot_manifest['cmdline']
report = {'ext4_e2fsck': 'passed', 'label': 'arch-root', 'sparse_expanded_size': raw.stat().st_size,
          'root_password_matches_private_file': 'passed', 'alarm_locked': True,
          'systemd_and_ttyGS0_getty': 'present', 'matching_modules': release,
          'op8_bluetooth_boot_setup': 'present',
          'ab_slot_success_guard': 'present',
          'plasma_mobile_config_crash_workaround': 'present',
          'plasma_mobile_wallpaper_plugin_fallback': 'present',
          'plasma_session_switcher': 'present',
          'v2rayn_linux_arm64': 'present',
          'wechat_linux_arm64': 'present',
          'codex_cli_linux_arm64': 'present',
          'arch_boot_image_linkage': 'passed', 'phone_flash': 'NOT PERFORMED'}
(out / 'test-results.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
