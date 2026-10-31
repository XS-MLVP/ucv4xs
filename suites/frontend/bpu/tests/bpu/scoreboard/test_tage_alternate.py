"""Independent hierarchy learning, event qualification and negative consumers."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from toffee import ScoreboardMismatch

from suites.frontend.bpu.bpu.case.definitions import PC
from suites.frontend.bpu.bpu.case.tage.alternate import POSITIONS, TARGETS
from suites.frontend.bpu.bpu.checker.tage.alternate import TageAlternateChecker, observed_alternate
from suites.frontend.bpu.bpu.coverage.tage.alternate import AlternateCoverage
from suites.frontend.bpu.bpu.model.selection import fallthrough
from suites.frontend.bpu.bpu.transaction.types import BpuPrediction
from suites.frontend.bpu.tage.model.semantic import Base, Branch, Context, Events, Feedback, Hint, decide
from tests.tage.scoreboard.test_semantic_model import actual_prediction, learn, lookup


def checked_source(*,strong=False,swapped=False,checker=None):
    checker = TageAlternateChecker(AlternateCoverage(),pc=PC,positions=POSITIONS,targets=TARGETS) if checker is None else checker
    model = checker.model
    model.reset()
    position = POSITIONS[-1]
    def allocate(tx,owner):
        for _ in range(128):
            before = deepcopy(model.state())
            candidate = model.allocation_at_next_accept(tx)
            assert model.state()==before
            if candidate==owner:
                break
            model.advance()
        else:
            raise AssertionError('independent allocation opportunity not reached')
        learn(model,tx)
    allocate(Feedback(PC,Context(),(Branch(position,False,1,True,True,2),)),(2,0))
    for counter in (3,2):
        learn(model,Feedback(PC,Context(),(Branch(position,False,1,False,True,0,
            Hint(True,False,counter==2,2,0,counter,0,False,False)),)))
    allocate(Feedback(PC,Context(),(Branch(position,True,1,True,True,0,
        Hint(True,False,True,2,0,1,0,False,True)),)),(3,0))
    if strong:
        learn(model,Feedback(PC,Context(),(Branch(position,True,1,True,True,3,
            Hint(True,True,False,3,0,4,0,False,True)),)))
    positions = (0,0,*POSITIONS) if swapped else (0,0,*reversed(POSITIONS))
    frame = lookup(model,pc=PC,positions=positions)
    assert tuple((t,w,c) for t,w,c,u in frame.read.matches(position)) == ((2,0,3 if strong else 2),(3,0,5 if strong else 4))
    bases = tuple(Base(True,p,p==position,True,1) if p else Base() for p in positions)
    checker.initialized = True
    tick = checker.expected[-1][0]+16 if checker.expected else 4
    checker.events,checker.input_tick = Events(advance=True),tick-1
    wanted = decide(frame,bases,model.selectors)
    actual = actual_prediction(wanted)
    extras = {name:tuple(wanted.get(f'{slot}.{field}',0) for slot in range(4))
              for name,field in (('fast_valids','fast_valid'),('fast_takens','fast_taken'),('sc_counters','sc_counter'))}
    checker.capture_output(SimpleNamespace(tick=tick),actual,bases=bases,enabled=True,extras=extras)
    checker.raise_failure()
    branch = fallthrough(PC).branch
    main = [dict(rawHit=int(bool(p)),position=p,counter_value=3 if p==position else 0) for p in positions]
    source = SimpleNamespace(prediction_tick=tick,meta_tick=tick+4,
        prediction=BpuPrediction(PC,branch.target,0,branch.position,0,0),
        meta=SimpleNamespace(resolve={'tage_entries':deepcopy(actual.metas),'mbtb_entries':(main[:2],main[2:])}))
    repairs = [(tick+2,BpuPrediction(PC,TARGETS[-1],1,position,1,0))]
    if not strong:
        repairs.append((tick+4,BpuPrediction(PC,branch.target,0,branch.position,0,1)))
    return checker,source,tuple(repairs),(frame,bases,actual,extras)


@pytest.mark.parametrize('swapped',(False,True))
def test_learned_hierarchy_overrides_the_opposite_base_then_strong_provider_reclaims_selection(swapped):
    checker,source,repairs,_ = checked_source(swapped=swapped)
    assert checker.consumer(source,repairs)=='weak'
    checker,source,repairs,_ = checked_source(strong=True,swapped=swapped,checker=checker)
    assert checker.consumer(source,repairs)=='strong'
    checker.finish()
    assert all(group.coverage==100 for group in checker.coverage.groups.values())


@pytest.mark.parametrize('fault',('missing-middle','missing-final','extra','target','pc','tick','stage','metadata'))
def test_bad_hierarchy_consumer_is_latched_without_golden_resynchronization(fault):
    checker,source,repairs,_ = checked_source()
    repairs = list(repairs)
    if fault=='missing-middle': repairs.pop(0)
    elif fault=='missing-final': repairs.pop()
    elif fault=='extra': repairs.append((source.meta_tick,repairs[0][1]))
    elif fault=='target': repairs[1] = source.meta_tick,replace(repairs[1][1],target=TARGETS[-1])
    elif fault=='pc': repairs[0] = repairs[0][0],replace(repairs[0][1],start_pc=PC+16)
    elif fault=='tick': repairs[1] = source.meta_tick+2,repairs[1][1]
    elif fault=='stage': repairs[0] = repairs[0][0],replace(repairs[0][1],s2_override=0,s3_override=1)
    else: source.meta.resolve['tage_entries'][2]['altOrBasePred'] = 1
    before = deepcopy(checker.model.state())
    coverage = checker.coverage.groups['checked'].coverage
    with pytest.raises(ScoreboardMismatch) as first: checker.consumer(source,tuple(repairs))
    assert checker.model.state()==before and checker.coverage.groups['checked'].coverage==coverage
    with pytest.raises(ScoreboardMismatch) as second: checker.finish()
    assert first.value is second.value


@pytest.mark.parametrize('fault',('extra-same-target-final','sentinel-counter'))
def test_strong_phase_cannot_hide_an_extra_correction_or_modified_sentinel(fault):
    checker,source,repairs,_ = checked_source()
    checker.consumer(source,repairs)
    checker,source,repairs,_ = checked_source(strong=True,checker=checker)
    if fault=='extra-same-target-final':
        repairs = (*repairs,(source.meta_tick,replace(repairs[0][1],s2_override=0,s3_override=1)))
    else:
        source.meta.resolve['mbtb_entries'][1][1]['counter_value'] = 1
    before = deepcopy(checker.model.state())
    coverage = checker.coverage.groups['checked'].coverage
    with pytest.raises(ScoreboardMismatch): checker.consumer(source,repairs)
    assert checker.model.state()==before and checker.coverage.groups['checked'].coverage==coverage


def test_corrupt_qualified_direction_does_not_earn_checked_alternate_credit():
    checker,_,_,(_,bases,actual,extras) = checked_source()
    checker.coverage = AlternateCoverage()
    checker.input_tick = 5
    actual = replace(actual,takens=(0,0,1,0))
    before = deepcopy(checker.model.state())
    checker.capture_output(SimpleNamespace(tick=6),actual,bases=bases,enabled=True,extras=extras)
    with pytest.raises(ScoreboardMismatch,match='taken'): checker.finish()
    assert checker.model.state()==before
    assert checker.coverage.groups['reached'].coverage > 0
    assert checker.coverage.groups['checked'].coverage == 0


def test_a_frozen_hierarchy_frame_cannot_earn_new_prediction_event_credit():
    checker,_,_,(_,bases,actual,extras) = checked_source()
    checker.coverage = AlternateCoverage()
    checker.events = replace(checker.events,advance=False)
    checker.input_tick = 5
    before = deepcopy(checker.model.state())
    checker.capture_output(SimpleNamespace(tick=6),actual,bases=bases,enabled=True,extras=extras)
    checker.raise_failure()
    assert checker.model.state()==before
    assert all(group.coverage==0 for group in checker.coverage.groups.values())
    assert all(tick!=6 for tick,phase in checker.routes)


@pytest.mark.parametrize('fault',('no-provider','no-alternate','same-as-base','wrong-table','no-base','not-opposing','wrong-position','weak-alternate'))
def test_planned_or_nondiscriminating_alternate_conditions_do_not_qualify(fault):
    _,_,_,(frame,bases,actual,_) = checked_source()
    actual = deepcopy(actual)
    slot = 2
    if fault=='no-provider': actual.metas[slot]['hasProvider'] = 0
    elif fault=='no-alternate': actual.metas[slot]['hasAlt'] = 0
    elif fault=='same-as-base': actual.metas[slot]['altOrBasePred'] = 1
    elif fault=='wrong-table': actual.metas[slot]['providerTableIdx'] = 1
    elif fault=='no-base': bases = (*bases[:slot],Base(),bases[3])
    elif fault=='not-opposing': bases = (*bases[:slot],replace(bases[slot],taken=False),bases[3])
    elif fault=='wrong-position': frame = replace(frame,positions=(0,0,11,8))
    else: actual.metas[slot]['altConf'] = 0
    assert observed_alternate(frame,bases,actual,POSITIONS[-1]) is None


def statement(source,name):
    text = re.sub(r'//[^\n]*','',source)
    start = text.index(name+' =')
    return re.sub(r'\s+','',text[start:text.index(';',start)])


@pytest.mark.parametrize('presence',range(256))
def test_compiled_highest_table_alt_guard_does_not_make_the_outer_alt_expression_unreachable(presence):
    # Local two-state Boolean review only: no native denominator exclusion,
    # no broad formal claim, and no runtime/golden use of compiled RTL text.
    source = Path('rtl/bpu/Tage.sv').read_text()
    assert statement(source,'_GEN_9') == '_GEN_9={s2_hits_2_7,s2_hits_2_6}'
    assert statement(source,'_GEN_10') == '_GEN_10={s2_hits_2_7,s2_hits_2_6,s2_hits_2_5,s2_hits_2_4}'
    assert statement(source,'_GEN_11') == '_GEN_11={s2_hits_2_3,s2_hits_2_2}'
    assert statement(source,'providerTableOH_2') == "providerTableOH_2=(|_GEN_10)?((|_GEN_9)?((|s2_hits_2_7)?8'h80:8'h40):(|s2_hits_2_5)?8'h20:8'h10):(|_GEN_11)?((|s2_hits_2_3)?8'h8:8'h4):(|s2_hits_2_1)?8'h2:8'h1"
    assert statement(source,'_hitTableMaskNoProvider_T_2') == '_hitTableMaskNoProvider_T_2=~providerTableOH_2'
    assert statement(source,'_alt_T_49') == '_alt_T_49=(|s2_hits_2_7)&_hitTableMaskNoProvider_T_2[7]'
    hit = tuple(bool(presence & (1<<table)) for table in range(8))
    provider = 1 << max((t for t in range(8) if hit[t]), default=0)
    highest_alt = hit[7] and not (provider & 128)
    shorter_alt = hit[6] and not (provider & 64)
    assert not highest_alt
    assert bool(highest_alt or shorter_alt) == bool(hit[7] and hit[6])
