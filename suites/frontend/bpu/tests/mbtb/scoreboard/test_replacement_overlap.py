"""Hand-derived discriminators and intentionally wrong comparisons; no DUT."""
from dataclasses import replace
from copy import deepcopy

import pytest
from toffee import ScoreboardMismatch

from bpuverify.mbtb.model.replacement_overlap import CASES, PC, ReplacementProgram
from bpuverify.mbtb.model.replacement import mbtb_replacement_geometry
from bpuverify.mbtb.checker.replacement_overlap import ReplacementChecks


class NoCoverage:
    def record(self,*args,**kwargs):pass


@pytest.mark.parametrize('mode',CASES)
def test_logical_program_has_a_discriminating_old_and_new_victim_or_no_forward_control(mode):
    program=ReplacementProgram(mode)
    assert program.old_victim==1
    assert program.victim==(0 if mode in ('same-taken','alias-taken') else 1)
    assert len(program.prepared)==len(program.final)==6
    assert program.new.position==3 and program.removed.position==(5 if program.forwarded else 1)
    assert all(r.counter in range(4) for r in program.final)
    a,b,c=(mbtb_replacement_geometry(pc,1) for pc in program.pcs.values())
    assert a.replacement_index==b.replacement_index!=c.replacement_index
    assert a.entry_set!=b.entry_set and a.bank==b.bank==c.bank


@pytest.mark.parametrize('mode',('same-taken','alias-taken'))
def test_lost_latest_age_is_rejected_with_expected_actual_and_program_state(mode):
    program=ReplacementProgram(mode)
    wrong=[replace(program.new,way=program.old_victim),
           next(r for r in program.prepared if r.pc==PC and r.way==program.victim)]
    actual=tuple((r.way,r.position,r.target,r.counter) for r in sorted(wrong,key=lambda r:r.way))
    checks=ReplacementChecks(program,NoCoverage(),'negative-control')
    with pytest.raises(ScoreboardMismatch) as error:checks.profile(PC,actual)
    assert error.value.context.request['program']['victim']==0
    assert error.value.context.request['program']['old_victim']==1
    assert error.value.expected!=error.value.actual and error.value.differences
    assert isinstance(error.value,AssertionError)


@pytest.mark.parametrize('mode',('independent-taken','same-not-taken','alias-not-taken',
                                 'independent-not-taken','lookup-only'))
def test_false_touch_or_cross_index_forwarding_is_rejected(mode):
    program=ReplacementProgram(mode)
    wrong=(replace(program.new,way=1-program.victim),
           replace(next(r for r in program.prepared if r.pc==PC and r.way==program.victim),counter=0))
    actual=tuple((r.way,r.position,r.target,r.counter) for r in sorted(wrong,key=lambda r:r.way))
    checks=ReplacementChecks(program,NoCoverage(),'negative-control')
    with pytest.raises(ScoreboardMismatch) as error:checks.profile(PC,actual)
    assert len(error.value.expected)==len(error.value.actual)==2


def test_inserting_a_bubble_cannot_qualify_adjacent_feedback():
    checks=ReplacementChecks(ReplacementProgram('same-taken'),NoCoverage(),'negative-control')
    with pytest.raises(ScoreboardMismatch,match='mismatch'):
        checks.admissions((100,104),('touch','allocate'),('touch','allocate'))


def test_different_ordered_public_inputs_cannot_qualify_the_same_program():
    checks=ReplacementChecks(ReplacementProgram('same-taken'),NoCoverage(),'negative-control')
    with pytest.raises(ScoreboardMismatch):
        checks.admissions((100,102),('allocate','touch'),('touch','allocate'))


def test_program_construction_is_reset_local_and_does_not_mutate_a_previous_run():
    program=ReplacementProgram('alias-taken');frozen=deepcopy(program.state())
    ReplacementProgram('independent-not-taken')
    assert program.state()==frozen


def test_unknown_physical_sweep_mode_is_not_a_semantic_scenario():
    with pytest.raises(ValueError):ReplacementProgram('all-banks')
