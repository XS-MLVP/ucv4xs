"""Independent persistent-frame lifetimes and synthetic wrong actuals only."""
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from bpuverify.ras.model.semantic import RasReference,Events,Recovery,Retirement
from bpuverify.bpu.model.ras.capacity import CAPACITY,PRESERVED,OLD_CALL,OLD_RETURN,NEW_CALL,NEW_RETURN,call_address
from bpuverify.bpu.checker.ras.capacity import RasReuseChecks
from bpuverify.bpu.coverage.ras_reuse import RasReuseCoverage


@pytest.mark.parametrize('adjacent,expected',((True,16),(False,15)))
def test_registered_guard_margin_is_a_real_cadence_contract_not_an_extra_capacity_bit(adjacent,expected):
    model=RasReference()
    for _ in range(CAPACITY+3):
        model.advance(Events(action=2,address=call_address(OLD_CALL)))
        if not adjacent:model.advance()
    assert model.program.calls==expected and model.guarded


@pytest.mark.parametrize('preserved',(CAPACITY,CAPACITY-1,CAPACITY-2))
def test_current_restore_cannot_reclaim_and_older_restore_must_cross_below_guard_threshold(preserved):
    model=RasReference();programs=[]
    for _ in range(CAPACITY+2):programs.append(model.program);model.advance(Events(action=2,address=call_address(OLD_CALL)))
    source=programs[preserved]
    model.advance(Events(recovery=Recovery(*source.redirect_key())));model.advance();model.advance()
    assert model.program.calls==preserved
    assert model.guarded==(preserved>CAPACITY-2)


class Program:
    """Synthetic phase-correct actuals qualify the checker, never DUT evidence."""
    def __init__(self):
        self.checks=RasReuseChecks(RasReuseCoverage());self.tick=-1
        self.last=self.step(Events(reset=True))
    def actual(self):
        model=self.checks.model;p=model.projection
        pointer=dict(flag=p['calls']//16,value=p['calls']%16)
        return dict(top=p['top'],redirect_meta=dict(ssp=p['group'],sctr=p['repeat'],tosw=pointer),
            commit_meta=dict(ssp=p['group'],tosw=pointer))
    def retained(self):
        model=self.checks.model
        return dict(head=model.committed_head,cells=tuple(dict(address=f.address//2,counter=f.repeat) for f in model.committed))
    def step(self,events=Events(),pc=OLD_CALL):
        self.tick+=2;c=self.checks
        consumer=dict(valid=1,taken=1,pc=pc,target=c.model.projection['top'])
        c.capture_input(NS(tick=self.tick),events,consumer=consumer);c.raise_failure()
        actual=self.actual();c.capture_output(NS(tick=self.tick+1),actual,retained=self.retained(),consumer=consumer);c.raise_failure()
        self.last=NS(meta_tick=self.tick+1,meta=NS(perf=NS(start_pc=pc),redirect={'ras':deepcopy(actual['redirect_meta'])}))
        return self.last
    def restore(self,source,pc):
        program=self.checks.owned_program(source)
        self.step(Events(recovery=Recovery(*program.redirect_key())),pc);self.step(pc=pc);self.step(pc=pc)
        return program
    def calls(self,count,pc):
        result=[]
        self.step(pc=pc)
        for _ in range(count):result.append(self.last);self.step(Events(action=2,address=call_address(pc)),pc)
        return result
    def returns(self,count,pc):
        result=[]
        self.step(pc=pc)
        for _ in range(count):result.append(self.last);self.step(Events(action=1),pc)
        return result
    def retire(self,sources,action,pc):
        for source in sources:
            program=self.checks.owned_program(source)
            self.step(Events(retirement=Retirement(*program.commit_key(),action)),pc)
        self.step(pc=pc)


def filled():
    p=Program();sources=p.calls(CAPACITY+3,OLD_CALL);p.checks.filled(sources)
    return p,sources


def recovered():
    p,sources=filled();p.restore(sources[-1],OLD_RETURN)
    guarded=p.returns(3,OLD_RETURN);p.checks.guarded_returns(guarded)
    source=sources[PRESERVED];program=p.restore(source,OLD_RETURN);p.checks.recovered(source,program)
    returns=p.returns(3,OLD_RETURN);p.restore(returns[-1],NEW_CALL)
    p.retire(sources[:PRESERVED],2,NEW_CALL);p.retire(returns[:-1],1,NEW_CALL)
    p.checks.old_retired(sources[:PRESERVED],returns[:-1])
    return p,sources,returns


def reused():
    p,sources,returns=recovered();new=p.calls(8,NEW_CALL);p.checks.reused(new)
    p.restore(new[-1],NEW_RETURN);p.retire(new[:-1],2,NEW_RETURN);p.checks.new_retired(new[:-1],new[-1])
    return p,sources,returns,new


def test_complete_lifetime_retains_old_groups_and_new_return_identity_after_cancelled_and_retired_storage_reuse():
    p,originals,old_returns,new=reused();c=p.checks
    assert c.lifecycle.groups['checked'].coverage==0
    returns=p.returns(3,NEW_RETURN);p.retire(returns,1,NEW_RETURN);c.final_returns(returns);c.finish()
    assert c.closed and all(g.coverage==100 for g in c.lifecycle.groups.values())
    assert c.model.program.calls==21 and c.model.retirements==26
    assert c.model.committed[1].address==c.model.committed[2].address==call_address(OLD_CALL)
    assert (c.model.committed[1].repeat,c.model.committed[2].repeat)==(7,3)
    assert (c.model.committed[3].address,c.model.committed[3].repeat)==(call_address(NEW_CALL),3)
    assert c.model.program.head.address==call_address(NEW_CALL) and c.model.program.head.version>=CAPACITY
    # The original cancelled full-capacity suffix can no longer retire.
    with pytest.raises(AssertionError,match='no owned speculative source'):
        c.model.advance(Events(retirement=Retirement(*c.owned_program(originals[-1]).commit_key(),2)))


@pytest.mark.parametrize('fault',('top','group','repeat','calls','retained-address','retained-repeat','tick'))
def test_wrong_actual_is_latched_without_reseeding_the_owned_program_or_retained_groups(fault):
    p,_,_,_=reused();c=p.checks;actual=p.actual();retained=deepcopy(p.retained());tick=p.tick+1
    if fault=='top':actual['top']=call_address(OLD_CALL)//2
    elif fault=='group':actual['redirect_meta']['ssp']^=1
    elif fault=='repeat':actual['redirect_meta']['sctr']^=1
    elif fault=='calls':actual['redirect_meta']['tosw']['value']^=1
    elif fault=='retained-address':retained['cells'][3]['address']=call_address(OLD_CALL)//2
    elif fault=='retained-repeat':retained['cells'][3]['counter']^=1
    else:tick+=2
    before=deepcopy(c.model.state())
    c.capture_output(NS(tick=tick),actual,retained=retained,consumer=dict(valid=1,pc=NEW_RETURN))
    with pytest.raises(AssertionError) as first:c.raise_failure()
    with pytest.raises(AssertionError) as second:c.finish()
    assert first.value is second.value and c.model.state()==before
    assert c.lifecycle.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('missing-source','wrong-pc','wrong-group','wrong-calls','wrong-repeat'))
def test_original_sources_require_the_exact_public_metadata_phase_not_a_nearby_same_pc_context(fault):
    p,sources=filled();s=deepcopy(sources[4]);c=p.checks
    if fault=='missing-source':s.meta_tick+=1000
    elif fault=='wrong-pc':s.meta.perf.start_pc=NEW_CALL
    elif fault=='wrong-group':s.meta.redirect['ras']['ssp']^=1
    elif fault=='wrong-calls':s.meta.redirect['ras']['tosw']['value']^=1
    else:s.meta.redirect['ras']['sctr']^=1
    before=deepcopy(c.model.state())
    with pytest.raises(AssertionError):c.owned_program(s)
    assert c.model.state()==before and c.lifecycle.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('no-real-guarded-calls','no-real-guarded-returns','no-rejected-restore','no-older-restore',
    'no-new-versions','no-kept-new-calls','no-final-new-identity','changed-old-snapshot'))
def test_plans_and_partial_lifetimes_cannot_replace_actual_events_and_consumers(fault):
    p,originals,old_returns,new=reused();c=p.checks
    with pytest.raises(AssertionError):
        if fault=='no-real-guarded-calls':c.blocked_calls.clear();c.filled(originals)
        elif fault=='no-real-guarded-returns':c.blocked_returns.clear();c.guarded_returns(old_returns)
        elif fault=='no-rejected-restore':c.ignored.clear();c.guarded_returns(old_returns)
        elif fault=='no-older-restore':c.restores.clear();c.recovered(originals[PRESERVED],c.owned_program(originals[PRESERVED]))
        elif fault=='no-new-versions':c.calls=[r for r in c.calls if r[2]!=call_address(NEW_CALL)];c.reused(new)
        elif fault=='no-kept-new-calls':c.new_retired([],new[-1])
        else:
            returns=p.returns(3,NEW_RETURN);p.retire(returns,1,NEW_RETURN)
            if fault=='no-final-new-identity':returns[0].meta.perf.start_pc=OLD_RETURN
            else:originals[0].meta.redirect['ras']['ssp']^=1
            c.final_returns(returns)
    assert c.lifecycle.groups['checked'].coverage==0


@pytest.mark.parametrize('phase',('empty','full','old-recovered','new-reused'))
def test_vacuous_or_incomplete_scenarios_never_close_checked_coverage(phase):
    p=Program() if phase=='empty' else filled()[0] if phase=='full' else recovered()[0] if phase=='old-recovered' else reused()[0]
    with pytest.raises(AssertionError):p.checks.finish()
    assert p.checks.lifecycle.groups['checked'].coverage==0


def test_reset_expires_all_lifecycle_witnesses_and_original_sources():
    p,sources=filled();c=p.checks;p.step(Events(reset=True))
    assert not c.calls and not c.blocked_calls and not c.reached and not c.originals and not c.restores
    with pytest.raises(AssertionError):c.owned_program(sources[4])
    assert c.lifecycle.groups['checked'].coverage==0
