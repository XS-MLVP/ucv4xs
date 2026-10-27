"""The ABTB residual arms are structural, not untested behaviour.

The audit is a bounded source/structure proof: each of the 64 per-set PLRU
chains ends inside a guard that already requires one of that set's four way
masks, and the ABTB WriteBuffer ternary is generated inside its own false
branch.  Synthetic fixtures prove the checker rejects weakened structure.
"""
import json
from pathlib import Path

import pytest

from bpuverify.abtb.coverage.replacer_branch_audit import REPLACER, WRITEBUFFER, audit, replacer_claims
from bpuverify.abtb.coverage.replacer_branch_audit import ROOT


def native_report():
    path = ROOT / 'results/abtb-module-baseline-20261021-v1/rtl-line-coverage.json'
    if not path.exists():
        pytest.skip('frozen ABTB module report is not present')
    return json.loads(path.read_text())


def test_every_replacer_arm_is_one_set_and_the_guard_union_is_unsatisfiable():
    report = native_report()
    result = audit(report)
    assert result['replacer_arms'] == 64
    assert result['writebuffer_arms'] == 1
    sets = {claim['set_index'] for claim in result['claims']}
    assert sets == set(range(64))
    for claim in result['claims']:
        assert all(mask in claim['guard'] for mask in claim['masks'])
        assert claim['kind'] == 'guard-union-makes-fallthrough-unsatisfiable'
    assert result['writebuffer']['kind'] == 'ternary-inside-its-own-false-branch'
    assert result['native_denominator_unchanged'] is True
    assert result['functional_pass_credit'] is False
    assert result['whole_design_formal_claim'] is False


@pytest.mark.parametrize('mutation', ('drop-a-mask', 'borrow-another-set', 'add-final-else'))
def test_weakened_or_extended_structure_is_rejected(monkeypatch, mutation):
    report = native_report()
    path = ROOT / REPLACER
    before = path.read_bytes()
    changed = path.read_text().splitlines()
    claim = replacer_claims(report)[0]
    arm = claim['line'] - 1
    guard = claim['guard_line'] - 1
    window = next(index for index in range(guard, guard + 4)
                  if 'set_touch_ways_3' in changed[index]
                  and 'valid' in changed[index])
    if mutation == 'drop-a-mask':
        changed[window] = changed[window].replace('set_touch_ways_3_valid', '')
    elif mutation == 'borrow-another-set':
        changed[window] = changed[window].replace('set_touch_ways_3_valid',
                                                  'set_touch_ways_3_1_valid')
    else:
        changed[arm + 2] = '          else\n            state_vec_0 <= 2\'h0;\n        end'
    real_read = Path.read_text

    def read(self, *args, **kwargs):
        return '\n'.join(changed) if self == path else real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', read)
    with pytest.raises(AssertionError):
        audit(report)
    assert path.read_bytes() == before


@pytest.mark.parametrize('mutation', ('remove-the-if', 'drop-the-hit-term', 'make-the-else-live'))
def test_writebuffer_claim_rejects_a_different_guard(monkeypatch, mutation):
    report = native_report()
    path = ROOT / WRITEBUFFER
    before = path.read_bytes()
    changed = path.read_text().splitlines()
    target = next(number for number, line in enumerate(changed, 1)
                  if "writeTouchVec_0_bits = io_write_0_valid & ~hit ? victim : 2'h0;" in line)
    guard = target - 2
    if mutation == 'remove-the-if':
        changed[guard] = '      if (io_write_0_valid) begin'
    elif mutation == 'drop-the-hit-term':
        changed[guard] = '      if (io_write_0_valid & hit) begin'
    else:
        changed[target - 1] = "        writeTouchVec_0_bits = io_write_0_valid ? victim : 2'h0;"
    real_read = Path.read_text

    def read(self, *args, **kwargs):
        return '\n'.join(changed) if self == path else real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'read_text', read)
    with pytest.raises(AssertionError):
        audit(report)
    assert path.read_bytes() == before
