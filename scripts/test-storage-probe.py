"""Positive and deliberately corrupted-DTB negative tests; no phone I/O."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile

P = Path(__file__).resolve().parents[1]
audit = ['python3', str(P / 'scripts/audit-diagnostic-board.py'), '--variant', 'storage-probe']
subprocess.run(audit, check=True)
source = P / 'artifacts/storage-probe/instantnoodle-storage-probe.dtb'
def sym(label):
    return subprocess.check_output(['fdtget', '-t', 's', str(source), '/__symbols__', label], text=True).strip()
mutations = (
    ('wrong-vcc-voltage', sym('vreg_l17a'), 'regulator-max-microvolt', '3008000'),
    ('missing-vcc-supply', sym('ufs_mem_hc'), 'vcc-supply', '0'),
    ('wrong-current', sym('ufs_mem_hc'), 'vcc-max-microamp', '900000'),
    ('display-enabled', sym('mdss'), 'status', 'okay'),
    ('wrong-board', '/', 'oplus,dtsi_no', '19801'),
    ('missing-parent', sym('vreg_s4a').rsplit('/', 1)[0], 'vdd-l6-l9-supply', '0'),
)
with tempfile.TemporaryDirectory(prefix='op8-dtb-tests-') as tmp:
    for name, node, prop, value in mutations:
        target = Path(tmp) / (name + '.dtb')
        shutil.copyfile(source, target)
        subprocess.run(['fdtput', '-t', 's' if prop == 'status' else 'u',
                        str(target), node, prop, value], check=True)
        result = subprocess.run(audit + ['--dtb', str(target)], capture_output=True, text=True)
        assert result.returncode != 0 and 'AssertionError' in result.stderr, (name, result.stderr)
report = {'positive_audit': 'passed', 'rejected_mutations': [m[0] for m in mutations],
          'phone_boot': 'NOT TESTED', 'full_dt_schema': 'NOT TESTED'}
(P / 'artifacts/storage-probe/test-results.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
