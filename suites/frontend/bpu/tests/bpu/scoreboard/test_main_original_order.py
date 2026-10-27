"""Independent logical Main state proves arrival order and sibling retention."""
from copy import deepcopy
import pytest
from bpuverify.bpu.model.main_original_order import Program,ORDERS,PHASES,COUNTERS,PC,STREAM_PC,EARLIER,LATER,INITIAL_TARGET,TARGETS,LATER_TARGET,RULES
from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.coverage.main_original_order import Coverage
from bpuverify.mbtb.model.semantic import MbtbReference,Events,Feedback,Branch,coordinate


def pending(model):
    return bool(model.snapshots or model.cleanup) or model.offered is not None or any(model.entry_offers.values()) or any(
        c.outstanding for c in model.entries.values()) or any(q.pending for q in model.directions.values())


def settle(model,*,busy=False,service=True):
    # This is a failure bound, not an expected latency or a fixed settling delay.
    for _ in range(32):
        mature=model.offered is None and not any(model.entry_offers.values())
        if mature and (not service or not pending(model)):return
        model.advance(Events(pc=STREAM_PC,select=busy))
    raise AssertionError('independent semantic model failed to settle')


def feedback(frame,position,target,kind,*,taken=True,wrong=True):
    return Feedback((frame.pc,(frame.pc//16+1)*16),source_entries(frame),
        (Branch(target,taken,position,kind,0,wrong),))


def teach(model,frame,position,target,kind,*,taken=True,wrong=True,busy=False):
    model.advance(Events(pc=STREAM_PC,select=busy,
        feedback=feedback(frame,position,target,kind,taken=taken,wrong=wrong)))
    settle(model,busy=busy,service=not busy)


@pytest.mark.parametrize('order',ORDERS)
@pytest.mark.parametrize('phase',PHASES)
@pytest.mark.parametrize('counter',COUNTERS)
def test_existing_independent_Main_model_derives_last_arrival_and_unchanged_sibling(order,phase,counter):
    p=Program(order,phase,counter);model=MbtbReference()
    teach(model,model.lookup_snapshot(PC+EARLIER+1),LATER,LATER_TARGET,1)
    for _ in range(2-counter):
        frame=model.lookup_snapshot(PC+EARLIER+1)
        teach(model,frame,LATER,LATER_TARGET,1,taken=False,wrong=bool(frame.values()['3.taken']))
    teach(model,model.lookup_snapshot(PC),EARLIER,INITIAL_TARGET,3)
    frames=tuple(model.lookup_snapshot(PC) for _ in range(2));original=deepcopy(frames)
    before_entries=model.entry_commits;before_directions=model.counter_commits
    for index in p.order_indices:
        teach(model,frames[index],EARLIER,TARGETS[index],3,busy=p.retained)
    if p.retained:
        assert model.entry_commits==before_entries and model.counter_commits==before_directions
        assert sum(len(v.outstanding) for v in model.entries.values())==1
        assert sum(len(v.pending) for v in model.directions.values())==2
        settle(model)
    assert model.entry_commits-before_entries==len(p.services)
    assert model.counter_commits-before_directions==2
    values=model.lookup_snapshot(PC).values()
    assert (values['2.position'],values['2.target'],values['2.counter'])==(EARLIER,p.final_target,2)
    assert (values['3.position'],values['3.target'],values['3.counter'],values['3.taken'])==(LATER,LATER_TARGET,counter,False)
    assert frames==original and frames[0] is not frames[1]


@pytest.mark.parametrize('bad',({'order':'unknown'},{'phase':'unknown'},{'sibling_counter':2},{'sibling_counter':True}))
def test_invalid_semantic_cross_is_rejected_before_driving(bad):
    args=dict(order=ORDERS[0],phase=PHASES[0],sibling_counter=0);args.update(bad)
    with pytest.raises(ValueError):Program(**args)


@pytest.mark.parametrize('missing',RULES)
def test_any_missing_service_or_consumer_prevents_all_checked_credit(missing):
    coverage=Coverage(Program(ORDERS[0],PHASES[0],0))
    for rule in RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError):coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('order',ORDERS)
@pytest.mark.parametrize('phase',PHASES)
@pytest.mark.parametrize('counter',COUNTERS)
def test_complete_semantic_program_only_credits_its_own_nine_obligations(order,phase,counter):
    coverage=Coverage(Program(order,phase,counter))
    for rule in RULES:coverage.reach(rule)
    assert coverage.groups['checked'].coverage==0
    coverage.finish();assert coverage.groups['checked'].coverage==12.5
    with pytest.raises(AssertionError):coverage.finish()


def test_physical_position_and_duplicate_witness_are_not_new_semantics():
    coverage=Coverage(Program(ORDERS[0],PHASES[0],0));coverage.reach(RULES[0])
    for rule in (RULES[0],'bank0-way1'):
        with pytest.raises(ValueError):coverage.reach(rule)


@pytest.mark.parametrize('capacity',(8,16))
def test_explicit_source_capacity_is_an_environment_assumption_not_a_signal(capacity):
    from bpuverify.bpu.checker.bounded_sources import BoundedChecker
    assert BoundedChecker(capacity=capacity).windows.ledger.capacity==capacity
    assert BoundedChecker().windows.ledger.capacity==8
