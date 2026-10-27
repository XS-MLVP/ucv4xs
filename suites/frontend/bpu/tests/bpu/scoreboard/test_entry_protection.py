"""Pure full source programs; actual packets here are synthetic, not DUT credit."""
from dataclasses import replace
from pathlib import Path
import ast
import pytest
from bpuverify.bpu.model.entry_protection import PROFILES,program,rules
from bpuverify.bpu.model.early_opposition import provider,main_counter
from bpuverify.bpu.model.pipeline import Redirect
from bpuverify.bpu.checker.entry_protection import Checks
from bpuverify.bpu.coverage.entry_protection import Coverage
from tests.bpu.scoreboard.test_early_opposition import Program as SourceProgram
from tests.bpu.scoreboard.test_early_short_protection import Program as WindowProgram


class Program(SourceProgram):
    def __init__(self,profile):
        self.profile=profile; self.actual_fallback=False
        super().__init__(program(profile).pc)
    def make_checks(self,pc,tag_class): return Checks(Coverage(self.profile),self.profile)
    def step(self,event=None,*,mutate=None):
        if self.actual_fallback and event is not None and event.redirect is not None:
            event=replace(event,redirect=replace(event.redirect,cfi_pc=self.checks.program.fallback_pc))
        return WindowProgram.step(self,event,mutate=mutate)
    def quiet(self):
        idle=super().quiet()
        if self.checks.pending_loss is not None: self.step(idle)
        assert self.checks.pending_loss is None
        return idle
    def prepared_reward(self):
        source=self.opposed(); self.checks.opposed_consumer(source); self.quiet()
        self.checks.reward_receipt(source); return source
    def contradict(self,source):
        self.actual_fallback=True; source=self.steer(source,3); source=self.query(source); self.enable(True)
        self.quiet()
        self.checks.before_flowing_recovery(source)
        self.step(replace(self.event,redirect=Redirect(source.token.history,self.checks.program.fallback_pc,self.pc,True)))
        self.step()
        for _ in range(64):
            token=self.step().metadata
            if token is None or token.pc!=self.pc: continue
            value=provider(self.model.sources,token)
            if (value is not None and value.key==self.checks.protected and value.counter<4
                    and main_counter(token)==3 and token.middle.branch.position==2 and token.middle.branch.taken):
                source=self.receipt(token); self.quiet(); self.checks.wrong_receipt(source); return source
        raise AssertionError('no qualified original interior contradiction')
    def complete(self):
        source=self.prepared_reward()
        if self.checks.program.mode=='contradiction': source=self.contradict(source)
        final=self.query(source); self.checks.final_source(final); self.quiet(); return final


@pytest.mark.parametrize('profile',PROFILES)
def test_complete_interior_original_protection_has_real_source_effect_and_next_actual_boundary(profile):
    p=Program(profile); p.complete(); c=p.checks
    assert c.coverage.groups['checked'].coverage==0
    c.finish_opposition(p.named)
    assert c.closed and c.coverage.closed
    assert c.reward['after']==c.reward['before']+1
    if c.program.mode=='contradiction':
        loss=c.wrong['loss']; assert loss['after']==loss['before']-1
        assert not c.wrong['provider']['base'] and c.wrong['provider']['counter']<4
        assert loss['written_tick']+2==loss['actual_confirmation_tick']
    assert c.final['prediction_tick']>c.reward['actual_confirmation_tick']


@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('missing',('reward-owner','final-source','original-snapshot','actual-reward'))
def test_incomplete_or_rebound_original_proof_never_gets_checked_credit(profile,missing):
    p=Program(profile); p.complete(); c=p.checks
    if missing=='reward-owner': c.reward=dict(c.reward,owner=c.reward['owner']+10000)
    elif missing=='final-source': c.final=None
    elif missing=='actual-reward': c.pending_loss=dict(not_confirmed=True)
    else:
        source,snapshot=next(iter(c.saved_sources.values()))
        c.saved_sources[source.meta_tick]=source,replace(snapshot,end_position=15)
    with pytest.raises(AssertionError): c.finish_opposition(p.named)
    assert c.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile',[p for p in PROFILES if program(p).mode=='contradiction'])
@pytest.mark.parametrize('fault',('wrong-owner','missing-next-actual','wrong-base'))
def test_wrong_consistent_prediction_requires_its_own_actual_penalty(profile,fault):
    p=Program(profile); source=p.prepared_reward(); source=p.contradict(source); c=p.checks
    if fault=='wrong-owner': c.losses=[dict(r,owner=r['owner']+10000) for r in c.losses]
    elif fault=='missing-next-actual': c.losses=[]
    else:
        token=source.token; saved=p.model.sources.short_snapshot(token)
        # Corrupt the immutable original's base: this tests source qualification,
        # not the DUT nor an alternative oracle.
        bases=list(saved.prediction.bases)
        lane=next(i for i,b in enumerate(bases) if b.position==2 and b.valid)
        bases[lane]=replace(bases[lane],taken=True)
        p.model.sources.short_reads[token.history.sequence]=replace(saved,prediction=replace(saved.prediction,bases=tuple(bases)))
    c.wrong=None
    with pytest.raises(AssertionError): c.wrong_receipt(source)
    assert c.coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('profile,missing',[(p,r) for p in PROFILES for r in rules(p)])
def test_every_original_protection_obligation_is_mandatory_before_atomic_credit(profile,missing):
    coverage=Coverage(profile)
    for rule in rules(profile):
        if rule!=missing: coverage.record('reached',rule,10); coverage.record('checked',rule,20)
    with pytest.raises(AssertionError): coverage.finish()
    assert coverage.groups['checked'].coverage==0


def test_case_hides_edges_io_and_concurrency_scheduling():
    for name in ('bpuverify/bpu/case/entry_protection.py','tests/bpu/testcase/test_entry_protection.py'):
        tree=ast.parse(Path(name).read_text()); forbidden={'RisingEdge','FallingEdge','ClockCycles','get_','set_','gather','create_task'}
        assert not {n.id for n in ast.walk(tree) if isinstance(n,ast.Name)} & forbidden
        assert not {n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)} & forbidden
