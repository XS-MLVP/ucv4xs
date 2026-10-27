import ucv.runtime as ucv_paths
"""Run normal-driver zero-key/cleanup diagnostics without touching formal reports."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]

def main():
    stage = Path(tempfile.mkdtemp(prefix='bpu-mbtb-flush-key-reproduce-'))
    (stage / 'dut').symlink_to(ROOT / 'dut', target_is_directory=True)
    protected = {}
    for name in ('feature-points.json', 'rtl-coverage-manifest.json', 'rtl-line-coverage.json', 'verification-report.html'):
        source = ROOT / 'results' / name
        shutil.copy2(source, stage / name)
        protected[name] = sha256(source.read_bytes()).hexdigest()
    (stage / 'protected.json').write_text(json.dumps(protected, indent=2) + '\n')
    shutil.copy2(ROOT / 'tests/mbtb/diagnostics/flush_key_probe.py', stage / 'source-flush-key-probe.py')
    env = dict(os.environ, BPU_DIAGNOSTIC_STAGE=str(stage))
    env['PYTHONPATH'] = os.pathsep.join((str(ROOT), str(ucv_paths.project_root() / '.tools/sources/toffee/src'), str(ucv_paths.project_root() / '.tools/share/picker/python'), env.get('PYTHONPATH', '')))
    command = [sys.executable, '-m', 'pytest', '-c', str(ROOT / 'pytest.ini'), '-q', '--tb=short',
        '-p', 'no:bpuverify.common.pytest.features', '-p', 'tests.mbtb.diagnostics.isolated_plugin',
        str(ROOT / 'tests/mbtb/diagnostics/flush_key_probe.py')]
    print(f'Isolated stage: {stage}', flush=True)
    run = subprocess.run(command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (stage / 'pytest.log').write_text(run.stdout)
    print(run.stdout, end='')
    assert protected == {name: sha256((ROOT / 'results' / name).read_bytes()).hexdigest() for name in protected}
    print(f'Diagnostic evidence: {stage / "probe-manifest.json"}', flush=True)
    return run.returncode

if __name__ == '__main__':
    raise SystemExit(main())
