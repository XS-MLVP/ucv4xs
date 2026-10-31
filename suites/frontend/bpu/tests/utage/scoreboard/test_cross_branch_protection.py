"""Normal semantic executions plus adversarial four-branch source witnesses."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest
from toffee import TransferState
from suites.frontend.bpu.utage.model.semantic import UtageReference, Events, Context
from suites.frontend.bpu.utage.model.cross_branch_protection import PROGRAMS, Program, RULES, POSITION
from suites.frontend.bpu.utage.checker.cross_branch_protection import Checks
from suites.frontend.bpu.utage.coverage.cross_branch_protection import Coverage
from suites.frontend.bpu.utage.checker.checking import UtageUsefulChecker
from suites.frontend.bpu.utage.transaction.types import UtageTraining
from tests.utage.scoreboard.test_semantic_model import lookup, feedback
from tests.utage.scoreboard.test_read_lifetime_model import bases
from tests.utage.scoreboard.test_selective_protection_controls import actual


def exercise(program, *, stop=None):
    model = UtageReference()
    checks = Checks(program)
    rows, sources = {}, {}
    monitor = NS(records=[], public=[], failure=None, at=rows.__getitem__,
        all_protection=lambda: tuple(table.get(i, 0) for table in model.useful for i in range(512)))
    tick = lambda: 100+model.cycles*2
    def query(owner, history, base):
        model.advance()
        accepted = tick()
        prediction = lookup(model, program.pc(owner), history, read_pc=program.read_pc(owner), read_history=0, bases=bases(base))
        source = actual(prediction)
        source.meta['abtbResult'][0].update(predTaken=prediction.values().get('0.taken', 0), baseTaken=base)
        handle = NS(accepted_event=NS(tick=accepted), completed_event=NS(tick=accepted+4), state=TransferState.COMPLETED)
        rows[accepted+2] = dict(tick=accepted+2, events=Events(select=True, read_pc=program.read_pc(owner), read_context=Context()), read=prediction.frame.read)
        rows[accepted+4] = dict(tick=accepted+4, frame=prediction.frame, actual=source)
        return prediction, handle, source
    def obtain(steps):
        result = []
        for step in steps:
            prediction, handle, source = query(step.owner, step.history, step.base)
            ordinal = checks.owned_source(step, handle, source, monitor)
            sources[step.phase, step.owner] = prediction, source, ordinal
            result.append((handle, source))
        return result
    def advance(event=Events()):
        before = tuple(cache.sequence for cache in model.updates)
        model.advance(event)
        versions = {}
        for table, old in enumerate(before):
            cache = model.updates[table]
            if cache.sequence != old:
                version = cache.recent[-1]
                versions[str(table)] = dict(sequence=version.sequence, next=cache.sequence%8, depth=8,
                    new_cell=dict(valid=1, data_valid=int(version.entry.valid), index=version.index, tag=version.entry.tag,
                        position=version.entry.position, counter=version.entry.counter))
        if versions:
            monitor.records.append(dict(tick=tick(), versions=versions,
                changes=tuple(sorted((table*512+i, old, new) for table, i, old, new, _ in model.effects if old != new)), aged=model.aged))
    def consume(phase, owners):
        for owner in owners:
            _, handle, source = query(owner, 0 if phase == 'final-long' else 64, program.taken(owner))
            checks.consume(phase, owner, handle, source, monitor)
    for group in program.groups:
        phase = group[0].phase
        if phase == 'allocate': obtain(group)
        if phase == 'flip':
            for role in ('late-correct', 'flip'): obtain(tuple(program.step(role, o) for o in program.owners))
        requests = []
        for step in group:
            prediction, source, ordinal = sources[step.phase, step.owner]
            if phase.startswith('late'):
                latest = next(r['versions']['0'] for r in reversed(monitor.records)
                    if r['versions'].get('0', {}).get('new_cell', {}).get('index') == step.indices[0])
                args = step, deepcopy(latest['new_cell']), latest, tick(), monitor.all_protection()
                if stop == (phase, step.owner): return checks, monitor, args
                checks.before_late(*args)
            predicted = step.base if step.before is None else step.before.taken
            transaction = UtageTraining(step.pc, POSITION, step.actual, deepcopy(source.meta), mispredict=int(predicted != step.actual))
            checks.owned_feedback(step, ordinal, transaction)
            requests.append((step, feedback(prediction, taken=bool(step.actual)), transaction))
        before = len(monitor.public)
        for step, request, transaction in requests:
            monitor.public.append(dict(tick=tick()+2, bits=UtageUsefulChecker._payload(transaction)))
            advance(Events(feedback=request))
            if program.mode == 'serial': advance(); advance(); checks.prefix(monitor, step.ordinal+1)
        if program.mode == 'adjacent': advance(); advance(); checks.prefix(monitor, group[-1].ordinal+1)
        checks.cadence(group, monitor.public[before:])
        if phase == 'flip':
            pairs = obtain(tuple(program.step('late-wrong', o) for o in program.owners))
            for owner, (handle, source) in zip(program.owners, pairs, strict=True): checks.consume('flip', owner, handle, source, monitor, existing_source=True)
        elif phase.startswith('late'): consume(phase, tuple(s.owner for s in group))
    consume('final-short', program.owners)
    consume('final-long', program.owners)
    assert model.accepted_feedback == 16 and model.low_tick == model.high_tick == 4
    assert monitor.all_protection() == program.protection_after(16)
    return checks, monitor, None


@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p:p.label)
def test_four_matching_branches_keep_original_correct_agreement_and_wrong_qualification(program):
    checks, monitor, _ = exercise(program)
    checks.finish(monitor)
    assert checks.closed and len(checks.late) == 8 and len(checks.consumers) == 20
    assert len(checks.originals) == 32 and len(checks.feedback.consumed) == 16
    correct = [program.step('late-correct', o) for o in program.owners]
    assert [s.after.useful for s in correct] == [1, 1, 0, 0]
    assert [program.step('late-wrong', o).after.counter for o in program.owners] == [5, 2, 5, 2]
    assert len({r['match_pc'] for r in checks.origins.values()}) == 4


@pytest.mark.parametrize('owner', range(4))
@pytest.mark.parametrize('fault', ('borrow-current-direction', 'wrong-read-identity', 'wrong-tag', 'other-protection'))
def test_late_reward_cannot_borrow_another_real_branch_or_current_direction(owner, fault):
    checks, monitor, args = exercise(PROGRAMS[0], stop=('late-correct', owner))
    step, cell, latest, tick, protection = args
    if fault == 'borrow-current-direction':
        origin = checks.origins['late-correct', owner]
        origin['source'] = replace(origin['source'], taken=step.current.taken)
    elif fault == 'wrong-read-identity': cell['index'] ^= 0x80
    elif fault == 'wrong-tag': cell['tag'] ^= 1
    else:
        protection = list(protection)
        protection[(step.indices[0]+7)%512] = 3
    with pytest.raises(AssertionError): checks.before_late(step, cell, latest, tick, tuple(protection))


@pytest.mark.parametrize('bad_gap', (0, 1, 2))
def test_every_gap_in_a_four_feedback_burst_is_checked(bad_gap):
    program = next(p for p in PROGRAMS if p.mode == 'adjacent')
    checks = Checks(program)
    public = [dict(tick=t) for t in (10, 12, 14, 16)]
    for row in public[bad_gap+1:]: row['tick'] += 2
    with pytest.raises(AssertionError): checks.cadence(program.groups[0], public)


@pytest.mark.parametrize('fault', ('another-matching-PC', 'another-read-index'))
def test_feedback_cannot_borrow_a_different_real_branch(fault):
    checks, _, args = exercise(PROGRAMS[0], stop=('late-correct', 0))
    step = args[0]
    original = checks.origins[step.phase, step.owner]
    request = UtageTraining(step.pc, POSITION, step.actual, deepcopy(original['source'].meta), mispredict=0)
    if fault == 'another-matching-PC': request = replace(request, pc=checks.program.pc(1))
    else: request.meta['readIndex'] = checks.program.read_indices(1)
    with pytest.raises(AssertionError): checks.owned_feedback(step, original['ordinal'], request)


@pytest.mark.parametrize('rule', RULES)
def test_no_checked_credit_until_the_complete_cross_branch_cohort_compares(rule):
    coverage = Coverage(PROGRAMS[0])
    for other in RULES:
        if other != rule: coverage.reach(other, synthetic_control=True)
    with pytest.raises(AssertionError): coverage.finish()
    assert coverage.groups['checked'].coverage == 0
