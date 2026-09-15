#!/usr/bin/env python3
"""Guarded IN2010 temporary boot / single-slot recovery flash wrapper."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time

P = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=('inspect', 'boot', 'flash-boot-a',
                                      'flash-noslpi-a',
                                      'flash-recovery', 'restore-recovery',
                                      'flash-arch-userdata'))
parser.add_argument('--variant', choices=('diagnostic', 'storage-probe', 'arch'), default='diagnostic')
parser.add_argument('--serial', help='Required when multiple devices exist')
parser.add_argument('--reboot', action='store_true',
                    help='Reboot after a successful persistent boot_a flash')
parser.add_argument('--capture-timeout', type=int, default=120,
                    help='Seconds to wait for diagnostic ttyACM after temporary boot')
args = parser.parse_args()
base = ['fastboot'] + (['-s', args.serial] if args.serial else [])

devices = [line.split() for line in subprocess.check_output(['fastboot', 'devices'], text=True).splitlines()]
if not devices:
    sys.exit('No fastboot device connected. Image remains host-side only.')
assert len(devices) == 1 or args.serial, f'expected one device, found {len(devices)}; use --serial'
serial = args.serial or devices[0][0]
expected_serial = 'd967403e'
if serial != expected_serial:
    sys.exit(f'Refusing non-target device {serial}; expected recorded IN2010 {expected_serial}')
base = ['fastboot', '-s', serial]
def var(name):
    p = subprocess.run(base + ['getvar', name], text=True, capture_output=True)
    text = p.stdout + p.stderr
    m = re.search(rf'(?:\(bootloader\) )?{re.escape(name)}:\s*(\S+)', text)
    if p.returncode or not m:
        sys.exit(f'Cannot read fastboot variable {name}: {text.strip()}')
    return m.group(1)

unlocked = var('unlocked')
slot = var('current-slot')
userspace = var('is-userspace')
product = var('product')
if unlocked.lower() not in ('yes', 'true'):
    sys.exit(f'Bootloader is not unlocked: {unlocked}')
if slot not in ('a', 'b'):
    sys.exit(f'Unexpected current slot: {slot}')
print(json.dumps({'serial': serial, 'product': product, 'unlocked': unlocked,
                  'current_slot': slot, 'is_userspace': userspace}, indent=2))
if args.action == 'inspect':
    raise SystemExit(0)

if args.action == 'flash-noslpi-a':
    if userspace.lower() == 'yes':
        sys.exit('Persistent boot flashing requires bootloader fastboot, not fastbootd.')
    if product != 'kona':
        sys.exit(f'Refusing non-SM8250 product: {product}')
    partition_size = var('partition-size:boot_a')
    try:
        if int(partition_size, 0) != 96 * 1024 * 1024:
            sys.exit(f'Unexpected boot_a size: {partition_size}')
    except ValueError:
        sys.exit(f'Cannot parse boot_a size: {partition_size}')
    boot_art = P / 'artifacts/boot-images/noslpi'
    boot = boot_art / 'boot-in2010-noslpi-avb.img'
    manifest_path = boot_art / 'manifest.json'
    if not boot.is_file() or not manifest_path.is_file():
        sys.exit('Noslpi persistent artifact or its manifest is missing.')
    manifest = json.loads(manifest_path.read_text())
    expected_boot = manifest.get('persistent_boot_sha256')
    actual_boot = hashlib.file_digest(boot.open('rb'), 'sha256').hexdigest()
    if actual_boot != expected_boot:
        sys.exit(f'Noslpi boot hash mismatch: {actual_boot} != {expected_boot}')
    if boot.stat().st_size != 96 * 1024 * 1024:
        sys.exit(f'Noslpi boot image has wrong size: {boot.stat().st_size}')
    avb_info = subprocess.run(['avbtool', 'info_image', '--image', str(boot)],
                              check=True, text=True, capture_output=True).stdout
    if ('Image size:               100663296 bytes' not in avb_info or
            'Partition Name:        boot' not in avb_info):
        sys.exit('Noslpi persistent image failed AVB footer validation.')
    vbmeta = P.parent / 'AOSP-OP8/out/target/product/instantnoodle/vbmeta.img'
    expected_vbmeta = '1240bb219395fc0ceb0df56e61cab5a00aed72607479fc42867c08dfd11b93d0'
    if not vbmeta.is_file():
        sys.exit(f'Missing AOSP vbmeta image: {vbmeta}')
    actual_vbmeta = hashlib.file_digest(vbmeta.open('rb'), 'sha256').hexdigest()
    if actual_vbmeta != expected_vbmeta:
        sys.exit(f'vbmeta hash mismatch: {actual_vbmeta} != {expected_vbmeta}')
    print(f'Writing only vbmeta_a and boot_a for noslpi; boot={actual_boot}')
    subprocess.run(base + ['flash', 'vbmeta_a', str(vbmeta)], check=True)
    subprocess.run(base + ['flash', 'boot_a', str(boot)], check=True)
    subprocess.run(base + ['set_active', 'a'], check=True)
    print('Noslpi A-slot image installed; boot_b and userdata were not touched.')
    if args.reboot:
        subprocess.run(base + ['reboot'], check=True)
    else:
        print('Not rebooting automatically (pass --reboot after reviewing the flash output).')
    raise SystemExit(0)

if args.action == 'flash-boot-a':
    if userspace.lower() == 'yes':
        sys.exit('Persistent boot flashing requires bootloader fastboot, not fastbootd.')
    if product != 'kona':
        sys.exit(f'Refusing non-SM8250 product: {product}')
    partition_size = var('partition-size:boot_a')
    try:
        if int(partition_size, 0) != 96 * 1024 * 1024:
            sys.exit(f'Unexpected boot_a size: {partition_size}')
    except ValueError:
        sys.exit(f'Cannot parse boot_a size: {partition_size}')

    boot_art = P / 'artifacts/linux-7.2.5-op8'
    boot = boot_art / 'persistent/boot-in2010-linux-7.2.5-avb.img'
    manifest = json.loads((boot_art / 'boot-manifest.json').read_text())
    expected_boot = manifest.get('persistent_boot_sha256')
    if not expected_boot or not boot.is_file():
        sys.exit('Persistent 7.2.5 AVB artifact or its manifest entry is missing.')
    actual_boot = hashlib.file_digest(boot.open('rb'), 'sha256').hexdigest()
    if actual_boot != expected_boot:
        sys.exit(f'Persistent boot hash mismatch: {actual_boot} != {expected_boot}')
    if boot.stat().st_size != 96 * 1024 * 1024:
        sys.exit(f'Persistent boot image has wrong size: {boot.stat().st_size}')
    avb_info = subprocess.run(['avbtool', 'info_image', '--image', str(boot)],
                              check=True, text=True, capture_output=True).stdout
    if ('Image size:               100663296 bytes' not in avb_info or
            'Partition Name:        boot' not in avb_info):
        sys.exit('Persistent boot image failed AVB footer validation.')

    vbmeta = P.parent / 'AOSP-OP8/out/target/product/instantnoodle/vbmeta.img'
    expected_vbmeta = '1240bb219395fc0ceb0df56e61cab5a00aed72607479fc42867c08dfd11b93d0'
    if not vbmeta.is_file():
        sys.exit(f'Missing AOSP vbmeta image: {vbmeta}')
    actual_vbmeta = hashlib.file_digest(vbmeta.open('rb'), 'sha256').hexdigest()
    if actual_vbmeta != expected_vbmeta:
        sys.exit(f'vbmeta hash mismatch: {actual_vbmeta} != {expected_vbmeta}')
    print(f'Writing only vbmeta_a and boot_a on unlocked IN2010; boot={actual_boot}')
    subprocess.run(base + ['flash', 'vbmeta_a', str(vbmeta)], check=True)
    subprocess.run(base + ['flash', 'boot_a', str(boot)], check=True)
    subprocess.run(base + ['set_active', 'a'], check=True)
    print('A-slot persistent boot image installed; boot_b and userdata were not touched.')
    if args.reboot:
        subprocess.run(base + ['reboot'], check=True)
    else:
        print('Not rebooting automatically (pass --reboot after reviewing the flash output).')
    raise SystemExit(0)

artifact = P / 'artifacts/boot-images' / args.variant
image = artifact / f'boot-in2010-{args.variant}.img'
manifest = json.loads((artifact / 'manifest.json').read_text())
actual = hashlib.file_digest(image.open('rb'), 'sha256').hexdigest()
assert actual == manifest['boot_image_sha256']
assert manifest['target'].startswith('OnePlus 8 IN2010')
if args.action == 'boot':
    if userspace.lower() == 'yes':
        sys.exit('Temporary boot requires bootloader fastboot, not fastbootd.')
    print('Temporary boot: no partition write requested.')
    before = set(Path('/dev').glob('ttyACM*'))
    subprocess.run(base + ['boot', str(image)], check=True)
    if args.variant != 'arch':
        print(f'Waiting up to {args.capture_timeout}s for OP8 diagnostic USB ACM...')
        deadline = time.monotonic() + args.capture_timeout
        tty = None
        while time.monotonic() < deadline:
            candidates = set(Path('/dev').glob('ttyACM*'))
            fresh = candidates - before
            if fresh:
                tty = sorted(fresh)[0]
                break
            time.sleep(1)
        if tty is None:
            sys.exit('No new ttyACM appeared; temporary boot is not validated.')
        log = P / 'logs' / f'phone-{args.variant}-ttyACM.log'
        with log.open('wb') as output:
            subprocess.run(['timeout', '25s', 'cat', str(tty)], stdout=output,
                           stderr=subprocess.STDOUT, check=False)
        print(f'Captured diagnostic transport {tty} to {log}')
elif args.action in ('flash-recovery', 'restore-recovery'):
    if userspace.lower() == 'yes':
        sys.exit('Recovery-slot flashing requires bootloader fastboot, not fastbootd.')
    restores = {
        'a': P / 'artifacts/device-baseline/lineage-recovery_a.img',
    }
    restore = restores.get(slot, Path('/nonexistent'))
    if not restore.exists():
        sys.exit(f'No verified recovery rollback for active slot: {restore}')
    expected = {'a': 'd3bf874fa1c416d40c5392e31e45ae1c4b426c8b498a40d7a7c3288ef1c6b981'}.get(slot)
    if not expected or hashlib.file_digest(restore.open('rb'), 'sha256').hexdigest() != expected:
        sys.exit(f'Active-slot rollback is not pinned/verified for slot {slot}; refusing flash.')
    target = image if args.action == 'flash-recovery' else restore
    print(f'Writing only recovery_{slot}; source={target}; rollback={restore}')
    subprocess.run(base + ['flash', f'recovery_{slot}', str(target)], check=True)
    print('Flash completed. Not rebooting automatically.')
else:
    if args.variant != 'arch':
        sys.exit('flash-arch-userdata requires --variant arch')
    if userspace.lower() != 'yes':
        sys.exit('Arch userdata flashing requires recovery fastbootd (is-userspace=yes).')
    sparse = P / 'artifacts/arch-rootfs/archlinux-in2010-rootfs.sparse.img'
    root_manifest = dict(line.split('=', 1) for line in
                         (P / 'artifacts/arch-rootfs/rootfs.manifest').read_text().splitlines())
    assert hashlib.file_digest(sparse.open('rb'), 'sha256').hexdigest() == root_manifest['sparse_sha256']
    raw_size = int(root_manifest['raw_size'])
    part_text = var('partition-size:userdata')
    try:
        part_size = int(part_text, 0)
    except ValueError:
        sys.exit(f'Cannot parse userdata size: {part_text}')
    if part_size < raw_size:
        sys.exit(f'userdata is too small: {part_size} < {raw_size}')
    print(f'ERASING USERDATA CONTENTS by writing {sparse}; expanded size={raw_size}, partition={part_size}')
    subprocess.run(base + ['-S', '256M', 'flash', 'userdata', str(sparse)], check=True)
    print('Arch rootfs write completed. Not rebooting automatically.')
