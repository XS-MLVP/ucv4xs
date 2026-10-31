"""Logical Main state and source lifetime are independent of DUT signal state."""
from copy import deepcopy
import pytest
from suites.frontend.bpu.bpu.model.main_cold_original_order import Program,ORDERS,PHASES,COUNTERS,RULES
from suites.frontend.bpu.bpu.model.main_original_order import PC,STREAM_PC,EARLIER,LATER,INITIAL_TARGET,TARGETS,LATER_TARGET
from suites.frontend.bpu.bpu.model.main_sources import source_entries
from suites.frontend.bpu.bpu.model.main_service import counter_payload
from suites.frontend.bpu.bpu.model.window_lifetime import WindowLifetimes,LifetimeError
from suites.frontend.bpu.bpu.coverage.main_cold_original_order import Coverage
from suites.frontend.bpu.mbtb.model.semantic import MbtbReference,Events,Feedback,Branch


def settle(model,*,busy=False):
    for _ in range(32): # Failure budget only; completion is model state.
        mature=model.offered is None and not any(model.entry_offers.values())
        pending=bool(model.snapshots or model.cleanup) or any(c.outstanding for c in model.entries.values()) or any(q.pending for q in model.directions.values())
        if mature and (busy or not pending):return
        model.advance(Events(pc=STREAM_PC,select=busy))
    raise AssertionError('semantic Main state failed to settle')


def teach(model,frame,position,target,kind,*,taken=True,wrong=True,busy=False):
    feedback=Feedback((frame.pc,(frame.pc//16+1)*16),source_entries(frame),
        (Branch(target,taken,position,kind,0,wrong),))
    model.advance(Events(pc=STREAM_PC,select=busy,feedback=feedback))
    directions=model.direction_proposals()
    nominated=model.offered.victims
    settle(model,busy=busy)
    return directions,nominated


@pytest.mark.parametrize('order',ORDERS)
@pytest.mark.parametrize('phase',PHASES)
@pytest.mark.parametrize('counter',COUNTERS)
def test_cold_original_initializes_the_retained_branch_not_its_new_nomination(order,phase,counter):
    p=Program(order,phase,counter);model=MbtbReference()
    cold=model.lookup_snapshot(PC);before_cold=deepcopy(cold)
    assert not any(s.hit for row in source_entries(cold) for s in row)
    teach(model,model.lookup_snapshot(PC+EARLIER+1),LATER,LATER_TARGET,1)
    for _ in range(2-counter):
        frame=model.lookup_snapshot(PC+EARLIER+1)
        teach(model,frame,LATER,LATER_TARGET,1,taken=False,wrong=bool(frame.values()['3.taken']))
    teach(model,model.lookup_snapshot(PC),EARLIER,INITIAL_TARGET,3)
    current=model.lookup_snapshot(PC);frames=(cold,current);before=deepcopy(frames)
    committed=model.entry_commits
    for index in p.order_indices:
        patches,nominated=teach(model,frames[index],EARLIER,TARGETS[index],3,busy=p.retained)
        assert counter_payload(patches[0,0])==p.direction
        if index==0:assert nominated[0]!=p.owner
    settle(model)
    assert model.entry_commits-committed==len(p.services)
    values=model.lookup_snapshot(PC).values()
    assert (values['2.position'],values['2.target'],values['2.counter'])==(EARLIER,p.final_target,2)
    assert (values['3.position'],values['3.target'],values['3.counter'])==(LATER,LATER_TARGET,counter)
    assert frames==before and cold==before_cold
    assert not any(s.hit for row in source_entries(cold) for s in row)


@pytest.mark.parametrize('flushed',(False,True))
def test_real_owner_progression_not_python_receipt_storage_controls_old_qualification(flushed):
    ledger=WindowLifetimes(16);helper=ledger.admit(PC+0x300,metadata={'history':0})
    cold=ledger.admit(PC,metadata={'history':1});younger=ledger.admit(PC,metadata={'history':2})
    ledger.redirect(helper if flushed else younger)
    resolution=ledger.resolve(cold,{'target':TARGETS[0]})
    if flushed:
        with pytest.raises(LifetimeError,match='flushed'):ledger.qualify(resolution)
    else:
        ledger.live(cold);teaching=ledger.qualify(resolution)
        ledger.accept(teaching,metadata={'history':1},payload={'target':TARGETS[0]})
        assert ledger.active[0] is helper and cold in ledger.active


@pytest.mark.parametrize('missing',RULES)
def test_any_missing_cold_source_effect_or_consumer_prevents_checked_credit(missing):
    coverage=Coverage(Program(ORDERS[0],PHASES[0],0))
    for rule in RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError):coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('order',ORDERS)
@pytest.mark.parametrize('phase',PHASES)
@pytest.mark.parametrize('counter',COUNTERS)
def test_a_complete_cold_semantic_lifetime_only_credits_its_nine_obligations(order,phase,counter):
    coverage=Coverage(Program(order,phase,counter))
    for rule in RULES:coverage.reach(rule)
    coverage.finish();assert coverage.groups['checked'].coverage==12.5
    with pytest.raises(AssertionError):coverage.finish()


def test_cold_and_current_source_bins_are_distinct_semantic_claims():
    from suites.frontend.bpu.bpu.coverage.main_original_order import Coverage as CurrentCoverage
    p=Program(ORDERS[0],PHASES[0],0)
    assert Coverage(p).groups['checked'].instance!=CurrentCoverage(p).groups['checked'].instance
