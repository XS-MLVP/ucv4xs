"""Independent original/current histories and adversarial actual witnesses."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS, FunctionType
import pytest
from toffee import TransferState, ScoreboardMismatch
from suites.frontend.bpu.utage.model.semantic import UtageReference, Events, Context
from suites.frontend.bpu.utage.model.delayed_protection import PROGRAMS, Program, RULES, PC, POSITION, READ_PCS
from suites.frontend.bpu.utage.checker.delayed_protection import Checks
from suites.frontend.bpu.utage.coverage.delayed_protection import Coverage
from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.utage.checker.checking import UtageUsefulChecker
from tests.utage.scoreboard.test_semantic_model import lookup, feedback
from tests.utage.scoreboard.test_read_lifetime_model import bases
from tests.utage.scoreboard.test_selective_protection_controls import actual


def exercise(p, *, stop=None):
    model = UtageReference(); checks = Checks(p); rows = {}; sources = {}
    monitor = NS(records=[], public=[], failure=None, at=rows.__getitem__,
        all_protection=lambda:tuple(table.get(i, 0) for table in model.useful for i in range(512)))
    def tick(): return 100+model.cycles*2
    def query(owner, history, base):
        model.advance(); accepted = tick()
        prediction = lookup(model, PC, history, read_pc=READ_PCS[owner], read_history=0, bases=bases(base))
        public = actual(prediction)
        public.meta['abtbResult'][0].update(predTaken=prediction.values().get('0.taken', 0), baseTaken=base)
        transfer = NS(accepted_event=NS(tick=accepted), completed_event=NS(tick=accepted+4), state=TransferState.COMPLETED)
        rows[accepted+2] = dict(tick=accepted+2, events=Events(select=True, read_pc=READ_PCS[owner], read_context=Context()), read=prediction.frame.read)
        rows[accepted+4] = dict(tick=accepted+4, frame=prediction.frame, actual=public)
        return prediction, transfer, public
    def obtain(steps):
        found = []
        for step in steps:
            prediction, transfer, public = query(step.owner, step.history, step.base)
            ordinal = checks.owned_source(step, transfer, public, monitor)
            sources[step.phase, step.owner] = prediction, public, ordinal
            found.append((transfer, public))
        return found
    def advance(event=Events()):
        before = tuple(cache.sequence for cache in model.updates)
        model.advance(event)
        versions = {}
        for table, old in enumerate(before):
            cache = model.updates[table]
            if cache.sequence != old:
                version = cache.recent[-1]
                versions[str(table)] = dict(sequence=version.sequence, next=cache.sequence%8, depth=8,
                    new_cell=dict(valid=1, data_valid=int(version.entry.valid), index=version.index,
                        tag=version.entry.tag, position=version.entry.position, counter=version.entry.counter))
        if versions:
            monitor.records.append(dict(tick=tick(), versions=versions,
                changes=tuple(sorted((table*512+i, old, new) for table, i, old, new, role in model.effects if old != new)), aged=model.aged))
    def consume(phase, owners):
        history = 0 if phase == 'final-long' else 64
        for owner in owners:
            _, transfer, public = query(owner, history, owner)
            checks.consume(phase, owner, transfer, public, monitor)
    for group in p.groups:
        phase = group[0].phase
        if phase == 'allocate': obtain(group)
        if phase == 'flip' and not any(key[0] == 'flip' for key in sources):
            for role in getattr(p, 'initial_roles', ('late-correct', 'flip')): obtain(tuple(p.step(role, owner) for owner in (0, 1)))
        requests = []
        for step in group:
            prediction, public, ordinal = sources[step.phase, step.owner]
            if phase.startswith('late'):
                latest = next(row['versions']['0'] for row in reversed(monitor.records)
                    if row['versions'].get('0', {}).get('new_cell', {}).get('index') == step.indices[0])
                current = deepcopy(latest['new_cell'])
                args = step, current, latest, tick(), monitor.all_protection()
                if stop == (phase, step.owner): return checks, monitor, args
                checks.before_late(*args)
            transaction = UtageTraining(PC, POSITION, step.actual, deepcopy(public.meta),
                mispredict=int((step.base if step.before is None else step.before.taken) != step.actual))
            checks.owned_feedback(step, ordinal, transaction)
            requests.append((step, feedback(prediction, taken=bool(step.actual)), transaction))
        public_before = len(monitor.public)
        for step, request, transaction in requests:
            monitor.public.append(dict(tick=tick()+2, bits=UtageUsefulChecker._payload(transaction)))
            advance(Events(feedback=request))
            if p.mode == 'serial':
                advance(); advance(); checks.prefix(monitor, step.ordinal+1)
        if p.mode == 'adjacent':
            advance(); advance(); checks.prefix(monitor, group[-1].ordinal+1)
        checks.cadence(group, monitor.public[public_before:])
        owners = tuple(step.owner for step in group)
        if phase == 'flip':
            for role in getattr(p, 'after_flip_roles', ('late-wrong',)):
                pairs = obtain(tuple(p.step(role, owner) for owner in owners))
                if role == 'late-wrong':
                    for owner, (transfer, public) in zip(owners, pairs, strict=True): checks.consume(phase, owner, transfer, public, monitor, existing_source=True)
        elif phase.startswith('late'): consume(phase, owners)
    consume('final-short', (0, 1)); consume('final-long', (0, 1))
    assert model.accepted_feedback == len(p.steps) and model.low_tick == model.high_tick == 2
    assert monitor.all_protection() == p.protection_after(len(p.steps))
    return checks, monitor, None


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.label)
def test_same_independent_reference_checks_original_contribution_and_current_counter(p):
    checks, monitor, _ = exercise(p)
    checks.finish(monitor)
    assert checks.closed and len(checks.late) == 4 and len(checks.consumers) == 10
    assert len(checks.originals) == 16 and len(checks.feedback.consumed) == 8
    for row in checks.late.values(): assert row['original_direction'] != row['current_direction']


@pytest.mark.parametrize('phase', ('late-correct', 'late-wrong'))
@pytest.mark.parametrize('owner', (0, 1))
@pytest.mark.parametrize('fault', ('old-counter-rebase', 'wrong-current-identity', 'current-direction-borrowed',
    'missing-comparison', 'wrong-source-age', 'newer-source', 'other-protection-cell'))
def test_delayed_qualification_requires_original_and_current_to_be_distinct(phase, owner, fault):
    checks, monitor, args = exercise(PROGRAMS[0], stop=(phase, owner))
    step, current, latest, tick, protection = args
    if fault == 'old-counter-rebase': current['counter'] = step.before.counter
    elif fault == 'wrong-current-identity': current['index'] ^= 256
    elif fault == 'current-direction-borrowed':
        entry = checks.origins[phase, owner]
        entry['source'] = replace(entry['source'], taken=step.current.taken)
    elif fault == 'missing-comparison': checks.compared = 0
    elif fault == 'wrong-source-age': checks.origins[phase, owner]['completed'] = tick-1 if phase == 'late-correct' else 0
    elif fault == 'newer-source': checks.origins[phase, owner]['completed'] = tick+2
    else:
        protection = list(protection); protection[2] = 1
    with pytest.raises(AssertionError) as error: checks.before_late(step, current, latest, tick, tuple(protection))
    assert error.value.context.request['point']


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.label)
@pytest.mark.parametrize('fault', ('retroactive-penalty', 'retroactive-agreement', 'old-counter', 'companion-dropped', 'other-cell', 'missing-learning'))
def test_final_equal_values_cannot_excuse_wrong_intermediate_learning(p, fault):
    checks, monitor, _ = exercise(p)
    if fault == 'missing-learning': monitor.records.pop()
    else:
        phase = 'flip' if fault == 'companion-dropped' else 'late-wrong' if fault == 'retroactive-agreement' else 'late-correct'
        step = p.step(phase, 0); row = monitor.records[step.ordinal]
        if fault == 'retroactive-penalty': row['changes'] = ()
        elif fault == 'retroactive-agreement': row['changes'] = ()
        elif fault == 'old-counter': row['versions']['0']['new_cell']['counter'] = step.before.counter+1
        elif fault == 'companion-dropped': row['versions'].pop('1')
        elif fault == 'other-cell': row['changes'] = ((2, 0, 1),)
    checks.compared = 0
    with pytest.raises(AssertionError): checks.prefix(monitor, 8)


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.label)
@pytest.mark.parametrize('missing', ('original', 'delayed-effect', 'consumer', 'immutable', 'cadence'))
def test_every_original_effect_consumer_and_preservation_obligation_is_mandatory(p, missing):
    checks, monitor, _ = exercise(p)
    if missing == 'original': checks.origins.pop(('late-correct', 1))
    elif missing == 'delayed-effect': checks.late['late-correct', 1]['actual_effect_tick'] = None
    elif missing == 'consumer': checks.consumers.pop(('final-long', 1))
    elif missing == 'immutable': checks.originals[0][0].meta['readIndex'] = (1, 1)
    else: checks.cadences.pop()
    with pytest.raises(AssertionError): checks.finish(monitor)


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.label)
@pytest.mark.parametrize('missing', RULES)
def test_checked_credit_is_atomic_for_the_full_semantic_cohort(p, missing):
    coverage = Coverage(p)
    for rule in RULES:
        if rule != missing: coverage.reach(rule)
    with pytest.raises(AssertionError): coverage.finish()
    assert coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('p', PROGRAMS, ids=lambda p:p.label)
def test_complete_cohort_has_only_its_own_semantic_bins_once(p):
    coverage = Coverage(p)
    for rule in RULES: coverage.reach(rule)
    coverage.finish()
    assert coverage.groups['checked'].coverage == 25
    with pytest.raises(AssertionError): coverage.finish()
    for name, value in vars(Checks).items():
        if isinstance(value, FunctionType): assert name not in vars(Checks(p))


def test_program_is_not_a_physical_matrix_and_case_has_no_clock_io_plumbing():
    with pytest.raises(ValueError): Program('bank0', 'interleaved')
    with pytest.raises(ValueError): Program('serial', 'slot7')
    for name in ('tests/utage/testcase/test_delayed_protection.py', 'utage/case/delayed_protection.py'):
        text = Path(name).read_text()
        assert not any(s in text for s in ('asyncio', 'ClockCycles', 'FallingEdge', 'RisingEdge', 'get_', 'set_'))
    tree = ast.parse(Path('utage/model/delayed_protection.py').read_text())
    assert not any(isinstance(n, ast.Import) for n in ast.walk(tree))
