"""Independent semantic replay and deliberate wrong-owner/qualification faults."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from toffee import ScoreboardMismatch
from suites.frontend.bpu.utage.model.semantic import UtageReference, Events
from suites.frontend.bpu.utage.model.returning_original import PROGRAMS, RULES, QUALIFICATIONS
from suites.frontend.bpu.utage.coverage.returning_original import Coverage
from suites.frontend.bpu.utage.checker.read_lifetime import LateReplacementChecks
from tests.utage.scoreboard.test_semantic_model import lookup, learn, feedback
from tests.utage.scoreboard.test_read_lifetime_model import bases, values


def derived(program):
    model = UtageReference()
    held, saved, records = {}, [], []
    previous, sequences = [0]*1024, [0, 0]

    def source(spec, expected=None):
        prediction = lookup(model, spec.pc, spec.history, read_pc=spec.read_pc,
            read_history=spec.history, bases=bases(spec.base))
        assert values(prediction) == (spec.expected if expected is None else expected)
        assert prediction.values()['0.base'] == spec.base
        saved.append((prediction, deepcopy(prediction.frame)))
        return prediction

    def capture():
        nonlocal previous, sequences
        current = [table.get(i, 0) for table in model.useful for i in range(512)]
        versions = {}
        for table, cache in enumerate(model.updates):
            if sequences[table] == cache.sequence: continue
            version = cache.recent[-1]
            entry = version.entry
            versions[str(table)] = dict(sequence=version.sequence, depth=8, next=cache.sequence%8,
                new_cell=dict(valid=int(entry.valid), data_valid=int(entry.valid), index=version.index,
                    tag=entry.tag, position=entry.position, counter=entry.counter))
        records.append(dict(tick=24+len(records)*2, versions=versions, aged=model.aged,
            changes=tuple((i,a,b) for i,(a,b) in enumerate(zip(previous,current,strict=True)) if a != b)))
        previous, sequences = current, [cache.sequence for cache in model.updates]

    for step in program.steps[:-2]:
        if step.name == 'B-enter': held['old-A-return'] = source(program.old_a)
        original = source(step.source)
        learn(model, feedback(original, taken=bool(step.actual)))
        capture()
        assert tuple(previous) == program.protection_after(step.ordinal+1)
    held['old-B-return'] = source(program.old_b)
    late = program.steps[-2:]
    if program.mode == 'adjacent':
        for step in late: model.advance(Events(feedback=feedback(held[step.name], taken=bool(step.actual))))
        model.advance(); capture(); model.advance(); capture()
    else:
        for step in late:
            learn(model, feedback(held[step.name], taken=bool(step.actual)))
            capture()
            if step.name == 'old-A-return':
                for spec, expected in program.consumers(after_a=True): source(spec, expected)
    for spec, expected in program.consumers(after_a=False): source(spec, expected)
    assert all(prediction.frame == snapshot for prediction,snapshot in saved)
    assert tuple(previous) == program.protection_after(len(program.steps))
    assert (model.low_tick, model.high_tick) == (program.failed_allocations,)*2
    checks = LateReplacementChecks(program)
    checks.sent = list(range(len(program.steps)))
    checks.originals = [dict(completed=1) for _ in program.steps]
    monitor = SimpleNamespace(records=records, failure=None,
        public=[dict(tick=20+i*2) for i in range(len(records))],
        all_protection=lambda: tuple(table.get(i,0) for table in model.useful for i in range(512)))
    return checks, monitor


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda program: program.label)
def test_all_qualifications_are_derived_from_normal_learning_and_distinct_originals(program):
    checks, monitor = derived(program)
    checks.prefix(monitor, len(program.steps))
    a, b = program.steps[-2:]
    assert a.before.useful == 1 and a.before.counter in (0,7)
    assert a.after.counter != a.before.counter and b.after.counter != a.after.counter
    assert a.after.useful == (2,1,0)[QUALIFICATIONS.index(program.qualification)]
    assert a.companion == program.a_wrong
    assert b.companion == (not program.a_wrong or program.mode == 'adjacent')


FAULTS = ('first-old-inherits-current-counter', 'second-old-inherits-first-counter',
    'wrong-original-protection-qualification', 'wrong-companion-qualification',
    'first-retag-hidden-by-second', 'wrong-original-tag', 'wrong-chronology', 'other-protection-changed')


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda program: program.label)
@pytest.mark.parametrize('fault', FAULTS)
def test_current_owner_or_current_correctness_cannot_replace_original_evidence(program, fault):
    checks, monitor = derived(program)
    row = monitor.records[-2]
    if fault == 'first-old-inherits-current-counter': row['versions']['0']['new_cell']['counter'] = program.steps[-2].before.counter
    elif fault == 'second-old-inherits-first-counter': monitor.records[-1]['versions']['0']['new_cell']['counter'] = program.steps[-2].after.counter
    elif fault == 'wrong-original-protection-qualification': row['changes'] += ((0,1,(program.steps[-2].after.useful+1)%4),)
    elif fault == 'wrong-companion-qualification':
        if program.a_wrong: row['versions'].pop('1')
        else: row['versions']['1'] = deepcopy(monitor.records[-1]['versions']['1'])
    elif fault == 'first-retag-hidden-by-second': monitor.records.pop(-2)
    elif fault == 'wrong-original-tag': row['versions']['0']['new_cell']['tag'] ^= 1<<8
    elif fault == 'wrong-chronology': row['versions']['0']['sequence'] -= 1
    else: row['changes'] += ((7,0,1),)
    with pytest.raises(ScoreboardMismatch) as error: checks.prefix(monitor, len(program.steps))
    assert error.value.context.request['point']


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda program: program.label)
@pytest.mark.parametrize('missing', RULES)
def test_missing_part_of_combined_lifetime_never_earns_checked_credit(program, missing):
    coverage = Coverage(program)
    for rule in RULES:
        if rule != missing: coverage.reach(rule)
    with pytest.raises(AssertionError, match='incomplete'): coverage.finish()
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda program: program.label)
def test_only_one_complete_qualification_cohort_is_credited(program):
    coverage = Coverage(program)
    for rule in RULES: coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage == pytest.approx(100/len(PROGRAMS))
    with pytest.raises(AssertionError): coverage.finish()
