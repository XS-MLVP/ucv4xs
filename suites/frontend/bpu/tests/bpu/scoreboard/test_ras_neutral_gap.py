"""Hand-derived lifetime boundaries and synthetic checker qualification only."""
from copy import deepcopy
from types import SimpleNamespace as NS
import pytest
from bpuverify.ras.model.semantic import RasReference,Events,Recovery,Retirement
from bpuverify.bpu.checker.ras.neutral_gap import RasNeutralGapChecks
from bpuverify.bpu.checker.ras.retirement import CommitChecker
from bpuverify.bpu.coverage.ras_neutral_gap import RasNeutralGapCoverage,RULES
from bpuverify.bpu.model.ras.capacity import CAPACITY,OLD_CALL,NEW_CALL,NEW_RETURN,call_address
from bpuverify.bpu.model.ras.neutral_gap import NEUTRAL
from tests.bpu.scoreboard.test_retirement_completion import row


@pytest.mark.parametrize('gap',(0,1,2,3,16,32))
def test_neutral_credit_boundary_is_registered_and_never_commits_stack_data(gap):
    m=RasReference()
    for _ in range(gap):m.advance(Events(2,call_address(OLD_CALL)))
    m.advance()
    committed=tuple(m.committed)
    m.advance(Events(retirement=Retirement(*m.program.commit_key(),0)))
    assert m.retired_calls==0 and m.retirements==0
    m.advance()
    assert m.retired_calls==(gap-1 if gap>2 else 0) and m.retirements==1
    assert tuple(m.committed)==committed and m.committed_head==0
    if gap==32:
        assert m.guarded and m.program.head.version==31
        m.advance()
        assert not m.guarded and m.projection['top']==call_address(OLD_CALL)//2


class Program:
    """Phase-correct synthetic actuals are never exported as DUT evidence."""
    def __init__(self):
        self.checks=RasNeutralGapChecks(RasNeutralGapCoverage());self.tick=-1
        self.last=self.step(Events(reset=True))
    def actual(self):
        m=self.checks.model;p=m.projection;ptr=dict(flag=p['calls']//32,value=p['calls']%32)
        return dict(top=p['top'],redirect_meta=dict(ssp=p['group'],sctr=p['repeat'],tosw=ptr),
            commit_meta=dict(ssp=p['group'],tosw=ptr))
    def retained(self):
        m=self.checks.model
        return dict(head=m.committed_head,cells=[dict(address=f.address//2,counter=f.repeat) for f in m.committed])
    def resources(self):
        m=self.checks.model
        return dict(bos=dict(flag=(m.retired_calls%64)//32,value=m.retired_calls%32),guarded=int(m.guarded))
    def step(self,events=Events(),pc=OLD_CALL):
        self.tick+=2;c=self.checks
        consumer=dict(valid=1,taken=1,pc=pc,target=c.model.projection['top'])
        c.capture_input(NS(tick=self.tick),events,consumer=consumer);c.raise_failure()
        actual=self.actual();c.capture_output(NS(tick=self.tick+1),actual,retained=self.retained(),
            consumer=consumer,resources=self.resources());c.raise_failure()
        self.last=NS(meta_tick=self.tick+1,meta=NS(perf=NS(start_pc=pc),redirect={'ras':deepcopy(actual['redirect_meta'])}))
        return self.last
    def restore(self,source,pc):
        program=self.checks.owned_program(source)
        self.step(Events(recovery=Recovery(*program.redirect_key())),pc);self.step(pc=pc);self.step(pc=pc)
    def offers(self,count,pc,action):
        result=[];self.step(pc=pc)
        for _ in range(count):
            result.append(self.last)
            self.step(Events(action,call_address(pc) if action==2 else None),pc)
        return result
    def retire(self,source):
        program=self.checks.owned_program(source)
        self.step(Events(retirement=Retirement(*program.commit_key(),0)),NEUTRAL)
        self.step(pc=NEUTRAL);self.step(pc=NEUTRAL)


def complete():
    p=Program();c=p.checks
    old=p.offers(CAPACITY+3,OLD_CALL,2);c.filled(old)
    p.restore(old[2],NEUTRAL);neutral=p.offers(3,NEUTRAL,0);c.neutral(neutral,calls=2)
    p.retire(neutral[-1]);c.held()
    p.restore(neutral[-1],OLD_CALL);old=p.offers(CAPACITY-2+3,OLD_CALL,2);c.filled(old,start=2)
    p.restore(old[-1],NEUTRAL);neutral=p.offers(3,NEUTRAL,0);c.neutral(neutral,calls=CAPACITY)
    p.retire(neutral[-1]);c.reclaimed()
    p.restore(neutral[-1],NEW_CALL);new=p.offers(8,NEW_CALL,2);c.reused(new)
    p.restore(new[-1],NEW_RETURN);returns=p.offers(3,NEW_RETURN,1);c.returned(returns)
    return p


def test_full_owned_lifetime_closes_only_after_all_actual_comparisons():
    p=complete();c=p.checks
    assert c.lifecycle.groups['reached'].coverage==100 and c.lifecycle.groups['checked'].coverage==0
    c.finish();assert c.lifecycle.groups['checked'].coverage==100
    c.finish()  # Idempotent environment shutdown, not duplicate credit.


@pytest.mark.parametrize('path',(('bos','flag'),('bos','value'),('guarded',)))
def test_bad_readonly_resource_actual_latches_failure_without_checked_credit(path):
    p=complete();resources=p.resources();target=resources
    for key in path[:-1]:target=target[key]
    target[path[-1]]^=1
    p.checks.capture_output(NS(tick=p.tick+1),p.actual(),retained=p.retained(),resources=resources)
    with pytest.raises(AssertionError,match='owned lifetime credit'):p.checks.finish()
    assert p.checks.lifecycle.groups['checked'].coverage==0


@pytest.mark.parametrize('fault',('no-resource','committed-cell','committed-head','top','source-metadata','missing-registered-effect','late-recovery'))
def test_faults_cannot_turn_a_reached_neutral_gap_into_checked_coverage(fault):
    p=complete();c=p.checks
    if fault in ('no-resource','committed-cell','committed-head','top'):
        actual=p.actual();retained=p.retained();resources=p.resources()
        if fault=='no-resource':resources=None
        elif fault=='committed-cell':retained['cells'][7]['address']^=1
        elif fault=='committed-head':retained['head']^=1
        else:actual['top']^=1
        c.capture_output(NS(tick=p.tick+1),actual,retained=retained,resources=resources)
    elif fault=='source-metadata':
        c.originals[0].meta.redirect['ras']['ssp']^=1
        with pytest.raises(AssertionError):c.returned([p.last])
    else:
        if fault=='missing-registered-effect':c.resources=[dict(tick=c.retirements[-1]+1,bos=0,guarded=1)]
        else:c.restores.append(c.retirements[-1])
        with pytest.raises(AssertionError):c.reclaimed()
    with pytest.raises(AssertionError):c.finish()
    assert c.lifecycle.groups['checked'].coverage==0


@pytest.mark.parametrize('missing',range(len(RULES)))
def test_every_semantic_obligation_is_required_before_credit(missing):
    p=complete();c=p.checks;c.reached.remove(missing)
    with pytest.raises(AssertionError,match='all neutral lifetime obligations'):c.finish()
    assert c.lifecycle.groups['checked'].coverage==0


def test_reset_expires_previous_lifetime_and_all_completion_obligations():
    p=complete();p.step(Events(reset=True))
    c=p.checks
    assert not c.reached and not c.retirements and not c.restores and not c.originals
    with pytest.raises(AssertionError,match='needs reset, genuine retirement'):c.finish()


def source_context():
    checker=CommitChecker();tick=20;pc=OLD_CALL
    meta=dict(ssp=2,tosw=dict(flag=1,value=0))
    resolve=dict(owner='actual-resolve');redirect=dict(ras=dict(ssp=2,sctr=7,tosw=deepcopy(meta['tosw'])))
    transaction=NS(meta_tick=tick,prediction_tick=tick-4,
        meta=NS(perf=NS(start_pc=pc),resolve=resolve,redirect=redirect))
    checker.records=[dict(tick=tick,public_meta=dict(valid=1,pc=pc,bits=meta),
        spec=dict(valid=1,enable=1,action=0,pc_bytes=pc*2,position=15))]
    phr=NS(records=[dict(tick=tick,public_meta=dict(bits=dict(perf=dict(start_pc=pc),resolve=deepcopy(resolve),redirect=deepcopy(redirect))))])
    return checker,transaction,phr


def test_neutral_request_uses_exact_actual_source_and_invents_no_return_address():
    c,source,phr=source_context();request=c.request_for(source,0,phr)
    assert request['meta']==dict(ssp=2,tosw=dict(flag=1,value=0)) and request['return_address'] is None
    assert request['branch_type']==2
    with pytest.raises(AssertionError,match='ordered-nonduplicate-source'):c.request_for(source,0,phr)


@pytest.mark.parametrize('fault',('tick','pc','valid','enabled','actual-call','actual-return','resolve','redirect'))
def test_neutral_request_cannot_reclassify_or_realign_an_unrelated_source(fault):
    c,source,phr=source_context()
    if fault=='tick':source.meta_tick+=2
    elif fault=='pc':source.meta.perf.start_pc^=1
    elif fault=='valid':c.records[0]['spec']['valid']=0
    elif fault=='enabled':c.records[0]['spec']['enable']=0
    elif fault=='actual-call':c.records[0]['spec']['action']=2
    elif fault=='actual-return':c.records[0]['spec']['action']=1
    elif fault=='resolve':phr.records[0]['public_meta']['bits']['resolve']={}
    else:phr.records[0]['public_meta']['bits']['redirect']={}
    with pytest.raises(AssertionError):c.request_for(source,0,phr)
    assert c.last_source_tick==-1


@pytest.mark.parametrize('action',(0,1,2))
def test_only_neutral_notification_can_leave_a_stale_committed_cursor_unchanged(action):
    c=CommitChecker();c.observe(row(c,reset=1),2)
    request=dict(action=action,branch_type=3 if action==1 else 2,
        meta=dict(ssp=2,tosw=dict(flag=1,value=0)),return_address=call_address(NEW_CALL)//2 if action==2 else None)
    c.planned.append(request)
    c.observe(row(c,commit={key:deepcopy(request[key]) for key in ('action','branch_type','meta')}),4)
    actual=row(c,pending=dict(valid=1,push=int(action==2),pop=int(action==1),ssp=2,tosw=dict(flag=1,value=0)))
    if action:
        with pytest.raises(AssertionError,match='ordered-source-ssp'):c.observe(actual,6)
        assert not c.applied
    else:
        before=c.reference;c.observe(actual,6)
        assert c.checked_applied==0
        c.observe(row(c),8)
        assert c.summary()['applied']==1 and c.reference==before


def test_neutral_notification_does_not_finish_before_actual_committed_data_comparison():
    c=CommitChecker();c.observe(row(c,reset=1),2)
    request=dict(action=0,branch_type=2,meta=dict(ssp=2,tosw=dict(flag=1,value=0)),return_address=None)
    c.planned.append(request)
    c.observe(row(c,commit={key:deepcopy(request[key]) for key in ('action','branch_type','meta')}),4)
    c.observe(row(c,pending=dict(valid=1,push=0,pop=0,ssp=2,tosw=dict(flag=1,value=0))),6)
    with pytest.raises(AssertionError,match='all-effects-compared'):c.summary()


@pytest.mark.parametrize('action',(True,False,3,-1,None))
def test_unsupported_notification_does_not_advance_source_ownership(action):
    c,source,phr=source_context()
    with pytest.raises(ValueError):c.request_for(source,action,phr)
    assert c.last_source_tick==-1
