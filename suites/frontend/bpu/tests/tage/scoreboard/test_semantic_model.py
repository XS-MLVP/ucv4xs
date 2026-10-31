"""Independent history/learning algebra, visibility and negative comparisons."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from toffee import CheckContext, ScoreboardMode

from suites.frontend.bpu.tage.model.semantic import Base, Branch, Context, Entry, Events, Feedback, Frame, Hint, RecentLearning, TageReference, UsefulLearning, UsefulWrite, Write, coordinate, decide, lfsr_next
from suites.frontend.bpu.models.folded_history import folded_history_values, PHR_FOLD_LAYOUT
from suites.frontend.bpu.tage.checker.semantic import TageSemanticChecker
from suites.frontend.bpu.tage.transaction.types import TagePrediction, TageLookup

PC, POSITION = 0x40000000, 6
BASES = (Base(True, POSITION, False, False, 1), Base(), Base(), Base())
POSITIONS = (6, 7, 8, 9)


def lookup(model, pc=PC, history=0, positions=POSITIONS):
    event = Events(pc, Context.from_recent(history), positions, select=True, advance=True)
    model.advance(event)
    model.advance(event)
    return model.frame


def feedback(model, *, actual=True, base=False, mispredict=True, kind=1, matched=True):
    frame = model.frame
    values = decide(frame, (replace(BASES[0], taken=base), *BASES[1:]), model.selectors)
    hint = Hint(bool(values['0.has_provider']), bool(values['0.has_alt']), bool(values['0.use_provider']),
        values.get('0.table', 0), values.get('0.way', 0), values.get('0.counter', 0), values.get('0.useful', 0),
        bool(values['0.alternative']), bool(values['0.alt_conf']))
    return Feedback(frame.read.pc, frame.read.context, (Branch(POSITION, actual, kind,
        mispredict, matched, 2 if base else 1, hint),))


def learn(model, request):
    model.advance(Events(feedback=request))
    for _ in range(7):
        model.advance()


def test_algorithm_has_no_signal_driver_or_old_partial_model_dependency():
    tree = ast.parse(Path('tage/model/semantic.py').read_text())
    assert [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)] == [
        'dataclasses', 'suites.frontend.bpu.models.configuration', 'copy', 'suites.frontend.bpu.models.folded_history']
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))


@pytest.mark.parametrize('history', (0, 1, 63, 64, 511, 512, 65535, (1 << 31) - 1))
def test_history_parity_is_independent_of_driver_chunk_fold(history):
    from suites.frontend.bpu.tage.model.semantic import VISIBLE_HISTORY_INDICES
    context = Context.from_recent(history)
    assert context.folds == tuple(
        row['foldedHist'] if index in VISIBLE_HISTORY_INDICES else 0
        for index, row in enumerate(folded_history_values(history, len(PHR_FOLD_LAYOUT))))


@pytest.mark.parametrize('pc,history,expected', ((PC, 0, (0, 0, 0)), (PC + 3, 0, (3, 0, 0)),
    (PC + 2044, 0, (0, 511, 0)), (PC + 2048, 0, (0, 0, 1)), (PC, 1, (0, 1, 3))))
def test_geometry_and_tag_operand_are_semantic_halfword_coordinates(pc, history, expected):
    assert coordinate(pc, Context.from_recent(history), 0) == expected


def test_random_generator_has_a_full_nonzero_period_and_known_prefix():
    state, seen = 1, set()
    prefix = []
    for _ in range(15):
        prefix.append(state)
        state = lfsr_next(state)
    assert prefix == [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16385]
    state = 1
    for _ in range(32767):
        assert state and state not in seen
        seen.add(state)
        state = lfsr_next(state)
    assert state == 1 and len(seen) == 32767
    assert lfsr_next(1 << 14) == 1


def test_random_advances_while_sram_reset_is_busy_but_reset_restores_seed():
    model = TageReference()
    model.advance(Events(ready=False))
    assert model.random == 2 and model.frame is None
    model.advance(Events(reset=True))
    assert model.random == 1


@pytest.mark.parametrize('direction', (False, True))
def test_allocate_and_learn_saturating_direction_and_usefulness(direction):
    model = TageReference()
    lookup(model)
    learn(model, feedback(model, actual=direction, base=not direction))
    for _ in range(10):
        lookup(model)
        learn(model, feedback(model, actual=direction, base=not direction, mispredict=False))
    frame = lookup(model)
    provider = frame.read.matches(POSITION)[-1]
    assert provider[2] == (7 if direction else 0) and provider[3] == 3


def test_metadata_fallback_selector_and_raw_provider_are_distinct():
    model = TageReference()
    lookup(model)
    learn(model, feedback(model))
    frame = lookup(model)
    values = decide(frame, BASES, model.selectors)
    assert values['0.has_provider'] == 1 and values['0.counter'] == 4
    assert values['0.use_provider'] == values['0.valid'] == 0
    assert values['0.fast_valid'] == values['0.fast_taken'] == values['0.sc_valid'] == 1


@pytest.mark.parametrize('condition', ('direct', 'indirect', 'unmatched', 'disabled'))
def test_unqualified_feedback_has_no_learning(condition):
    model = TageReference()
    lookup(model)
    request = feedback(model, kind=2 if condition == 'direct' else 3 if condition == 'indirect' else 1,
                       matched=condition != 'unmatched')
    model.advance(Events(feedback=request, enabled=condition != 'disabled'))
    for _ in range(8):
        model.advance()
    assert model.memory == model.useful == {} and model.selectors == [16] * 16


def test_snapshot_is_not_changed_by_later_learning_commit():
    model = TageReference()
    source = lookup(model)
    learn(model, feedback(model))
    assert source.read.matches(POSITION) == ()
    assert lookup(model).read.matches(POSITION)


def test_acceptance_learning_entry_retirement_have_different_boundaries():
    model = TageReference()
    lookup(model)
    model.advance(Events(feedback=feedback(model)))
    assert not model.memory
    for _ in range(3):
        model.advance()
        assert not model.memory
    model.advance()
    assert not model.memory and any(cache.pending for cache in model.cache.values())
    model.advance()
    assert model.memory


def test_same_bank_reread_conflict_is_rejected_without_silently_advancing():
    model = TageReference()
    lookup(model)
    with pytest.raises(ValueError, match='conflicts'):
        model.advance(Events(PC, select=True, feedback=feedback(model)))


def test_recent_updates_forward_latest_confidence_and_preserve_owner_across_ports():
    cache = RecentLearning()
    first = Write(1, 1, Entry(True, 17, 4), True)
    cache.advance(True, (first,))
    old = cache.find(1, 17)
    for _ in range(3):
        cache.advance(True, (replace(first, way=0),))
    assert cache.find(1, 17).write.way == 1
    assert cache.find(1, 17).write.entry.counter == 7
    assert old.write.entry.counter == 4
    assert cache.advance(False)[0].entry.counter == 7


def test_superseded_version_cannot_clear_new_same_key_obligation():
    cache = RecentLearning()
    first = Write(1, 0, Entry(True, 17, 4), True)
    cache.advance(True, (first,))
    retired = cache.advance(False, (first,))
    assert retired[0].entry.counter == 4
    assert cache.find(1, 17).sequence in cache.pending
    assert cache.advance(False)[0].entry.counter == 5


def test_useful_fifo_flush_cancels_old_writes_and_preserves_capacity_contract():
    queue = UsefulLearning()
    for row in range(4):
        assert queue.advance(True, UsefulWrite(row, 3)) is None
    queue.advance(True, UsefulWrite(4, 3))
    assert queue.drops == 1
    queue.advance(False, flush=True)
    assert queue.pending == []


def test_aging_clears_usefulness_not_branch_identity_or_counter():
    model = TageReference()
    lookup(model)
    learn(model, feedback(model))
    for _ in range(3):
        lookup(model)
        learn(model, feedback(model, mispredict=False))
    before = deepcopy(model.memory)
    model.tick = 255
    lookup(model)
    learn(model, feedback(model, matched=False, mispredict=False))
    assert model.aging and model.tick == 0
    for _ in range(514):
        model.advance()
    assert not model.aging and not model.clear_cursor
    assert model.memory == before and all(value == 0 for value in model.useful.values())


def actual_prediction(wanted):
    metadata = []
    names = dict(hasProvider='has_provider', hasAlt='has_alt', useProvider='use_provider',
        altOrBasePred='alternative', altConf='alt_conf', providerTableIdx='table', providerWayIdx='way',
        providerTakenCtr_value='counter', providerUsefulCtr_value='useful')
    for slot in range(4):
        metadata.append({field: wanted.get(f'{slot}.{name}', 0) for field, name in names.items()})
    valids = tuple(wanted.get(f'{slot}.valid', 0) for slot in range(4))
    takens = tuple(wanted.get(f'{slot}.taken', 0) for slot in range(4))
    sc = tuple(wanted.get(f'{slot}.sc_valid', 0) for slot in range(4))
    return TagePrediction(valids[0], takens[0], metadata[0], sc[0], valids, takens, tuple(metadata), sc)


@pytest.mark.parametrize('field', ('valid', 'taken', 'has_provider', 'has_alt', 'use_provider',
    'alternative', 'alt_conf', 'table', 'way', 'counter', 'useful', 'fast_valid', 'fast_taken', 'sc_counter'))
def test_wrong_actual_fails_with_owned_state_unchanged(field):
    checker = TageSemanticChecker()
    checker.initialized = True
    lookup(checker.model)
    learn(checker.model, feedback(checker.model))
    for _ in range(3):
        lookup(checker.model)
        learn(checker.model, feedback(checker.model, mispredict=False))
    frame = lookup(checker.model)
    wanted = decide(frame, BASES, checker.model.selectors)
    assert '0.taken' in wanted
    faulty = dict(wanted)
    faulty['0.' + field] ^= 1
    actual = actual_prediction(faulty)
    extras = {name: tuple(faulty.get(f'{slot}.{field_name}', 0) for slot in range(4)) for name, field_name in (
        ('fast_valids', 'fast_valid'), ('fast_takens', 'fast_taken'), ('sc_counters', 'sc_counter'))}
    checker.events, checker.input_tick = Events(), 1
    before = deepcopy(checker.model.state())
    checker.capture_output(SimpleNamespace(tick=2), actual, bases=BASES, enabled=True, extras=extras)
    with pytest.raises(AssertionError):
        checker.raise_failure()
    assert checker.model.state() == before


@pytest.mark.parametrize('wrong', ('pc', 'history', 'position', 'base', 'valid'))
def test_pipeline_context_cannot_be_reassociated_from_actual_payload(wrong):
    checker = TageSemanticChecker()
    frame = lookup(checker.model)
    request = TageLookup(PC, POSITION, 0)
    bases = BASES
    if wrong in ('pc', 'history'):
        request = replace(request, **{wrong: PC + 4 if wrong == 'pc' else 1})
    elif wrong == 'position':
        frame = replace(frame, positions=(7, 8, 9, 10))
    elif wrong == 'base':
        bases = (replace(BASES[0], taken=True), *BASES[1:])
    else:
        bases = (Base(), *BASES[1:])
    wanted = decide(frame, bases, checker.model.selectors)
    checker.expected.append((4, frame, wanted, True, bases))
    context = CheckContext(checker.board.name, ScoreboardMode.ASYNC, request=request,
                           accepted_event=SimpleNamespace(tick=0))
    # This actual is self-consistent with the wrong context. Payload-only
    # checking would accept it; the independent request association must not.
    with pytest.raises(AssertionError):
        checker.response_expected(request, context)(actual_prediction(wanted))
