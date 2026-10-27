"""Redirect both DUT raw coverage and functional outputs before collection."""
from hashlib import sha256
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

def pytest_addoption(parser):
    parser.addini('toffee_feature_plan', 'disabled in isolated diagnostics')
    parser.addini('toffee_feature_report', 'disabled in isolated diagnostics')

def pytest_configure(config):
    if not os.environ.get('BPU_DIAGNOSTIC_STAGE'):
        raise RuntimeError('Use run_flush_key_probe.py; diagnostic stage is required')
    stage = Path(os.environ['BPU_DIAGNOSTIC_STAGE']).resolve()
    if stage == ROOT or not (stage / 'protected.json').is_file():
        raise RuntimeError('diagnostic stage must be isolated and contain protected report hashes')
    import bpuverify.common.env.dut as factory
    import bpuverify.common.env.paths as support
    factory.ROOT = support.REPO_ROOT = stage
    factory.RTL_COVERAGE_FILES.clear()
    original = factory.DutFactory.create
    def isolated(self, name, *, coverage_name='verilator-coverage.dat'):
        return original(self, name, coverage_name='probe-flush-key-' + coverage_name)
    factory.DutFactory.create = isolated

def pytest_sessionfinish(session, exitstatus):
    from bpuverify.common.env.dut import RTL_COVERAGE_FILES
    from tests.mbtb.diagnostics.flush_key_probe import CASES
    stage = Path(os.environ['BPU_DIAGNOSTIC_STAGE'])
    protected = json.loads((stage / 'protected.json').read_text())
    assert protected == {name: sha256((ROOT / 'results' / name).read_bytes()).hexdigest() for name in protected}
    (stage / 'probe-manifest.json').write_text(json.dumps(dict(exitstatus=exitstatus,
        files=list(map(str, sorted(RTL_COVERAGE_FILES))), cases=CASES, formal_credit=False,
        strict_xfail_registered=False, integrated_ftq_reachability_proven=False,
        formal_reports_preserved=True), indent=2) + '\n')
