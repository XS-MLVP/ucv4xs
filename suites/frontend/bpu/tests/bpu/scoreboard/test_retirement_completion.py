"""Applied reference state is not yet checked DUT state."""
from copy import deepcopy

import pytest

from bpuverify.bpu.checker.ras.retirement import CommitChecker


def row(checker,*,reset=0,commit=None,pending=None):
    return dict(reset=reset,state=checker.reference.native(),
        commit=dict(valid=int(commit is not None),bits=commit),
        pending=dict(valid=0) if pending is None else pending,
        spec=dict(enable=1))


def applied_but_uncompared():
    checker = CommitChecker()
    checker.observe(row(checker,reset=1),2)
    request = dict(action=2,branch_type=2,meta=dict(ssp=0,tosw=dict(flag=0,value=0)),return_address=0x40018010)
    checker.planned.append(request)
    commit = {key:deepcopy(request[key]) for key in ('action','branch_type','meta')}
    checker.observe(row(checker,commit=commit),4)
    checker.observe(row(checker,pending=dict(valid=1,push=1,pop=0,ssp=0,tosw=dict(flag=0,value=0))),6)
    assert len(checker.accepted)==len(checker.applied)==1
    assert checker.pending_expected is None
    return checker


def test_summary_cannot_pass_before_final_dut_effect_comparison():
    checker = applied_but_uncompared()
    assert checker.checked_applied==0
    with pytest.raises(AssertionError,match='all-effects-compared'):checker.summary()


def test_completion_follows_actual_dut_effect_comparison():
    checker = applied_but_uncompared()
    checker.observe(row(checker),8)
    assert checker.checked_applied==1
    assert checker.summary()['applied']==1


def test_wrong_final_dut_cell_never_advances_completion_counter():
    checker = applied_but_uncompared()
    actual = row(checker)
    actual['state']['cells'][1]['address'] ^= 1
    with pytest.raises(AssertionError):checker.observe(actual,8)
    assert checker.checked_applied==0
