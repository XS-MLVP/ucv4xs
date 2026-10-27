"""Maintenance preserves learned behavior; synthetic tests earn no DUT credit."""
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest

from bpuverify.bpu.checker.history_maintenance import HistoryMaintenanceChecks
from bpuverify.bpu.coverage.history_working_set import HistoryWorkingSetCoverage
from bpuverify.bpu.env.history_working_set import HistoryWorkingSetEnv
from bpuverify.bpu.model.early_aging import Allocation, aged
from bpuverify.bpu.model.history_working_set import (
    MAINTENANCE_RULES, HistoryLearningLedger, HistoryWorkingSetProgram,
)
from bpuverify.utage.model.usefulness_events import ProtectionState


@pytest.mark.parametrize('before,predicted,base,actual',((1,1,0,1),(2,1,1,0)))
def test_common_prestate_maintenance_does_not_double_apply_local_protection(before,predicted,base,actual):
    program = HistoryWorkingSetProgram('turnover-forward')
    ledger = HistoryLearningLedger(program)
    path,other = program.positives[:2]
    ledger.states = {path.ordinal:ProtectionState(5,before),other.ordinal:ProtectionState(2,3)}
    previous = dict(ledger.states)
    feedback = ledger.feedback(path,predicted=predicted,base=base,actual=actual)
    assert feedback.useful//2 != before//2, 'the fixture discriminates sequential double transformation'
    ledger.maintain(previous)
    assert ledger.states[path.ordinal] == ProtectionState(feedback.counter,before//2)
    assert ledger.states[other.ordinal] == ProtectionState(2,1)
    assert previous[path.ordinal] == ProtectionState(5,before)


def test_capacity_maintenance_preserves_every_learned_direction_not_just_current_history():
    program = HistoryWorkingSetProgram('capacity-reverse')
    ledger = HistoryLearningLedger(program)
    ledger.states = {path.ordinal:ProtectionState(path.ordinal%8,path.ordinal%4) for path in program.positives}
    previous = deepcopy(ledger.states)
    ledger.maintain(previous)
    assert len(ledger.states) == 510
    assert ledger.states == {ordinal:ProtectionState(state.counter,state.useful//2)
        for ordinal,state in previous.items()}
    assert {ordinal:state.taken for ordinal,state in ledger.states.items()} == {
        ordinal:state.taken for ordinal,state in previous.items()}


def test_unmodeled_new_admission_overlap_fails_explicitly_instead_of_hiding_a_new_owner():
    program = HistoryWorkingSetProgram('turnover-forward')
    ledger = HistoryLearningLedger(program)
    previous = dict(ledger.states)
    ledger.allocate(program.positives[0],taken=True)
    with pytest.raises(NotImplementedError,match='displaced-owner prestate'):
        ledger.maintain(previous)
    assert ledger.transitions['maintenance'] == 0


async def test_direction_reversal_does_not_misclassify_legal_global_protection_as_wrong_learning():
    program = HistoryWorkingSetProgram('capacity-reverse')
    path = program.selected[0]
    ledger = HistoryLearningLedger(program)
    ledger.states[path.ordinal] = ProtectionState(7,3)
    env = object.__new__(HistoryWorkingSetEnv)
    env.program = program
    visits = []
    def check(expected,actual,label):assert expected == actual,label
    def direction(source,original,*,taken,phase):
        assert source is visits[-1] and original is path and taken is False and phase == 'reversed'
        assert not ledger.states[path.ordinal].taken
    env.checks = NS(ledger=ledger,check=check,direction=direction,
        declare_result=lambda *args:None,penalized=set())
    async def negative_base(helper):assert helper is program.helper_for(path)
    async def visit(original):
        assert original is path
        previous = dict(ledger.states)
        before = ledger.states[path.ordinal]
        ledger.feedback(path,predicted=before.taken,base=0,actual=0)
        if len(visits) == 1:ledger.maintain(previous)
        source = object()
        visits.append(source)
        return source
    env.negative_base,env.visit = negative_base,visit
    await env.reverse(path)
    assert len(visits) == 5 and ledger.transitions['maintenance'] == 1
    assert env.checks.penalized == {path.ordinal}


async def test_restore_reestablishes_correct_opposition_after_intervening_global_maintenance():
    program = HistoryWorkingSetProgram('capacity-reverse')
    path = program.selected[0]
    env = object.__new__(HistoryWorkingSetEnv)
    env.program = program
    states = {path.ordinal:ProtectionState(2,2)}
    maintenance = NS(failures=NS(ages=0))
    returned = []
    def check(expected,actual,label):assert expected == actual,label
    def direction(source,original,**kwargs):
        assert original is path and source is returned[-1] and kwargs == dict(taken=True,phase='restored')
    env.checks = NS(declare_result=lambda *args:None,ledger=NS(states=states),maintenance=maintenance,
        check=check,direction=direction,recovered=set())
    async def positive(original,*,require_upper):
        assert original is path and require_upper is False
        before = states[path.ordinal]
        if not returned:states[path.ordinal] = ProtectionState(5,2)
        elif len(returned) == 1:
            maintenance.failures.ages += 1
            states[path.ordinal] = ProtectionState(6,before.useful//2)
        else:states[path.ordinal] = ProtectionState(7,before.useful+1)
        source = object()
        returned.append(source)
        return source
    env.positive = positive
    await env.restore(path)
    assert len(returned) == 4 and states[path.ordinal] == ProtectionState(7,3)
    assert env.checks.recovered == {path.ordinal}


def owner(profile='capacity-reverse'):
    program = HistoryWorkingSetProgram(profile)
    def check(expected,actual,label):assert expected == actual,label
    return NS(program=program,coverage=HistoryWorkingSetCoverage(program),check=check,
        ledger=HistoryLearningLedger(program),public_consumers={'restored':{}},originals=[])


def quiet_sources():
    return NS(short=NS(learning=None,low_tick=0,useful=[{},{}]))


def observed(*,pressure=0,maintenance=False,protection=None):
    return {'observed':{'early_direction':{'maintenance':dict(low=pressure,fire=0,
        tables=[dict(age=int(maintenance)),dict(age=int(maintenance))]),
        'useful':protection or (tuple([0]*512),tuple([0]*512))}}}


@pytest.mark.parametrize('fault',('none','other-history','late-observation','premature-observation'))
def test_actual_complete_maintenance_poststate_is_required_before_any_credit(fault):
    parent = owner()
    checks = HistoryMaintenanceChecks(parent)
    before = (tuple(index%4 for index in range(512)),tuple((index+1)%4 for index in range(512)))
    expected = aged(before)
    actual = [list(table) for table in expected]
    if fault == 'other-history':actual[1][499] ^= 1
    record = {'tick':10}
    checks.pending = 10,expected,record
    tick = 14 if fault == 'late-observation' else 10 if fault == 'premature-observation' else 12
    if fault == 'none':
        checks.before(observed(protection=actual),quiet_sources(),tick)
        assert checks.pending is None and checks.receipts == [record]
        assert record['observed_tick'] == 12
        assert parent.coverage.maintenance_groups['reached'].coverage > 0
    else:
        with pytest.raises(AssertionError):checks.before(observed(protection=actual),quiet_sources(),tick)
        assert not checks.receipts
        assert parent.coverage.maintenance_groups['reached'].coverage == 0
    assert parent.coverage.maintenance_groups['checked'].coverage == 0


def test_only_qualified_failures_advance_pressure_not_quiet_cycles_or_successes():
    checks = HistoryMaintenanceChecks(owner())
    sources = quiet_sources()
    for tick in range(0,300,2):
        checks.before(observed(),sources,tick)
        checks.after(tick,sources)
    assert checks.failures.count == checks.failures.ages == 0
    for _ in range(127):checks.failures.apply(Allocation(10,1,None))
    checks.failures.apply(None)
    checks.failures.apply(Allocation(None,None,None))
    checks.failures.apply(Allocation(10,None,0))
    assert checks.failures.count == 127 and not checks.failures.aging
    checks.failures.apply(Allocation(10,1,None))
    assert checks.failures.aging and checks.failures.failures == 128
    checks.before(observed(pressure=128,maintenance=True),sources,400)
    checks.after(400,sources)
    assert checks.failures.count == 0 and checks.failures.ages == 1
    checks.before(observed(),sources,402)
    assert len(checks.receipts) == 1 and checks.pending is None


@pytest.mark.parametrize('fault',('pressure','missing-maintenance','spurious-maintenance'))
def test_control_cannot_claim_an_unqualified_maintenance_event(fault):
    checks = HistoryMaintenanceChecks(owner())
    if fault == 'missing-maintenance':checks.failures.count = 128
    row = observed(pressure=128 if fault == 'missing-maintenance' else int(fault=='pressure'),
                   maintenance=fault == 'spurious-maintenance')
    with pytest.raises(AssertionError):checks.before(row,quiet_sources(),20)
    assert checks.pending is None and not checks.receipts


@pytest.mark.parametrize('fault',('none','missing-NT','stale-source','unknown-epoch','duplicate-epoch'))
def test_maintenance_needs_fresh_public_consumers_of_both_directions(fault):
    checks = HistoryMaintenanceChecks(owner())
    checks.receipts = [{'observed_tick':20}]
    views = {False:{'prediction_tick':24},True:{'prediction_tick':26}}
    if fault == 'missing-NT':views.pop(False)
    elif fault == 'stale-source':views[False]['prediction_tick'] = 20
    elif fault == 'duplicate-epoch':checks.record_consumers(1,views)
    if fault == 'none':
        checks.record_consumers(1,views)
        assert checks.consumers == {1:views}
    else:
        with pytest.raises(AssertionError):checks.record_consumers(2 if fault=='unknown-epoch' else 1,views)
    assert checks.owner.coverage.maintenance_groups['checked'].coverage == 0


@pytest.mark.parametrize('fault',('none','no-event','unconfirmed-event','missing-public-pair','stale-final-consumer'))
def test_checked_credit_requires_complete_maintenance_and_late_public_consumers(fault):
    parent = owner()
    checks = HistoryMaintenanceChecks(parent)
    checks.failures.ages = int(fault != 'no-event')
    if fault not in ('no-event','unconfirmed-event'):checks.receipts = [{'observed_tick':20}]
    if fault not in ('no-event','unconfirmed-event','missing-public-pair'):
        checks.record_consumers(1,{False:{'prediction_tick':24},True:{'prediction_tick':26}})
    parent.public_consumers['restored'] = {1:{'prediction_tick':20 if fault=='stale-final-consumer' else 30}}
    if fault == 'none':
        checks.finish()
        assert parent.coverage.maintenance_groups['checked'].coverage == 100
        assert len(MAINTENANCE_RULES) == 5
    else:
        with pytest.raises(AssertionError):checks.finish()
        assert parent.coverage.maintenance_groups['checked'].coverage == 0
