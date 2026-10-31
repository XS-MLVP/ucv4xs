"""Unmodified independent semantics and adversarial native-write evidence."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from toffee import ScoreboardMismatch
from suites.frontend.bpu.utage.model.displaced_branch import PROGRAMS, RULES, OWNERS, PC
from suites.frontend.bpu.utage.model.semantic import UtageReference, Events, Base, Context
from suites.frontend.bpu.utage.checker.displaced_branch import Checks
from suites.frontend.bpu.utage.coverage.displaced_branch import Coverage
from tests.utage.scoreboard.test_dual_source import feedback


def derived(program):
    model = UtageReference()
    originals,records,native = [],[],[]
    previous,sequences = [0]*1024,[0,0]

    def query(state,positions):
        event = Events(read_pc=PC,read_context=Context(),select=True,pc=PC,context=Context(),
            positions=tuple(p or 0 for p in positions),
            bases=tuple(Base() if p is None else Base(True,p,bool(p==2),1) for p in positions),advance=True)
        model.advance(event); model.advance(event)
        source = model.prediction
        values = source.values()
        for slot,value in enumerate(Checks.expected_vector(positions,state)):
            if value is None: continue
            assert values[f'{slot}.hit'] == value['hit']
            if value['hit']:
                assert (values[f'{slot}.provider'],values[f'{slot}.counter'],values[f'{slot}.taken']) == (
                    value['provider'],value['counter'],value['taken'])
        originals.append((source,deepcopy(source.frame)))
        return source

    def capture(step):
        nonlocal previous,sequences
        current = [table.get(i,0) for table in model.useful for i in range(512)]
        assert tuple(current) == program.protection_after(step.ordinal+1)
        versions = {}
        for table,cache in enumerate(model.updates):
            if sequences[table] == cache.sequence: continue
            version = cache.recent[-1]; entry = version.entry
            versions[str(table)] = dict(sequence=version.sequence,depth=8,next=cache.sequence%8,
                new_cell=dict(valid=int(entry.valid),data_valid=int(entry.valid),index=version.index,
                    tag=entry.tag,position=entry.position,counter=entry.counter))
        assert set(versions) == {str(t) for t in step.writes}
        for table in step.writes: assert versions[str(table)]['new_cell'] == step.cell(table)
        before = tuple(n%8 for n in sequences)
        after = tuple(cache.sequence%8 for cache in model.updates)
        tick = 24+step.ordinal*2
        records.append(dict(tick=tick,versions=versions,aged=model.aged,
            changes=tuple((i,a,b) for i,(a,b) in enumerate(zip(previous,current,strict=True)) if a!=b)))
        native.append(dict(tick=tick,tables=step.writes,before=before,after=after,
            cells={key:deepcopy(value['new_cell']) for key,value in versions.items()}))
        previous,sequences = current,[cache.sequence for cache in model.updates]

    cold = query((None,None),program.positions(program.replacement_position))
    held = None
    for step in program.steps[:program.preparation_count]:
        if step.ordinal == program.capture_after:
            held = [query(step.before,program.positions()) for _ in range(2)]
        source = cold if step.ordinal == program.preparation_count-1 else query(step.sources,program.positions(step.seed_position))
        model.advance(Events(feedback=feedback(source,step))); model.advance(); model.advance()
        capture(step)
        query(step.after,program.positions(consumer=True))
    late = program.steps[-2:]
    if program.mode == 'adjacent':
        for source,step in zip(held,late,strict=True): model.advance(Events(feedback=feedback(source,step)))
        for step in late: model.advance(); capture(step)
    else:
        for source,step in zip(held,late,strict=True):
            model.advance(Events(feedback=feedback(source,step))); model.advance(); model.advance()
            capture(step)
            query(step.after,program.positions(consumer=True))
    query(late[-1].after,program.positions(consumer=True))
    assert all(source.frame == saved for source,saved in originals)
    assert (model.low_tick,model.high_tick) == (program.failed_allocations,)*2
    checks = Checks(program)
    checks.sent = list(range(len(program.steps)))
    checks.queries = [dict(completed=1) for _ in program.steps]
    monitor = SimpleNamespace(records=records,native_updates=native,failure=None,
        public=[dict(tick=20+i*2) for i in range(len(records))],
        all_protection=lambda:tuple(table.get(i,0) for table in model.useful for i in range(512)))
    return checks,monitor


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
def test_normal_learning_derives_both_resident_identity_policies(program):
    checks,monitor = derived(program)
    checks.prefix(monitor,len(program.steps))
    checks.resident(monitor)
    late = program.steps[-2:]
    assert late[0].sources[0].taken == int(program.original_wrong)
    assert late[0].before[1].counter == 6 and late[0].after[1].counter == 7
    if program.owner == OWNERS[1]:
        assert all(s.writes == (1,) and s.after[0] == s.before[0] for s in late)
    else:
        assert all(s.writes == (0,1) and s.after[0].counter == s.before[0].counter-1 for s in late)
        assert late[-1].after[0].useful == (0 if program.original_wrong else 3)


FAULTS = ('missing-companion-write','wrong-companion-confidence','extra-short-equal-write',
    'original-reclaims-current-position','hidden-native-write','wrong-write-mask',
    'wrong-protection-owner','wrong-native-boundary','wrong-version-sequence')


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('fault',FAULTS)
def test_each_missing_or_misattributed_learning_boundary_is_rejected(program,fault):
    checks,monitor = derived(program)
    row = monitor.records[-2]
    if fault == 'missing-companion-write': row['versions'].pop('1')
    elif fault == 'wrong-companion-confidence': row['versions']['1']['new_cell']['counter'] = 6
    elif fault == 'extra-short-equal-write':
        if '0' in row['versions']: row['versions'].pop('0')
        else: row['versions']['0'] = dict(new_cell=program.steps[-2].cell(0))
    elif fault == 'original-reclaims-current-position':
        row['versions']['1']['new_cell']['position'] = 2
    elif fault == 'hidden-native-write': monitor.native_updates.insert(-1,deepcopy(monitor.native_updates[-2]))
    elif fault == 'wrong-write-mask': monitor.native_updates[-2]['tables'] = ()
    elif fault == 'wrong-protection-owner': row['changes'] += ((7,0,1),)
    elif fault == 'wrong-native-boundary': monitor.native_updates[-2]['tick'] += 2
    else: row['versions']['1']['sequence'] -= 1
    with pytest.raises(ScoreboardMismatch) as error: checks.prefix(monitor,len(program.steps))
    assert error.value.context.request['point']


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
@pytest.mark.parametrize('missing',RULES)
def test_partial_lifetime_never_earns_checked_credit(program,missing):
    coverage = Coverage(program)
    for rule in RULES:
        if rule != missing: coverage.reach(rule)
    with pytest.raises(AssertionError,match='incomplete'): coverage.finish()
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
def test_only_a_complete_declared_program_is_credited(program):
    coverage = Coverage(program)
    for rule in RULES: coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage == pytest.approx(100/len(PROGRAMS))
    with pytest.raises(AssertionError): coverage.finish()
