"""Normal source replay exposes identity mixing even when directions agree."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from toffee import ScoreboardMismatch
from bpuverify.utage.model.semantic import UtageReference,Events,Context,Base,Entry,Source,Feedback,Learning
from bpuverify.utage.model.instruction_confidence import PROGRAMS,RULES,PC
from bpuverify.utage.checker.instruction_confidence import Checks
from bpuverify.utage.coverage.instruction_confidence import Coverage
from tests.utage.scoreboard.test_dual_source import feedback


def derived(program):
    model=UtageReference();originals=[];records=[];native=[]
    previous=[0]*1024;sequences=[0,0]
    def query(state,positions):
        event=Events(read_pc=PC,read_context=Context(),select=True,pc=PC,context=Context(),
            positions=tuple(p or 0 for p in positions),
            bases=tuple(Base() if p is None else Base(True,p,p in (2,7),1) for p in positions),advance=True)
        model.advance(event);model.advance(event);source=model.prediction;actual=source.values()
        for slot,value in enumerate(Checks.expected_vector(positions,state)):
            if value is None:continue
            assert actual[f'{slot}.hit']==value['hit']
            if value['hit']:assert (actual[f'{slot}.provider'],actual[f'{slot}.counter'],actual[f'{slot}.taken'])==(
                value['provider'],value['counter'],value['taken'])
        originals.append((source,deepcopy(source.frame)));return source
    def capture(step):
        nonlocal previous,sequences
        current=[table.get(i,0) for table in model.useful for i in range(512)]
        assert tuple(current)==program.protection_after(step.ordinal+1)
        versions={}
        for table,cache in enumerate(model.updates):
            if sequences[table]==cache.sequence:continue
            version=cache.recent[-1];entry=version.entry
            versions[str(table)]=dict(sequence=version.sequence,depth=8,next=cache.sequence%8,
                new_cell=dict(valid=int(entry.valid),data_valid=int(entry.valid),index=version.index,
                    tag=entry.tag,position=entry.position,counter=entry.counter))
        assert set(versions)=={str(t) for t in step.writes}
        for table in step.writes:assert versions[str(table)]['new_cell']==step.cell(table)
        before=tuple(v%8 for v in sequences);after=tuple(c.sequence%8 for c in model.updates)
        tick=24+step.ordinal*2
        records.append(dict(tick=tick,versions=versions,aged=model.aged,
            changes=tuple((i,a,b) for i,(a,b) in enumerate(zip(previous,current,strict=True)) if a!=b)))
        native.append(dict(tick=tick,tables=step.writes,before=before,after=after,
            cells={key:deepcopy(value['new_cell']) for key,value in versions.items()}))
        previous,sequences=current,[c.sequence for c in model.updates]
    cold=query((None,None),program.positions(program.replacement_position));held=None
    for step in program.steps[:8]:
        source=query(step.sources,program.positions(step.seed_position))
        model.advance(Events(feedback=feedback(source,step)));model.advance();model.advance();capture(step)
        query(step.after,program.positions(consumer=True))
        if step.ordinal+1==program.capture_after:held=[query(step.after,program.positions()) for _ in range(2)]
    pending=program.steps[8:];sources=[cold,*held]
    if program.mode=='adjacent':
        for number,(source,step) in enumerate(zip(sources,pending,strict=True)):
            model.advance(Events(feedback=feedback(source,step)))
            if number>=2:capture(pending[number-2])
        for step in pending[-2:]:model.advance();capture(step)
    else:
        for source,step in zip(sources,pending,strict=True):
            model.advance(Events(feedback=feedback(source,step)));model.advance();model.advance();capture(step)
            query(step.after,program.positions(consumer=True))
    query(pending[-1].after,program.positions(consumer=True))
    assert all(source.frame==saved for source,saved in originals)
    assert (model.low_tick,model.high_tick)==(program.failed_allocations,)*2
    checks=Checks(program);checks.sent=list(range(len(program.steps)));checks.queries=[dict(completed=1) for _ in program.steps]
    monitor=SimpleNamespace(records=records,native_updates=native,failure=None,
        public=[dict(tick=20+i*2) for i in range(len(records))],
        all_protection=lambda:tuple(table.get(i,0) for table in model.useful for i in range(512)))
    return checks,monitor


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
def test_normal_semantics_never_blend_one_instruction_position_and_another_counter(program):
    checks,monitor=derived(program)
    checks.prefix(monitor,len(program.steps))
    first=program.steps[9]
    if program.owner=='different-branch-takeover' and program.mode=='adjacent':
        assert first.before[0].position==7 and first.before[0].counter==3
        assert first.after[0].position==2 and first.after[0].counter==3
        assert first.after[0].counter!=first.before[0].counter-1
    elif program.owner=='same-branch-refresh':assert first.after[0].counter==2


FAULTS=('borrow-new-instruction-counter','drop-companion','wrong-native-mask','extra-equal-write',
    'wrong-counter-owner-position','wrong-protection','wrong-version','wrong-boundary')


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('fault',FAULTS)
def test_incoherent_or_missing_actual_versions_are_rejected(program,fault):
    checks,monitor=derived(program);row=monitor.records[-2]
    if fault=='borrow-new-instruction-counter':
        if '0' in row['versions']:row['versions']['0']['new_cell']['counter']^=1
        else:row['versions']['1']['new_cell']['counter']=6
    elif fault=='drop-companion':row['versions'].pop('1')
    elif fault=='wrong-native-mask':monitor.native_updates[-2]['tables']=()
    elif fault=='extra-equal-write':monitor.native_updates.insert(-1,deepcopy(monitor.native_updates[-2]))
    elif fault=='wrong-counter-owner-position':row['versions']['1']['new_cell']['position']=7
    elif fault=='wrong-protection':row['changes']+=((7,0,1),)
    elif fault=='wrong-version':row['versions']['1']['sequence']-=1
    else:monitor.native_updates[-2]['tick']+=2
    with pytest.raises(ScoreboardMismatch) as error:checks.prefix(monitor,len(program.steps))
    assert error.value.context.request['point']


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('missing',RULES)
def test_partial_handover_has_no_checked_credit(program,missing):
    coverage=Coverage(program)
    for rule in RULES:
        if rule!=missing:coverage.reach(rule)
    with pytest.raises(AssertionError,match='incomplete'):coverage.finish()
    assert coverage.groups['checked'].coverage==0


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
def test_complete_handover_credits_only_its_own_semantic_program(program):
    coverage=Coverage(program)
    for rule in RULES:coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage==pytest.approx(100/len(PROGRAMS))


@pytest.mark.parametrize('forwarded,resident,expected',(
    (Entry(True,0,5,1),Entry(True,0,5,4),0),
    (Entry(True,0,7,1),Entry(True,0,5,4),3),
    (Entry(True,64,5,1),Entry(True,0,5,4),3),
    (Entry(False,0,5,1),Entry(True,0,5,4),3),
    (None,Entry(True,0,5,4),3),
    (Entry(True,0,7,1),None,5),
    (Entry(True,64,5,1),None,5),
    (Entry(True,0,5,1),None,0),
))
def test_only_a_complete_compatible_identity_can_supply_confidence(forwarded,resident,expected):
    model=UtageReference()
    source=Source(True,5,True,0,6,True,False)
    request=Feedback(PC,Context(),(0,0),(source,),5,False,1)
    learning=Learning(request,(0,3),(resident,None),(forwarded,None))
    writes,_,failed=model._learn(learning)
    assert failed and writes[0][1].position==5 and writes[0][1].counter==expected
    assert writes[1] is None
