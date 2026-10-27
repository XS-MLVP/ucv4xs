"""Normal semantic learning independently derives every warm-vector program."""
from copy import deepcopy
from dataclasses import replace
import pytest
from bpuverify.utage.model.semantic import Base, Context, Events, Feedback, Source, UtageReference
from bpuverify.utage.model.dual_source import PROGRAMS, PC
from types import SimpleNamespace
from toffee import ScoreboardMismatch, TransferState
from bpuverify.utage.checker.dual_source import Checks
from bpuverify.utage.coverage.dual_source import Coverage
from bpuverify.utage.transaction.types import UtagePrediction


def query(model, program, state, seed_position=None):
    positions = program.positions(seed_position)
    bases = tuple(Base() if p is None else Base(True,p,bool(p==2),1) for p in positions)
    event = Events(read_pc=PC, read_context=Context(), select=True, pc=PC, context=Context(),
        positions=tuple(0 if p is None else p for p in positions), bases=bases, advance=True)
    model.advance(event); model.advance(event)
    prediction = model.prediction
    providers = prediction.frame.providers()
    for slot, position in enumerate(positions):
        if position is None: continue
        expected = next((table for table,value in enumerate(state) if value is not None and value.position == position),None)
        assert providers[slot] == expected
        if expected is not None:
            entry = prediction.frame.read.entries[expected]
            assert (entry.position,entry.counter) == (position,state[expected].counter)
    return prediction


def feedback(prediction, step):
    frame = prediction.frame
    providers = frame.providers()
    sources = tuple(Source(base.valid, base.position, provider is not None, provider or 0,
        0 if provider is None else frame.read.entries[provider].counter,
        False if provider is None else frame.read.entries[provider].counter >= 4, base.taken)
        for base,provider in zip(prediction.bases,providers,strict=True))
    result = Feedback(PC,Context(),frame.read.indices,sources,step.position,bool(step.taken),step.kind)
    errors = sum((s.predicted if s.hit else s.base) != (s.position == result.position and result.taken)
        for s in sources if s.valid and (s.position < result.position or s.position == result.position and result.kind == 1))
    assert errors <= 1 and bool(errors) == step.error
    return result


def derived(program):
    model = UtageReference()
    originals, records = [], []
    previous, sequences = [0]*1024, [0,0]
    def capture(step):
        nonlocal previous,sequences
        current = [t.get(i,0) for t in model.useful for i in range(512)]
        assert tuple(current) == program.protection_after(step.ordinal+1)
        versions = {}
        for table,cache in enumerate(model.updates):
            if cache.sequence == sequences[table]: continue
            version = cache.recent[-1];entry = version.entry
            versions[str(table)] = dict(sequence=version.sequence,depth=8,next=cache.sequence%8,
                new_cell=dict(valid=int(entry.valid),data_valid=int(entry.valid),index=version.index,
                    tag=entry.tag,position=entry.position,counter=entry.counter))
        assert set(versions) == {str(t) for t in step.writes}
        for table in step.writes: assert versions[str(table)]['new_cell'] == step.cell(table)
        records.append(dict(tick=24+step.ordinal*2,versions=versions,aged=model.aged,
            changes=tuple((i,a,b) for i,(a,b) in enumerate(zip(previous,current,strict=True)) if a!=b)))
        previous, sequences = current,[cache.sequence for cache in model.updates]
    for step in program.steps[:program.preparation_count]:
        original = query(model,program,step.sources,step.seed_position)
        originals.append((original,deepcopy(original.frame)))
        model.advance(Events(feedback=feedback(original,step)));model.advance();model.advance()
        capture(step)
        query(model,program,step.after)
    late = [query(model,program,program.prepared) for _ in range(2)]
    originals.extend((p,deepcopy(p.frame)) for p in late)
    if program.mode == 'adjacent':
        for source,step in zip(late,program.steps[program.preparation_count:],strict=True): model.advance(Events(feedback=feedback(source,step)))
        for step in program.steps[program.preparation_count:]:model.advance();capture(step)
    else:
        for source,step in zip(late,program.steps[program.preparation_count:],strict=True):
            model.advance(Events(feedback=feedback(source,step)));model.advance();model.advance();capture(step)
            query(model,program,step.after)
    query(model,program,program.steps[-1].after)
    assert all(p.frame == snapshot for p,snapshot in originals)
    assert (model.low_tick,model.high_tick) == (program.failed_allocations,)*2
    return model,records


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
def test_unmodified_independent_model_derives_two_warm_providers_and_all_execution_qualifications(program):
    model,records = derived(program)
    assert len(records) == len(program.steps)
    assert {e.position for e in program.prepared} == {2,12}
    if program.result in ('later-direct','later-indirect'):
        assert next(e.counter for e in program.prepared if e.position==12) == 6
    else: assert {e.counter for e in program.prepared} == {0,7}
    assert tuple(e.useful for e in program.prepared) == (3,3)


def witnesses(program):
    model,records = derived(program)
    native = []
    cursors = [0,0]
    for row in records:
        before = tuple(cursors)
        tables = tuple(int(key) for key in row['versions'])
        for table in tables:cursors[table] = (cursors[table]+1)%8
        native.append(dict(tick=row['tick'],tables=tables,before=before,after=tuple(cursors),
            cells={key:deepcopy(value['new_cell']) for key,value in row['versions'].items()}))
        row['native_cursors'] = tuple(cursors)
    checks = Checks(program)
    checks.sent = list(range(len(program.steps)))
    checks.queries = [dict(completed=1) for _ in program.steps]
    monitor = SimpleNamespace(records=records,native_updates=native,failure=None,
        public=[dict(tick=20+i*2) for i in range(len(program.steps))],
        all_protection=lambda:tuple(t.get(i,0) for t in model.useful for i in range(512)))
    return checks,monitor


FAULTS = ('missing-first-effect','wrong-position','wrong-counter','extra-protection-change',
    'extra-native-quiet-write','native-wrong-boundary','native-wrong-write-mask',
    'native-cursor-not-advanced','wrong-sequence','saturation-wrap')


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('fault',FAULTS)
def test_omitted_or_reassigned_branch_learning_is_rejected_even_if_endpoint_could_match(program,fault):
    checks,monitor = witnesses(program)
    ordinal=program.preparation_count-1
    row = monitor.records[ordinal]
    if fault=='missing-first-effect':monitor.records.pop(program.preparation_count)
    elif fault=='wrong-position':row['versions']['0']['new_cell']['position'] ^= 1
    elif fault=='wrong-counter':row['versions']['1']['new_cell']['counter'] ^= 1
    elif fault=='extra-protection-change':row['changes'] += ((7,0,1),)
    elif fault=='extra-native-quiet-write':monitor.native_updates.insert(0,dict(tick=22,tables=(0,),before=(0,0),after=(1,0)))
    elif fault=='native-wrong-boundary':monitor.native_updates[ordinal]['tick'] += 2
    elif fault=='native-wrong-write-mask':monitor.native_updates[ordinal]['tables'] = (0,)
    elif fault=='native-cursor-not-advanced':monitor.native_updates[ordinal]['after'] = monitor.native_updates[ordinal]['before']
    elif fault=='wrong-sequence':row['versions']['0']['sequence'] -= 1
    else:row['versions']['0']['new_cell']['counter'] = 7 if row['versions']['0']['new_cell']['counter']==0 else 0
    with pytest.raises(ScoreboardMismatch) as error:checks.prefix(monitor,len(program.steps))
    assert error.value.context.request['point']


@pytest.mark.parametrize('program',[p for p in PROGRAMS if p.result in ('whole-window-NT','earlier-conditional')],ids=lambda p:p.label)
def test_second_old_feedback_must_accumulate_on_current_confidence(program):
    checks,monitor = witnesses(program)
    step = program.steps[-1]
    table = next(t for t in step.writes if step.after[t].counter != step.sources[t].counter)
    monitor.records[-1]['versions'][str(table)]['new_cell']['counter'] = program.steps[-2].after[table].counter
    with pytest.raises(ScoreboardMismatch):checks.prefix(monitor,len(program.steps))


@pytest.mark.parametrize('program',[p for p in PROGRAMS if len(p.steps[-1].writes)==1],ids=lambda p:p.label)
def test_even_equal_valued_write_to_ineligible_warm_provider_is_rejected(program):
    checks,monitor = witnesses(program)
    inactive = next(t for t in (0,1) if t not in program.steps[-1].writes)
    monitor.native_updates[-1]['tables'] = (0,1)
    monitor.native_updates[-1]['cells'][str(inactive)] = program.steps[-1].cell(inactive)
    monitor.records[-1]['versions'][str(inactive)] = dict(new_cell=program.steps[-1].cell(inactive))
    with pytest.raises(ScoreboardMismatch):checks.prefix(monitor,len(program.steps))


def query_witness(program):
    positions = program.positions()
    expected = Checks.expected_vector(positions,program.prepared)
    rows = [dict(valid=0,hit=0,tableId=1,takenCtr_value=7,cfiPosition=0,baseTaken=0) for _ in range(4)]
    hits,takens = [0]*4,[0]*4
    branches = []
    for slot,value in enumerate(expected):
        if value is None:branches.append(None);continue
        rows[slot] = dict(valid=1,hit=value['hit'],cfiPosition=value['position'],baseTaken=value['base'],
            tableId=value['provider'],takenCtr_value=value['counter'])
        hits[slot],takens[slot] = value['hit'],value['taken']
        branches.append(SimpleNamespace(position=value['position']))
    actual = UtagePrediction(hits[0],takens[0],dict(readIndex=(0,0),abtbResult=rows,
        foldedPathHistForTrain_hist=[dict(foldedHist=0) for _ in Context().folds]),tuple(hits),tuple(takens))
    transfer = SimpleNamespace(state=TransferState.COMPLETED,accepted_event=SimpleNamespace(tick=10),
        completed_event=SimpleNamespace(tick=14),request=SimpleNamespace(pc=PC,read_pc=PC,
            folded_history=0,read_history=0,branches=tuple(branches)))
    entries = (object(),object())
    read = SimpleNamespace(entries=entries,indices=(0,0))
    observed = {12:dict(tick=12,events=SimpleNamespace(select=True,read_pc=PC,read_context=Context()),read=read),
        14:dict(tick=14,frame=SimpleNamespace(pc=PC,context=Context(),read=read))}
    monitor = SimpleNamespace(at=lambda tick:observed[tick])
    return transfer,actual,monitor


QUERY_FAULTS = ('wrong-base','wrong-position','wrong-provider','wrong-confidence','invalid-slot-valid','wrong-output-direction','wrong-completion')


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('fault',QUERY_FAULTS)
def test_vector_slot_cannot_impersonate_instruction_position_or_original_provider(program,fault):
    transfer,source,monitor = query_witness(program)
    slot = next(i for i,p in enumerate(program.positions()) if p is not None)
    entry = source.meta['abtbResult'][slot]
    if fault=='wrong-base':entry['baseTaken'] ^= 1
    elif fault=='wrong-position':entry['cfiPosition'] ^= 1
    elif fault=='wrong-provider':entry['tableId'] = 1-entry['tableId']
    elif fault=='wrong-confidence':entry['takenCtr_value'] ^= 1
    elif fault=='invalid-slot-valid':source.meta['abtbResult'][next(i for i,p in enumerate(program.positions()) if p is None)]['valid'] = 1
    elif fault=='wrong-output-direction':
        directions = list(source.takens);directions[slot] ^= 1;source = replace(source,takens=tuple(directions))
    else:transfer.completed_event.tick += 2
    with pytest.raises(ScoreboardMismatch):Checks(program).query('original',program.positions(),program.prepared,transfer,source,monitor)


MISSING = tuple((program,rule) for program in PROGRAMS for rule in program.rules)


@pytest.mark.parametrize('program,missing',MISSING,ids=[p.label+'.'+r for p,r in MISSING])
def test_any_missing_applicable_semantic_obligation_prevents_checked_credit(program,missing):
    coverage = Coverage(program)
    for rule in program.rules:
        if rule != missing:coverage.reach(rule)
    with pytest.raises(AssertionError,match='incomplete'):coverage.finish()
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
def test_only_the_complete_program_and_applicable_rules_earn_credit(program):
    checks,monitor = witnesses(program)
    checks.prefix(monitor,len(program.steps))
    transfer,source,observed = query_witness(program)
    Checks(program).query('original',program.positions(),program.prepared,transfer,source,observed)
    coverage = Coverage(program)
    for rule in program.rules:coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage == pytest.approx(100*len(program.rules)/len(MISSING))
    with pytest.raises(AssertionError):coverage.finish()
