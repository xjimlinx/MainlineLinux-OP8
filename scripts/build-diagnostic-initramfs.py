"""Build a root-owned cpio without root privileges, using kernel gen_init_cpio.

Only copies pinned Arch files and exactly three matching baseline USB modules.
No phone operations, guest code execution, rootfs installation or host mounts.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import tarfile

P = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--mode', choices=('diagnostic', 'arch'), default='diagnostic')
args = parser.parse_args()
mode = args.mode
archive = P / 'downloads/ArchLinuxARM-aarch64-latest.tar.gz'
expected = '42a4eeaa038994ffd31fa173256ef2f0ef511358eeb41b9ea1f8626391b9b319'
assert hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest() == expected
root = P / f'build/{mode}-initramfs/root'
out = P / f'artifacts/{mode if mode == "diagnostic" else "arch-rootfs"}'
root.mkdir(parents=True, exist_ok=True)
out.mkdir(parents=True, exist_ok=True)
for name in ('bin', 'lib', 'usr', 'dev', 'proc', 'sys', 'run', 'config', 'modules'):
    (root / name).mkdir(exist_ok=True)
# Arch's dynamic linker searches /usr/lib; keep both standard paths valid.
if not (root / 'usr/lib').is_symlink():
    (root / 'usr/lib').symlink_to('../lib')
selected = {
    './usr/lib/initcpio/busybox': 'bin/busybox',
    './usr/bin/mount': 'bin/mount',
    './usr/bin/kmod': 'bin/kmod',
    './usr/lib/ld-linux-aarch64.so.1': 'lib/ld-linux-aarch64.so.1',
    './usr/lib/libc.so.6': 'lib/libc.so.6',
    './usr/lib/libcrypt.so.2.0.0': 'lib/libcrypt.so.2',
}
if mode == 'arch':
    selected.update({
        './usr/bin/blkid': 'bin/blkid',
        './usr/bin/switch_root': 'bin/switch_root',
    })
with tarfile.open(archive, 'r:gz') as tf:
    members = {m.name.removeprefix('./'): m for m in tf.getmembers()}
    def copy_member(name, dest):
        if dest.is_symlink():
            assert dest == root / 'bin/mount' and os.readlink(dest) == 'busybox'
            dest.unlink()  # Only the known generated prototype link.
        name = name.removeprefix('./')
        for _ in range(20):
            member = members[name]
            if member.isfile():
                break
            assert member.issym(), f'Unsupported archive member: {name}'
            name = posixpath.normpath(posixpath.join(posixpath.dirname(name), member.linkname))
            assert name.startswith(('usr/lib/', 'usr/bin/')), name
        else:
            raise ValueError('Archive symlink cycle')
        with tf.extractfile(member) as src, dest.open('wb') as target:
            shutil.copyfileobj(src, target)
        dest.chmod(0o755)
    for name, dest in selected.items():
        copy_member(name, root / dest)
    # Arch mkinitcpio's BusyBox omits mount and insmod. Include the actual
    # util-linux mount/kmod programs and their complete DT_NEEDED closure.
    queue = [root / dest for dest in selected.values()]
    visited = set()
    while queue:
        binary = queue.pop()
        if binary in visited:
            continue
        visited.add(binary)
        dynamic = subprocess.check_output(['readelf', '-d', '-W', str(binary)], text=True)
        for soname in re.findall(r'\(NEEDED\).*?\[(.*?)\]', dynamic):
            assert '/' not in soname
            dest = root / 'lib' / soname
            if not dest.exists():
                copy_member('usr/lib/' + soname, dest)
            queue.append(dest)
for dest in selected.values():
    assert (root / dest).is_file(), dest
shutil.copyfile(P / 'device/instantnoodle' / ('diagnostic-init' if mode == 'diagnostic' else 'arch-init'), root / 'init')
(root / 'init').chmod(0o755)
applets = ('sh', 'mkdir', 'ln', 'sleep', 'cat', 'uname', 'dmesg', 'sync')
for name in applets:
    link = root / 'bin' / name
    if not link.is_symlink():
        link.symlink_to('busybox')
# Replace only the generated earlier prototype's BusyBox insmod symlink.
insmod = root / 'bin/insmod'
if insmod.is_symlink() and os.readlink(insmod) == 'busybox':
    insmod.unlink()
if not insmod.is_symlink():
    insmod.symlink_to('kmod')
kernel_artifacts = P / ('artifacts/in2010-kernel' if (P / 'artifacts/in2010-kernel/Image').exists()
                        else 'artifacts/baseline')
release = (kernel_artifacts / 'kernel.release').read_text().strip()
module_base = kernel_artifacts / 'modules/lib/modules' / release
module_names = ('libcomposite', 'u_serial', 'usb_f_acm')
for name in module_names:
    matches = list(module_base.rglob(name + '.ko.zst'))
    assert len(matches) == 1, (name, matches)
    with (root / 'modules' / (name + '.ko')).open('wb') as f:
        subprocess.run(['zstd', '-q', '-d', '-c', str(matches[0])], stdout=f, check=True)
    vermagic = subprocess.check_output(['modinfo', '-F', 'vermagic', str(root / 'modules' / (name + '.ko'))], text=True)
    assert vermagic.split()[0] == release

manifest = []
for path in sorted(root.rglob('*')):
    rel = '/' + str(path.relative_to(root))
    if path.is_symlink():
        manifest.append(f'slink {rel} {os.readlink(path)} 777 0 0')
    elif path.is_dir():
        manifest.append(f'dir {rel} 755 0 0')
    else:
        file_mode = '755' if path.stat().st_mode & 0o111 else '644'
        manifest.append(f'file {rel} {path} {file_mode} 0 0')
manifest += ['nod /dev/console 600 0 0 c 5 1', 'nod /dev/null 666 0 0 c 1 3']
manifest_path = P / f'build/{mode}-initramfs/cpio.list'
manifest_path.write_text('\n'.join(manifest) + '\n')
cpio = out / f'initramfs-{mode}.cpio'
with cpio.open('wb') as f:
    subprocess.run([str(P / 'build/kernel/usr/gen_init_cpio'), '-t', '0', str(manifest_path)], stdout=f, check=True)
with (out / f'initramfs-{mode}.cpio.gz').open('wb') as f:
    subprocess.run(['gzip', '-n', '-c', str(cpio)], stdout=f, check=True)
record = {'kernel_release': release, 'arch_rootfs_sha256': expected,
          'modules': module_names, 'applets_required': applets,
          'files': {str(p.relative_to(root)): hashlib.file_digest(p.open('rb'), 'sha256').hexdigest()
                    for p in root.rglob('*') if p.is_file() and not p.is_symlink()},
          'mode': mode, 'phone_validated': False,
          'opens_shell': mode == 'arch', 'mounts_block_devices': mode == 'arch'}
manifest_name = 'initramfs-manifest.json' if mode == 'diagnostic' else 'initramfs-arch-manifest.json'
(out / manifest_name).write_text(json.dumps(record, indent=2) + '\n')
print(f'Created {mode} cpio for {release}; no phone operation.')
