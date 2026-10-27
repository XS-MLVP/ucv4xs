"""Guard proofs fail closed if source layout/input relations or native rows drift."""
from copy import deepcopy
from pathlib import Path

import pytest

from bpuverify.ras.coverage.guard_audit import CHILD, PARENT, ROOT, audit, inspect_sources, witnesses


def report():
    proof = inspect_sources()
    return dict(line_coverage='native LCOV DA rows', dut=dict(ras=dict(
        source_lines=dict(total=585, hit=569), build_provenance=dict(test_fixture=True),
        uncovered_rtl_source_lines=proof['rows'])))


@pytest.mark.parametrize('kind', ('priority', 'parent-action'))
def test_each_proof_has_a_satisfying_relaxed_negative_control(kind):
    assert witnesses(kind) == []
    assert witnesses(kind, relax=True)


def test_native_denominator_is_retained_not_subtracted():
    native = report()
    before = deepcopy(native)
    result = audit(native)
    assert result['classified_rows'] == 16
    assert result['native_source_lines'] == dict(total=585, hit=569)
    assert result['native_denominator_unchanged'] is True
    assert native == before


@pytest.mark.parametrize('drift', ('extra-row', 'missing-row', 'source-text'))
def test_native_evidence_drift_invalidates_audit(drift):
    native = report()
    missing = native['dut']['ras']['uncovered_rtl_source_lines']
    if drift == 'extra-row':
        missing.append(dict(file=CHILD, line=1, verilog='module changed;'))
    elif drift == 'missing-row':
        missing.pop()
    else:
        missing[0]['verilog'] = 'changed;'
    with pytest.raises(ValueError):
        audit(native)


@pytest.mark.parametrize('drift', ('parent-action', 'child-priority', 'decrement-guard'))
def test_source_mutations_invalidate_guard_proof(tmp_path, drift):
    for name in (PARENT, CHILD):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / name).read_text())
    if drift == 'parent-action':
        path = tmp_path / PARENT
        before, after = "commitValid & commitInfo_attribute_rasAction == 2'h1", "commitValid & commitInfo_attribute_rasAction == 2'h2"
    else:
        path = tmp_path / CHILD
        before, after = (('if (_GEN_15)', 'if (_GEN_17)') if drift == 'child-priority' else
                         ('_GEN_16 = io_commit_popValid', '_GEN_16 = io_commit_pushValid'))
    path.write_text(path.read_text().replace(before, after, 1))
    with pytest.raises(ValueError):
        inspect_sources(tmp_path)
