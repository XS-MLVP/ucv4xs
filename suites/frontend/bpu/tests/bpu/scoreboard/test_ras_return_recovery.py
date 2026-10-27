"""Synthetic lifecycle/negative contracts; these are not DUT coverage evidence."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from bpuverify.bpu.checker.ras.semantic import RasSemanticComponentChecker
from bpuverify.bpu.coverage.ras_return_recovery import ReturnRecoveryCoverage,return_recovery_coverage
from bpuverify.ras.model.semantic import Events,Recovery,Retirement
from tests.bpu.scoreboard.test_ras_semantic import ADDRESS,PC,actuals,step


def prepare(calls,storage,*,coverage=None):
    checker = RasSemanticComponentChecker(coverage=coverage,return_pc=PC)
    step(checker,Events(reset=True))
    sources = []
    for _ in range(calls):
        sources.append(dict(checker.model.projection))
        step(checker,Events(2,ADDRESS))
    if storage=='retained':
        for source in sources:
            step(checker,Events(retirement=Retirement(source['group'],source['calls'],2)))
        step(checker)
    prefix = dict(checker.model.projection)
    for _ in range(3):step(checker,Events(1))
    return checker,sources,Events(recovery=Recovery(prefix['group'],prefix['calls'],prefix['repeat'],1))


@pytest.mark.parametrize('calls',(8,9))
@pytest.mark.parametrize('storage',('speculative','retained'))
def test_complete_synthetic_lifecycle_needs_owned_restore_retirement_and_new_consumer(calls,storage):
    coverage = ReturnRecoveryCoverage(calls,storage)
    checker,sources,recovery = prepare(calls,storage,coverage=coverage)
    assert coverage.groups['reached'].coverage==coverage.groups['checked'].coverage==0
    step(checker,recovery)
    assert coverage.groups['reached'].coverage==50 and coverage.groups['checked'].coverage==0
    step(checker)
    assert coverage.recovery_checked and coverage.groups['checked'].coverage==50
    if storage=='speculative':
        for source in sources:
            step(checker,Events(retirement=Retirement(source['group'],source['calls'],2)))
        step(checker)
    source = recovery.recovery
    step(checker,Events(retirement=Retirement(source.group,source.calls,1)))
    step(checker)
    for _ in range(2):
        before = dict(checker.model.projection)
        step(checker,Events(1))
        step(checker,Events(retirement=Retirement(before['group'],before['calls'],1)))
        step(checker)
        step(checker)
    checker.check_survivors(calls=calls,returns=3,return_pc=PC)
    checker.finish()
    assert all(group.coverage==100 for group in coverage.groups.values())


@pytest.mark.parametrize('calls',(8,9))
@pytest.mark.parametrize('actual_storage',('speculative','retained'))
def test_wrong_predecessor_lifetime_is_a_failure_not_another_passing_label(calls,actual_storage):
    wrong = 'retained' if actual_storage=='speculative' else 'speculative'
    coverage = ReturnRecoveryCoverage(calls,wrong)
    checker,_,recovery = prepare(calls,actual_storage,coverage=coverage)
    with pytest.raises(AssertionError,match='predecessor lifetime'):step(checker,recovery)
    assert checker.failure is not None
    assert all(group.coverage==0 for group in coverage.groups.values())


@pytest.mark.parametrize('field',('top','repeat','group','calls','retained-cell'))
def test_bad_registered_actual_latches_and_cannot_close_recovery_rules(field):
    coverage = ReturnRecoveryCoverage(9,'retained')
    checker,_,recovery = prepare(9,'retained',coverage=coverage)
    step(checker,recovery)
    tick = checker.input_tick+2
    checker.capture_input(NS(tick=tick),Events(),consumer=dict(valid=0,taken=0,pc=0,target=0))
    public,retained = actuals(checker.model)
    if field=='top':public['top'] ^= 1
    elif field=='repeat':public['redirect_meta']['sctr'] ^= 1
    elif field=='group':public['redirect_meta']['ssp'] ^= 1
    elif field=='calls':public['redirect_meta']['tosw']['value'] ^= 1
    else:retained['cells'][6]['address'] ^= 1
    state = deepcopy(checker.model.state())
    checker.capture_output(NS(tick=tick+1),public,retained=retained)
    with pytest.raises(AssertionError):checker.raise_failure()
    failure = checker.failure
    checker.capture_input(NS(tick=tick+2),Events(2,ADDRESS),consumer={})
    assert checker.failure is failure and checker.model.state()==state
    assert coverage.groups['checked'].coverage==0 and not coverage.recovery_checked


def test_effect_requires_the_exact_comparison_and_cannot_be_ignored_by_enable():
    coverage = ReturnRecoveryCoverage(8,'speculative')
    checker,_,recovery = prepare(8,'speculative')
    model = checker.model
    model.advance(recovery)
    coverage.accept(recovery,model,101)
    coverage.consume(102,model)
    assert coverage.groups['checked'].coverage==0
    model.advance(Events(enabled=False))
    with pytest.raises(AssertionError,match='no accepted registered effect'):coverage.consume(104,model)
    with pytest.raises(AssertionError,match='exact comparison'):coverage.consume(106,model)
    assert coverage.groups['checked'].coverage==0


def test_duplicate_redone_return_delivery_is_rejected():
    coverage = ReturnRecoveryCoverage(8,'retained')
    checker,_,recovery = prepare(8,'retained',coverage=coverage)
    step(checker,recovery)
    step(checker)
    event = Events(retirement=Retirement(recovery.recovery.group,recovery.recovery.calls,1))
    model = checker.model
    model.advance(event)
    coverage.accept(event,model,101)
    with pytest.raises(AssertionError,match='more than once'):coverage.accept(event,model,103)


@pytest.mark.parametrize('kind',('no-owner','non-return','disabled'))
def test_nonqualifying_recovery_has_no_event_credit(kind):
    coverage = ReturnRecoveryCoverage(8,'speculative')
    checker,_,event = prepare(8,'speculative')
    recovery = event.recovery
    event = (Events(recovery=Recovery(7,7,7,1)) if kind=='no-owner' else
        Events(recovery=Recovery(recovery.group,recovery.calls,recovery.repeat,0)) if kind=='non-return' else
        Events(recovery=recovery,enabled=False))
    coverage.accept(event,checker.model,101)
    coverage.consume(104,checker.model)
    assert all(group.coverage==0 for group in coverage.groups.values())


def test_reset_cancels_effect_ownership_but_does_not_invent_checked_credit():
    coverage = ReturnRecoveryCoverage(8,'speculative')
    checker,_,event = prepare(8,'speculative')
    checker.model.advance(event)
    coverage.accept(event,checker.model,101)
    assert coverage.pending
    coverage.accept(Events(reset=True),checker.model,103)
    coverage.consume(110,checker.model)
    assert not coverage.pending and coverage.recovery_key is None and not coverage.recovery_checked
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('arguments',((7,'retained','reached'),(8,'memory','reached'),(9,'speculative','phase')))
def test_unknown_coverage_scope_fails_closed(arguments):
    with pytest.raises(ValueError):return_recovery_coverage(*arguments)


def test_case_and_shared_program_contain_no_edge_get_set_or_task_gather():
    for filename in ('return_recovery','redo_unwind'):
        tree = ast.parse(Path(f'bpuverify/bpu/case/ras/{filename}.py').read_text())
        forbidden = {'ClockCycles','FallingEdge','RisingEdge','get_','set_','gather','GetInternalSignal'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                name = node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',None)
                assert name not in forbidden
