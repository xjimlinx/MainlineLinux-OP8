"""Assert offline board invariants; not a substitute for hardware validation."""
from pathlib import Path
import json
import subprocess
import argparse

P = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--variant', choices=('diagnostic', 'storage-probe'), default='diagnostic')
parser.add_argument('--dtb', type=Path, help='Audit another blob; do not publish a report')
args = parser.parse_args()
ref = P / 'build/board-audit/android-merged.dtb'
dtb = args.dtb or P / f'artifacts/{args.variant}/instantnoodle-{args.variant}.dtb'

def get(blob, path, prop, kind='x'):
    r = subprocess.run(['fdtget', '-t', kind, str(blob), path, prop], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None

def children(blob, path):
    return subprocess.check_output(['fdtget', '-l', str(blob), path], text=True).splitlines()

def ranges(blob):
    result = []
    for name in children(blob, '/reserved-memory'):
        path = '/reserved-memory/' + name
        raw = get(blob, path, 'reg')
        if raw is None:
            continue
        cells = [int(c, 16) for c in raw.split()]
        assert len(cells) % 4 == 0
        for i in range(0, len(cells), 4):
            start = (cells[i] << 32) | cells[i + 1]
            size = (cells[i + 2] << 32) | cells[i + 3]
            result.append({'node': path, 'start': start, 'size': size, 'end': start + size})
    return sorted(result, key=lambda r: r['start'])

original, proposed = ranges(ref), ranges(dtb)
for a, b in zip(proposed, proposed[1:]):
    assert a['end'] <= b['start'], f'Overlapping diagnostic reservations: {a} {b}'
coverage = []
for old in original:
    covered = any(new['start'] <= old['start'] and new['end'] >= old['end'] for new in proposed)
    assert covered, f'Unreserved original fixed memory: {old}'
    coverage.append({'original': old['node'], 'covered': covered})

disabled = ('ufs_mem_hc', 'ufs_mem_phy', 'usb_2', 'mdss', 'gpu', 'gmu', 'adsp', 'cdsp', 'slpi',
            'venus', 'pm8150b_charger', 'pm8150b_vbus', 'pm8150b_typec')
if args.variant == 'storage-probe':
    disabled = disabled[2:]
for label in disabled:
    path = get(dtb, '/__symbols__', label, 's')
    assert path and get(dtb, path, 'status', 's') == 'disabled', label
usb = get(dtb, '/__symbols__', 'usb_1_dwc3', 's')
assert get(dtb, usb, 'dr_mode', 's') == 'peripheral'
assert get(dtb, usb, 'maximum-speed', 's') == 'high-speed'
assert get(dtb, '/', 'oplus,dtsi_no', 'u') == '19821'
assert get(dtb, '/', 'qcom,msm-id') == get(ref, '/', 'qcom,msm-id')
assert get(dtb, '/', 'qcom,board-id') == '0 0'

supplies = []
for old_label, new_label in (('pm8150_l2', 'vreg_l2a_3p1'), ('pm8150_l5', 'vreg_l5a_0p88'),
                             ('pm8150_l12', 'vreg_l12a_1p8')):
    a = get(ref, '/__symbols__', old_label, 's')
    b = get(dtb, '/__symbols__', new_label, 's')
    assert a and b
    for prop in ('regulator-min-microvolt', 'regulator-max-microvolt'):
        assert get(ref, a, prop) == get(dtb, b, prop), (old_label, prop)
    supplies.append({'downstream': old_label, 'mainline': new_label,
                     'microvolts': get(dtb, b, 'regulator-min-microvolt', 'u')})

report = {'fixed_reservation_coverage': coverage, 'reference_ranges': original,
          'diagnostic_ranges': proposed, 'disabled_devices': disabled,
          'usb_supplies': supplies, 'usb_mode': 'peripheral/high-speed',
          'syntax_and_invariants_passed': True, 'hardware_validated': False,
          'not_checked': ['bootloader DTBO policy', 'USB electrical/role behavior',
                          'regulator parent rails', 'thermal/charging behavior',
                          'PMIC hardware reset behavior', 'memory changes applied by bootloader']}
if args.variant == 'storage-probe':
    def symbol(blob, label):
        path = get(blob, '/__symbols__', label, 's')
        assert path, label
        return path

    def linked(blob, consumer, prop, provider):
        assert get(blob, symbol(blob, consumer), prop) == get(
            blob, symbol(blob, provider), 'phandle'), (consumer, prop, provider)

    rails = (
        ('pm8150_s4', 'vreg_s4a'), ('pm8150_s5', 'vreg_s5a'),
        ('pm8150_s6', 'vreg_s6a'), ('pm8150_l6', 'vreg_l6a'),
        ('pm8150_l9', 'vreg_l9a'), ('pm8150_l17', 'vreg_l17a'),
        ('pm8150a_s8', 'vreg_s8c'), ('pm8150a_bob', 'vreg_bob'))
    checked_rails = []
    for old, new in rails:
        bounds = lambda blob, label: tuple(int(get(blob, symbol(blob, label), p, 'u'))
            for p in ('regulator-min-microvolt', 'regulator-max-microvolt'))
        lo, hi = bounds(ref, old)
        nlo, nhi = bounds(dtb, new)
        assert lo <= nlo <= nhi <= hi, (old, (lo, hi), (nlo, nhi))
        checked_rails.append({'original': old, 'candidate': new,
                              'original_uv': [lo, hi], 'candidate_uv': [nlo, nhi]})

    # Check the actual original consumer phandles, not just similar rail names.
    mapping = (
        ('ufshc_mem', 'ufs_mem_hc', 'vcc-supply', 'pm8150_l17', 'vreg_l17a'),
        ('ufshc_mem', 'ufs_mem_hc', 'vccq-supply', 'pm8150_l6', 'vreg_l6a'),
        ('ufshc_mem', 'ufs_mem_hc', 'vccq2-supply', 'pm8150_s4', 'vreg_s4a'),
        ('ufsphy_mem', 'ufs_mem_phy', 'vdda-phy-supply', 'pm8150_l5', 'vreg_l5a_0p88'),
        ('ufsphy_mem', 'ufs_mem_phy', 'vdda-pll-supply', 'pm8150_l9', 'vreg_l9a'))
    for old, new, prop, old_rail, new_rail in mapping:
        linked(ref, old, prop, old_rail)
        linked(dtb, new, prop, new_rail)
        assert get(dtb, symbol(dtb, new), 'status', 's') == 'okay'
    old_hc, new_hc = symbol(ref, 'ufshc_mem'), symbol(dtb, 'ufs_mem_hc')
    for prop in ('vcc-max-microamp', 'vccq-max-microamp', 'vccq2-max-microamp'):
        assert get(ref, old_hc, prop) == get(dtb, new_hc, prop), prop
    assert bounds(dtb, 'vreg_l17a') == tuple(map(int, get(ref, old_hc, 'vcc-voltage-level', 'u').split()))
    assert get(dtb, new_hc, 'lanes-per-direction', 'u') == '2'
    # Candidate topology is statically consistent, not established OP8 wiring.
    parent = symbol(dtb, 'vreg_s4a').rsplit('/', 1)[0]
    parents = {'vdd-l2-l10-supply': 'vreg_bob',
               'vdd-l3-l4-l5-l18-supply': 'vreg_s6a',
               'vdd-l6-l9-supply': 'vreg_s8c',
               'vdd-l7-l12-l14-l15-supply': 'vreg_s5a',
               'vdd-l13-l16-l17-supply': 'vreg_bob'}
    for prop, label in parents.items():
        assert get(dtb, parent, prop) == get(dtb, symbol(dtb, label), 'phandle'), prop
    config_path = P / ('build/in2010-kernel/.config' if (P / 'build/in2010-kernel/.config').exists()
                       else 'build/kernel/.config')
    config = config_path.read_text().splitlines()
    for name in ('SCSI', 'BLK_DEV_SD', 'SCSI_UFSHCD', 'SCSI_UFS_QCOM',
                 'PHY_QCOM_QMP_UFS', 'REGULATOR_QCOM_RPMH'):
        assert f'CONFIG_{name}=y' in config, name
    report['storage_rails'] = checked_rails
    report['storage_consumer_phandles'] = mapping
    report['parent_topology'] = 'community 8 Pro inference; NOT hardware verified'
    report['not_checked'] += ['UFS device reset', 'downstream UFS auxiliary supply votes',
                              'UFS runtime power sequencing and storage enumeration']
report['variant'] = args.variant
report['dtb_sha256'] = __import__('hashlib').sha256(dtb.read_bytes()).hexdigest()
if not args.dtb:
    (P / f'artifacts/{args.variant}/board-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS: {len(original)} original fixed ranges covered; no diagnostic overlaps; USB voltages match.')
if args.variant == 'storage-probe':
    print('PASS: UFS phandles/current limits, 8 rail bounds, OP8 VCC range, parent links and built-in drivers.')
