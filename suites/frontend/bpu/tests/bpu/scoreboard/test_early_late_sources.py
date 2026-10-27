"""Five independent models, one base pipeline, three separate snapshot domains."""
from copy import deepcopy
from dataclasses import replace
import pytest
from bpuverify.bpu.model.early_late_sources import EarlyLateSources
from bpuverify.bpu.model.direction_sources import DirectionSources
from bpuverify.bpu.model.pipeline import Outcome,Resolution,Redirect
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.early_aging import require_recovery_window
from bpuverify.bpu.model.path_history import WIDTH,LAYOUT,SHIFT,path_contribution
from bpuverify.tage.model.semantic import TABLES,HISTORIES
from tests.bpu.scoreboard.test_semantic_pipeline import boot

ENABLED=(False,True,True,True,False,False,False)


class Program:
    def __init__(self,pc=0x40000001,*,early=True,sources_factory=EarlyLateSources):
        self.pc=pc; self.a=0x40000103; self.model,self.event=boot(sources_factory(),pc=self.a)
        enabled=list(ENABLED); enabled[1]=early; self.event=replace(self.event,enabled=tuple(enabled))
        while self.model.control_pipe[-1]!=self.event.enabled: self.model.advance(replace(self.event,reset=True))
        self.tick=0; self.originals=[]; self.repairs=[]; self.inputs=[]
    def step(self,event=None):
        cycle=self.model.advance(self.event if event is None else event); self.tick+=2
        if cycle.final_repair:
            self.repairs.append((self.tick,cycle))
        return cycle
    def quiet(self):
        idle=replace(self.event,prediction_ready=False)
        for _ in range(256):
            self.step(idle)
            if self.model.stages[1:]==(None,None) and not self.model.sources.main_pending(): return idle
        raise AssertionError('declared original learning did not become quiescent')
    def source(self,predicate=lambda _:True,*,pc=None):
        pc=self.pc if pc is None else pc
        for _ in range(256):
            token=self.step().metadata
            if token is not None and token.pc==pc and token.lookup is not None and predicate(token):
                self.originals.append(token); self.quiet(); return token
        raise AssertionError('no declared complete original source')
    def restart(self):
        idle=self.quiet(); source=self.anchor
        require_recovery_window(self.model.history.taken_edges,source.history.taken_edges,
            capacity=WIDTH,history_bits=max(length for length,_ in LAYOUT),shift=SHIFT)
        assert source.pc==self.a
        self.step(replace(idle,redirect=Redirect(source.history,(self.a//8)*8+4,self.pc,True)))
    def query(self): self.restart(); return self.source()
    def resolve(self,source,position,taken,*,wrong,room=False):
        idle=self.quiet(); target=self.pc if source.pc==self.a else self.a
        request=Resolution(source.history,source.pc,
            (Outcome(position,target,Kind.CONDITIONAL if position==2 else Kind.DIRECT,taken,mispredict=wrong),),origin=source)
        if room:
            feedback=self.model.sources.feedback_for(request)
            for _ in range(128):
                owner=self.model.sources.tage.allocation_at_next_accept(feedback)
                if owner is not None and owner[0]<TABLES-1: break
                self.step(idle)
            else: raise AssertionError('no provider allocation leaves a longer-history opportunity')
        self.step(replace(idle,feedback=request)); self.inputs.append(request); self.quiet()
    def early_enabled(self,value):
        self.quiet(); enabled=list(ENABLED); enabled[1]=value; self.event=replace(self.event,enabled=tuple(enabled))
        for _ in range(8):
            self.step(replace(self.event,prediction_ready=False))
            if tuple(self.model.control_pipe[-1])==self.event.enabled: break
        else: raise AssertionError('declared controls were not applied')
        self.quiet()
    def warm(self):
        self.query(); self.restart()
        original=self.source(lambda t:t.early.source in ('ahead','ahead-direction') and t.early.branch.position==2)
        # Keep flowing to a new real predecessor; the cold checkpoint may
        # already be outside the physical retained-history window by now.
        self.anchor=self.source(lambda t:t.early.source=='ahead' and t.early.branch.position==4,pc=self.a)
        return original
    def prepare_late(self):
        self.anchor=self.source(pc=self.a); self.resolve(self.anchor,4,True,wrong=True)
        source=self.query(); self.resolve(source,2,True,wrong=True)
        self.seed=self.warm(); self.early_enabled(False)
        source=self.query(); self.resolve(source,2,False,wrong=True,room=True)
        source=self.query(); self.resolve(source,2,False,wrong=False)
        source=self.query(); self.resolve(source,4,True,wrong=True)
        edge=(path_contribution((self.a//8)*8+4,self.pc)<<SHIFT)^path_contribution((self.pc//8)*8+4,self.a); recent=0
        for bit in range(0,max(HISTORIES),2*SHIFT): recent^=edge<<bit
        recent%=1<<max(HISTORIES)
        self.restart(); self.anchor=self.source(lambda t:t.history.history%(1<<max(HISTORIES))==recent,pc=self.a)
        source=self.query(); self.resolve(source,2,True,wrong=True)
        self.weak=self.query()
        return self.weak
    def prepare(self):
        self.prepare_late()
        self.early_enabled(True)
        self.restart()
        for _ in range(256):
            cycle=self.step()
            if not cycle.final_repair: continue
            token=cycle.tokens[2]; values=self.model.sources.defined_short_metadata(token)
            if any(values.get(f'{w}.valid') and values.get(f'{w}.position')==2 for w in range(4)):
                self.originals.append(token); self.quiet(); return token,cycle
        raise AssertionError('S3 alone is insufficient: an owned early conditional must be qualified')


@pytest.mark.parametrize('pc',(0x40000001,0x40000002))
def test_real_final_correction_has_independent_early_and_late_originals(pc):
    p=Program(pc); token,cycle=p.prepare(); bank=p.model.sources
    assert bank.snapshot(token).owner is bank.short_snapshot(token).owner is bank.tage_snapshot(token).owner is token.history
    assert cycle.decisions[0] is not cycle.decisions[2] and cycle.final_repair
    assert token.early.branch.position==token.middle.branch.position==2
    assert cycle.decisions[2].branch.position==4 and not token.middle_corrected
    feedback=bank.short_feedback(token,cycle.decisions[2])
    assert feedback.pc==token.pc and feedback.position==4 and feedback.kind==2
    assert any(source.valid and source.position==2 for source in feedback.sources)
    assert bank.defined_metadata(token)!=bank.defined_tage_metadata(token)
    assert bank.tage_snapshot(token,resolved=True).late==cycle.decisions[2]


def test_each_of_five_components_advances_once_per_boundary(monkeypatch):
    p=Program(); p.source(pc=p.a); counts=dict.fromkeys(('micro','main','ahead','short','tage'),0)
    for name in counts:
        component=getattr(p.model.sources,name); original=component.advance
        def counted(*args,_name=name,_original=original,**kwargs):
            counts[_name]+=1; return _original(*args,**kwargs)
        monkeypatch.setattr(component,'advance',counted)
    for _ in range(8): p.step()
    assert counts==dict.fromkeys(counts,8)


@pytest.mark.parametrize('domain',('ahead','short','tage-read','tage-resolved'))
@pytest.mark.parametrize('fault',('foreign-checkpoint','retired','reset'))
def test_equal_or_dead_origins_cannot_borrow_any_component_snapshot(domain,fault):
    p=Program(); token,_=p.prepare(); bank=p.model.sources
    if fault=='foreign-checkpoint': token=replace(token,history=replace(token.history))
    elif fault=='retired': p.model.retire_source(token.sequence)
    else: p.model.advance(replace(p.event,reset=True))
    getter={'ahead':bank.snapshot,'short':bank.short_snapshot,'tage-read':bank.tage_snapshot,
        'tage-resolved':lambda t:bank.tage_snapshot(t,resolved=True)}[domain]
    with pytest.raises(ValueError,match='absent|retired|checkpoint'): getter(token)


def test_tage_metadata_projection_never_calls_the_ahead_namespace(monkeypatch):
    from bpuverify.bpu.checker.pipeline import tage_metadata_values
    p=Program(); token,_=p.prepare(); bank=p.model.sources; expected=bank.defined_tage_metadata(token)
    actual=[{} for _ in range(4)]
    for key,value in expected.items():
        slot,field=key.split('.'); actual[int(slot)][field]=value
    def wrong_domain(_): raise AssertionError('Ahead namespace must not supply TAGE metadata')
    monkeypatch.setattr(bank,'defined_metadata',wrong_domain)
    assert tage_metadata_values(bank,token,actual)==(expected,expected)


def test_enabling_early_does_not_copy_or_advance_a_second_main_model():
    p=Program(); token,_=p.prepare(); bank=p.model.sources
    assert not hasattr(bank.directions,'main') and not hasattr(bank.directions,'micro')
    assert bank.tage is bank.directions.tage
    # Micro has no public cycle counter; the five-component advance spy above
    # checks it directly instead of inventing a counter or a private fallback.
    assert bank.main.cycles==bank.ahead.cycles==bank.short.cycles==bank.tage.cycles


def test_old_single_domain_tage_interface_keeps_exact_metadata_and_frames():
    from tests.bpu.scoreboard.test_direction_sources import learned
    model,event,anchor,token=learned(); bank=model.sources
    assert bank.tage_snapshot(token) is bank.snapshot(token)
    assert bank.tage_snapshot(token,resolved=True) is bank.snapshot(token,resolved=True)
    assert bank.defined_tage_metadata(token)==bank.defined_metadata(token)


def test_later_selector_and_learning_changes_cannot_rebase_any_original():
    p=Program(); token,_=p.prepare(); bank=p.model.sources
    snapshots=(bank.snapshot(token),bank.short_snapshot(token),bank.tage_snapshot(token),bank.tage_snapshot(token,resolved=True))
    metadata=deepcopy((bank.defined_metadata(token),bank.defined_short_metadata(token),bank.defined_tage_metadata(token)))
    source=p.query(); p.resolve(source,2,False,wrong=False)
    assert snapshots==(bank.snapshot(token),bank.short_snapshot(token),bank.tage_snapshot(token),bank.tage_snapshot(token,resolved=True))
    assert metadata==(bank.defined_metadata(token),bank.defined_short_metadata(token),bank.defined_tage_metadata(token))
