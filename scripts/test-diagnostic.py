"""Host-only tests: guest utilities under qemu-user, cpio metadata, DT invariants.

Does not emulate a phone/kernel or execute the PID 1 startup/mount path.
"""
from pathlib import Path
import hashlib
import json
import stat
import subprocess

P = Path(__file__).resolve().parents[1]
root = P / 'build/diagnostic-initramfs/root'
qemu = P / 'toolchains/qemu-test/usr/bin/qemu-aarch64-static'
base = [str(qemu), '-L', str(root), str(root / 'bin/busybox')]
applets = set(subprocess.check_output(base + ['--list'], text=True).splitlines())
manifest = json.loads((P / 'artifacts/diagnostic/initramfs-manifest.json').read_text())
assert set(manifest['applets_required']) <= applets
assert subprocess.check_output(base + ['echo', 'OP8-AARCH64-SMOKE-OK'], text=True).strip() == 'OP8-AARCH64-SMOKE-OK'
for name in ('mount', 'kmod'):
    subprocess.run([str(qemu), '-L', str(root), str(root / 'bin' / name), '--version'], check=True)
subprocess.run(base + ['sh', '-n', str(root / 'init')], check=True)
guard = subprocess.run(base + ['sh', str(root / 'init')], text=True, capture_output=True)
assert guard.returncode == 1 and 'outside PID 1' in guard.stderr

cpio = (P / 'artifacts/diagnostic/initramfs-diagnostic.cpio').read_bytes()
entries = {}
offset = 0
while True:
    header = cpio[offset:offset + 110]
    assert header[:6] == b'070701'
    fields = [int(header[i:i+8], 16) for i in range(6, 110, 8)]
    _, mode, uid, gid, _, _, size, _, _, major, minor, namesize, _ = fields
    start = offset + 110
    name = cpio[start:start + namesize - 1].decode()
    offset = (start + namesize + 3) & ~3
    data = cpio[offset:offset+size]
    offset = (offset + size + 3) & ~3
    if name == 'TRAILER!!!':
        break
    assert uid == 0 and gid == 0, name
    assert not name.startswith('/') and '..' not in Path(name).parts
    assert name not in entries, name
    entries[name] = {'mode': mode, 'major': major, 'minor': minor, 'data': data}
assert stat.S_ISCHR(entries['dev/console']['mode'])
assert (entries['dev/console']['major'], entries['dev/console']['minor']) == (5, 1)
assert entries['init']['mode'] & 0o111
assert entries['usr/lib']['data'].rstrip(b'\0') == b'../lib'
for name, digest in manifest['files'].items():
    assert hashlib.sha256(entries[name]['data']).hexdigest() == digest, name
subprocess.run(['python3', str(P / 'scripts/audit-diagnostic-board.py')], check=True)
report = {'arm64_busybox_exec': 'passed', 'required_applets': 'passed',
          'arm64_mount_and_kmod_exec': 'passed',
          'init_syntax': 'passed', 'host_execution_guard': 'passed',
          'root_owned_cpio_and_hashes': 'passed', 'cpio_entries': len(entries),
          'board_static_invariants': 'passed', 'phone_boot': 'NOT TESTED',
          'kernel_emulation': 'NOT TESTED', 'full_dt_schema_validation': 'NOT TESTED'}
(P / 'artifacts/diagnostic/test-results.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
