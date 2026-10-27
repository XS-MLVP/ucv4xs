from bpuverify.bpu.model.early_opposition import FALLBACK
"""Independent two-consumer paths and adversarial actual response controls."""
import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from bpuverify.bpu.model.short_revisit import PROFILES,program,rules
from bpuverify.bpu.model.early_opposition import provider
from bpuverify.bpu.model.pipeline import Redirect
from bpuverify.bpu.checker.short_revisit import Checks
from bpuverify.bpu.coverage.short_revisit import Coverage
from tests.bpu.scoreboard.test_entry_protection import Program as ProtectionProgram
from tests.bpu.scoreboard.test_early_short_protection import Program as WindowProgram


class Program(ProtectionProgram):
    recovery_position=FALLBACK
    def __init__(self,profile):
        self.revisit_profile=profile; super().__init__(program(profile).base_name)
    def make_checks(self,pc,tag_class): return Checks(Coverage(self.revisit_profile),self.revisit_profile)
    def step(self,event=None,*,mutate=None):
        if self.actual_fallback and event is not None and event.redirect is not None:
            event=replace(event,redirect=replace(event.redirect,cfi_pc=(self.pc//16)*16+self.recovery_position))
        return WindowProgram.step(self,event,mutate=mutate)
    def quiet(self):
        idle=super().quiet()
        if self.checks.pending_long is not None: self.step(idle)
        assert self.checks.pending_long is None
        return idle
    def flow(self,source,predicate):
        self.recovery_position=FALLBACK; self.quiet()
        self.step(replace(self.event,redirect=Redirect(source.token.history,self.checks.program.fallback_pc,self.pc,True)))
        self.step()
        for _ in range(64):
            token=self.step().metadata
            if token is not None and token.pc==self.pc and predicate(token):
                result=self.receipt(token); self.quiet(); return result
        raise AssertionError('declared original consumer did not become qualified')
    def prepare_revisit(self):
        source=self.prepared_reward(); return self.contradict(source)
    def consume_long(self):
        c=self.checks; allocation=c.allocation_for_wrong()
        def match(token):
            value=provider(self.model.sources,token)
            return value is not None and (value.table,value.index,value.tag)==(1,allocation['index'],allocation['tag'])
        result=self.flow(c.bridge_source,match); c.long_consumer(result); return result
    def prepare_path(self,source):
        self.enable(False); self.checks.begin_path()
        for position in self.checks.revisit.positions:
            self.recovery_position=position; before=source
            source=self.query(before); self.checks.path_receipt(before,position,source)
        self.recovery_position=FALLBACK; self.checks.path_ready(); return source
    def consume_short(self,source):
        self.enable(True)
        def match(token):
            value=provider(self.model.sources,token)
            return value is not None and value.key==self.checks.protected
        result=self.flow(source,match); self.checks.short_consumer(result); return result
    def complete(self):
        self.prepare_revisit(); source=self.consume_long(); source=self.prepare_path(source)
        return self.consume_short(source)


@pytest.mark.parametrize('profile',PROFILES)
def test_long_priority_then_short_error_result_are_both_independently_consumed(profile):
    p=Program(profile); p.complete(); c=p.checks
    assert c.coverage.groups['checked'].coverage==0
    c.finish_opposition(p.named)
    assert c.closed and c.coverage.closed
    assert c.long['provider']['table']==1 and c.long['provider']['counter']==4
    assert c.short['provider']['table']==0 and c.short['provider']['counter']==1
    assert c.long['allocation']['owner']==c.wrong['owner']
    assert c.long['allocation']['written_tick']+2==c.long['allocation']['actual_confirmation_tick']


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('missing',('read-ancestor','long-consumer','short-consumer','path-edge','actual-long','public-metadata'))
def test_partial_or_rebound_lifetimes_never_get_checked_credit(profile,missing):
    p=Program(profile); p.complete(); c=p.checks
    if missing=='read-ancestor': c.bridge=None
    elif missing=='long-consumer': c.long=None
    elif missing=='short-consumer': c.short=None
    elif missing=='path-edge': c.path.pop()
    elif missing=='actual-long': c.pending_long=dict(unconfirmed=True)
    else:
        source,_=next(iter(c.metadata.values())); source.meta=dict(corrupted=True)
    with pytest.raises(AssertionError): c.finish_opposition(p.named)
    assert c.coverage.groups['checked'].coverage==0


def corrupt_packets(p,table,counter,new_counter):
    step=p.step; seen=[]
    def corrupt(actual):
        for entry in actual['meta']['entries']:
            if entry['valid'] and entry['hit'] and entry['position']==2 and entry['provider']==table and entry['counter']==counter:
                entry['counter']=new_counter; seen.append(p.tick)
    def damaged(event=None,**kwargs):
        kwargs['mutate']=corrupt; return step(event,**kwargs)
    p.step=damaged
    return seen


@pytest.mark.parametrize('profile',PROFILES)
def test_actual_long_counter_is_checked_not_only_expected_allocation(profile):
    p=Program(profile); p.prepare_revisit(); seen=corrupt_packets(p,1,4,5)
    with pytest.raises(AssertionError): p.consume_long()
    assert len(seen)==1 and p.checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',PROFILES)
def test_actual_short_revisit_cannot_revert_to_old_zero(profile):
    p=Program(profile); p.prepare_revisit(); source=p.consume_long(); source=p.prepare_path(source)
    seen=corrupt_packets(p,0,1,0)
    with pytest.raises(AssertionError): p.consume_short(source)
    assert len(seen)==1 and p.checks.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',PROFILES)
def test_equal_copied_read_source_is_not_the_original(profile):
    p=Program(profile); p.prepare_revisit(); c=p.checks; source=c.bridge_source
    c.bridge_source=NS(token=replace(source.token),prediction_tick=source.prediction_tick,meta_tick=source.meta_tick)
    with pytest.raises(AssertionError): p.consume_long()
    assert c.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile,missing',[(p,r) for p in PROFILES for r in rules(p)])
def test_every_both_consumer_obligation_is_required(profile,missing):
    coverage=Coverage(profile)
    for rule in rules(profile):
        if rule!=missing: coverage.record('reached',rule,10); coverage.record('checked',rule,20)
    with pytest.raises(AssertionError): coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('entry',('compressed-entry','conditional-entry'))
def test_older_paths_have_distinct_long_read_contexts_but_same_short_identity(entry):
    programs=[Program(entry+'.older-'+older) for older in ('conditional','fallback')]
    for p in programs: p.complete()
    assert len({p.checks.path[-1]['history']%4096 for p in programs})==2
    assert len({p.checks.short['read_indices'][1] for p in programs})==2
    assert len({tuple(p.checks.short['provider'][k] for k in ('table','index','tag','counter')) for p in programs})==1


def test_case_hides_io_edges_and_task_scheduling():
    for name in ('bpuverify/bpu/case/short_revisit.py','tests/bpu/testcase/test_short_revisit.py'):
        tree=ast.parse(Path(name).read_text()); forbidden={'RisingEdge','FallingEdge','ClockCycles','get_','set_','gather','create_task'}
        assert not {n.id for n in ast.walk(tree) if isinstance(n,ast.Name)} & forbidden
        assert not {n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)} & forbidden
