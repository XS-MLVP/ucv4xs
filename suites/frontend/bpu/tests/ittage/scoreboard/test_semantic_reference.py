"""Semantic entries, snapshots and pending updates, without a native DUT."""
from dataclasses import replace
from itertools import product
from types import SimpleNamespace

import pytest
from toffee import ScoreboardMismatch

from bpuverify.ittage.checker.semantic import IttageSemanticChecker
from bpuverify.ittage.model.semantic import (
    Context, Entry, Events, IttageReference, Metadata, Outcome, Patch, SETS,
    Target, WriteCache, coordinates,
)
from bpuverify.ittage.transaction.types import IttagePrediction
from bpuverify.ittage.coverage.semantic import TargetLearningCoverage


PC, A, B = 0x40000800, 0x40002000, 0x40006000


def learn(model, metadata, target, *, pc=PC, history=0, mispredict=True):
    feedback = Outcome(pc, Context.from_recent(history), metadata, target, mispredict=mispredict)
    model.advance(Events(feedback=feedback))
    for _ in range(3):
        model.advance(Events())


def install(model, table, *, pc=PC, history=0, target=A, confidence=2, useful=0):
    bank, index, tag = coordinates(pc, Context.from_recent(history), table)
    ref = Target(target % (1 << 20))
    if pc >> 20 != target >> 20:
        ref = Target(target % (1 << 20), model.regions.allocate(target).pointer)
    model.memories[table][bank][index] = Entry(True, tag, confidence, useful, ref)


def actual_value(prediction, *, choice=None):
    if choice is None and prediction.candidates:
        choice = prediction.candidates[0]
    return IttagePrediction(int(prediction.provider is not None), prediction.target, dict(
        valid=1, provider=dict(valid=int(prediction.provider is not None), bits=prediction.provider or 0),
        altProvider=dict(valid=int(prediction.alternate is not None), bits=prediction.alternate or 0),
        providerCnt_value=prediction.confidence, providerUsefulCnt_value=prediction.useful,
        providerTarget_addr=prediction.provider_target,
        altProviderCnt_value=prediction.alternate_confidence,
        altProviderTarget_addr=prediction.alternate_target,
        altDiffers=int(prediction.alternate is not None and prediction.provider_target != prediction.alternate_target),
        allocate=dict(valid=int(bool(prediction.candidates)), bits=choice or 0)))


@pytest.mark.parametrize('pc,history', tuple(product((PC, PC + 2, PC + 4, PC + 0x200), (0, 4, 0x100, 0x1FFFF))))
def test_hash_uses_semantic_byte_geometry_and_independent_fold_parity(pc, history):
    context = Context.from_recent(history)
    for table, sets in enumerate(SETS):
        bank, index, tag = coordinates(pc, context, table)
        idx_fold, primary, secondary = context.folds[table]
        assert bank == (pc >> 1) & 1
        assert index == ((pc >> 2) & (sets - 1)) ^ idx_fold
        assert tag == ((pc // (4 * sets)) ^ primary ^ (2 * secondary)) & 127
    assert Context.from_recent(4).folds == ((4, 4, 4),) * 3


def test_feedback_acceptance_is_not_memory_visibility():
    model = IttageReference()
    feedback = Outcome(PC, Context(), Metadata(allocation=0), A, mispredict=True)
    model.advance(Events(feedback=feedback))
    assert model.inspect(PC).provider is None
    model.advance(Events())  # Learning rule evaluated, not enqueued yet.
    assert model.inspect(PC).provider is None and model.normal
    model.advance(Events())  # Pending entry, not yet committed.
    assert model.inspect(PC).provider is None and model.commits == 0
    model.advance(Events())
    actual = model.inspect(PC)
    assert (actual.provider, actual.confidence, actual.target) == (0, 2, A)


def test_same_bank_reads_defer_commit_but_other_bank_access_releases_it():
    model = IttageReference()
    feedback = Outcome(PC, Context(), Metadata(allocation=0), A, mispredict=True)
    model.advance(Events(pc=PC, feedback=feedback))
    for _ in range(8):
        model.advance(Events(access=True, select=True))
        assert model.inspect(PC).provider is None
    model.advance(Events(pc=PC + 2, access=True, select=True))
    assert model.inspect(PC).provider is None
    model.advance(Events(access=True, select=True))
    assert model.inspect(PC).target == A
    # The preceding read still describes the old memory, not the new commit.
    assert model.prediction.provider is None


def test_read_snapshot_survives_later_entry_commit():
    model = IttageReference()
    learn(model, Metadata(allocation=0), A)
    model.advance(Events(pc=PC))
    model.advance(Events(access=True))
    before = model.read
    bank, index, tag = coordinates(PC, Context(), 0)
    model.memories[0][bank][index] = Entry(True, tag, 0, 1, Target(B % (1 << 20)))
    model.advance(Events(select=True))
    assert model.read is None and model.prediction.target == A
    assert before.entries[0].confidence == 2


def test_request_relaunch_does_not_reuse_preceding_read_token():
    model = IttageReference()
    learn(model, Metadata(allocation=0), A)
    model.advance(Events(pc=PC))
    model.advance(Events(access=True))
    model.advance(Events(select=True))
    assert model.prediction.target == A
    model.advance(Events())  # Table-valid pipeline bubble, not a held read token.
    model.advance(Events(pc=PC, access=True, select=True))
    assert model.prediction is None
    model.advance(Events(access=True, select=True))
    assert model.prediction.target == A


@pytest.mark.parametrize('tables', [(), (0,), (1,), (2,), (0, 1), (0, 2), (1, 2), (0, 1, 2)])
def test_provider_alternate_and_legal_allocation_are_independent_of_actual_choice(tables):
    model = IttageReference()
    for table in tables:
        install(model, table, target=A + table * 0x100)
    prediction = model.inspect(PC)
    assert prediction.provider == (max(tables) if tables else None)
    assert prediction.alternate == (sorted(tables)[-2] if len(tables) > 1 else None)
    assert prediction.candidates == tuple(table for table in range(3)
        if table not in tables and (not tables or table > max(tables)))


def test_tag_miss_cannot_allocate_over_a_useful_resident():
    model = IttageReference()
    install(model, 0, useful=1)
    alias = PC + 4 * SETS[0]
    assert coordinates(PC, Context(), 0)[1] == coordinates(alias, Context(), 0)[1]
    assert model.inspect(alias).provider is None
    assert model.inspect(alias).candidates == (1, 2)


@pytest.mark.parametrize('counter,correct', tuple(product(range(4), (False, True))))
def test_confidence_learning_uses_accepted_source_snapshot(counter, correct):
    model = IttageReference()
    install(model, 2, confidence=3)  # Current memory differs from source.
    metadata = Metadata(provider=2, confidence=counter, provider_target=A)
    learn(model, metadata, A if correct else B, mispredict=not correct)
    after = model.inspect(PC)
    assert after.confidence == (min(3, counter + 1) if correct else max(0, counter - 1))
    assert after.target == (B if not correct and counter == 0 else A)


@pytest.mark.parametrize('useful,differs,correct', tuple(product(range(2), (False, True), (False, True))))
def test_provider_usefulness_is_not_reconstructed_from_actual_counter(useful, differs, correct):
    model = IttageReference()
    install(model, 2, confidence=2, useful=1 - useful)
    learn(model, Metadata(provider=2, confidence=2, useful=useful,
                          provider_target=A, differs=differs), A if correct else B)
    assert model.inspect(PC).useful == (int(correct) if differs else useful)


def test_zero_confidence_selects_alternate_and_penalty_preserves_its_useful():
    model = IttageReference()
    install(model, 0, target=A, confidence=2, useful=1)
    install(model, 2, target=B, confidence=0)
    assert model.inspect(PC).target == A
    learn(model, Metadata(provider=2, confidence=0, provider_target=B,
                          alternate=0, alternate_confidence=2, alternate_target=A, differs=True),
          A + 0x100)
    bank, index, _ = coordinates(PC, Context(), 0)
    alternate = model.memories[0][bank][index]
    assert (alternate.confidence, alternate.useful) == (1, 1)
    assert model.inspect(PC).provider_target == A + 0x100


def test_correct_unconfident_provider_suppresses_allocation_and_tick_not_alternate_penalty():
    model = IttageReference()
    install(model, 0, target=A)
    install(model, 1, target=B, confidence=0)
    learn(model, Metadata(provider=1, confidence=0, provider_target=B,
        alternate=0, alternate_confidence=2, alternate_target=A, differs=True, allocation=2), B)
    assert model.tick == 0 and model.inspect(PC).provider == 1
    assert model.inspect(PC).confidence == 1 and model.inspect(PC).useful == 1


def test_zero_confidence_cross_region_learning_preserves_real_target():
    model = IttageReference()
    install(model, 2, target=A, confidence=0)
    target = 0x41000400
    learn(model, Metadata(provider=2, confidence=0, provider_target=A), target)
    assert model.inspect(PC).provider_target == target
    assert model.inspect(PC).provider_target != (PC & ~((1 << 20) - 1)) | (target & ((1 << 20) - 1))


def test_retained_metadata_target_can_use_an_existing_region_binding():
    model = IttageReference()
    pointer = model.regions.allocate(A).pointer
    install(model, 2, target=A, confidence=2)
    learn(model, Metadata(provider=2, confidence=2, provider_target=A), A, mispredict=False)
    bank, index, _ = coordinates(PC, Context(), 2)
    assert model.memories[2][bank][index].target.pointer == pointer
    assert model.inspect(PC).provider_target == A


def test_useful_clear_composes_with_pending_target_write_not_erase_it():
    cache = WriteCache()
    target_patch = Patch(True, 7, 2, 1, Target(A % (1 << 20)))
    assert cache.advance(read_busy=True, incoming=(3, target_patch)) is None
    assert cache.advance(read_busy=True, incoming=(3, Patch(useful=0))) is None
    drain = cache.advance(read_busy=False)
    result = drain.patch.apply(Entry())
    assert (result.valid, result.tag, result.confidence, result.useful, result.target) == (
        True, 7, 2, 0, Target(A % (1 << 20)))


def test_same_cycle_drain_keeps_old_payload_and_new_feedback_pending():
    cache = WriteCache()
    cache.advance(read_busy=True, incoming=(3, Patch(confidence=2)))
    drain = cache.advance(read_busy=False, incoming=(3, Patch(confidence=3)))
    assert drain.patch.confidence == 2
    assert cache.slots[0].dirty and cache.slots[0].patch.confidence == 3
    assert cache.advance(read_busy=False).patch.confidence == 3


def test_reset_cancels_learning_and_all_pending_memory_effects():
    model = IttageReference()
    model.advance(Events(feedback=Outcome(PC, Context(), Metadata(allocation=0), A, mispredict=True)))
    model.advance(Events())
    model.advance(Events())
    model.advance(Events(reset=True))
    for _ in range(5):
        model.advance(Events())
    assert model.commits == 0 and model.inspect(PC).provider is None


@pytest.mark.parametrize('condition', ['invalid', 'untaken', 'non-indirect', 'return', 'disabled'])
def test_unqualified_feedback_cannot_learn(condition):
    model = IttageReference()
    changes = {'invalid': dict(valid=False), 'untaken': dict(taken=False),
               'non-indirect': dict(indirect=False), 'return': dict(returns=True)}
    feedback = Outcome(PC, Context(), Metadata(allocation=0), A, mispredict=True,
                       **changes.get(condition, {}))
    model.advance(Events(feedback=feedback, enabled=condition != 'disabled'))
    for _ in range(4):
        model.advance(Events())
    assert model.inspect(PC).provider is None and model.tick == 0


def test_global_tick_saturates_then_clears_all_useful_without_losing_entries():
    model = IttageReference()
    install(model, 2, confidence=2, useful=1)
    feedback = Outcome(PC, Context(), Metadata(provider=2, confidence=2, useful=1,
                       provider_target=A), B, mispredict=True)
    for _ in range(255):
        model.advance(Events(feedback=feedback))
    model.advance(Events())
    assert model.tick == 255
    model.advance(Events())
    assert model.tick == 0
    # Exact scope-bound completion limit: longest table sweep, its start
    # bridge and the last cached write. Not a wait inserted into a DUT case.
    for _ in range(max(SETS) + 4):
        model.advance(Events())
    assert all(not busy for busy, _ in model.maintenance)
    prediction = model.inspect(PC)
    assert (prediction.provider, prediction.provider_target, prediction.confidence, prediction.useful) == (2, A, 1, 0)


@pytest.mark.parametrize('field', ['target', 'providerCnt_value', 'providerUsefulCnt_value',
                                  'providerTarget_addr', 'allocate', 'provider', 'altProvider', 'altDiffers'])
def test_wrong_output_or_illegal_random_choice_fails_without_state_reseeding(field):
    checker = IttageSemanticChecker()
    install(checker.model, 0)
    checker.initialized = True
    checker.events = Events()
    checker.input_tick = 0
    checker.model.prediction = checker.model.inspect(PC)
    good = actual_value(checker.model.prediction)
    if field == 'target':
        bad = replace(good, target=B)
    elif field == 'allocate':
        bad = replace(good, meta={**good.meta, 'allocate': dict(valid=1, bits=0)})
    elif field in ('provider', 'altProvider'):
        value = dict(good.meta[field])
        value['valid'] ^= 1
        bad = replace(good, meta={**good.meta, field: value})
    else:
        bad = replace(good, meta={**good.meta, field: good.meta[field] ^ 1})
    before = checker.model.state()
    checker.capture_output(SimpleNamespace(tick=1), bad, visible=True)
    with pytest.raises(ScoreboardMismatch):
        checker.raise_failure()
    assert checker.model.state() == before
    checker.raise_unobserved_failure()


@pytest.mark.parametrize('choice', [1, 2])
def test_random_proposals_are_checked_against_legal_set_not_sampled_as_golden(choice):
    checker = IttageSemanticChecker()
    install(checker.model, 0)
    checker.initialized, checker.input_tick, checker.events = True, 0, Events()
    checker.model.prediction = checker.model.inspect(PC)
    checker.capture_output(SimpleNamespace(tick=1), actual_value(checker.model.prediction, choice=choice), visible=True)
    checker.raise_failure()


@pytest.mark.parametrize('wrong', [True, False])
def test_retarget_credit_requires_committed_full_target_consumer(wrong):
    coverage = TargetLearningCoverage()
    checker = IttageSemanticChecker(coverage=coverage)
    checker.initialized = True
    install(checker.model, 2, confidence=0)
    target = 0x41001400
    feedback = Outcome(PC, Context(), Metadata(provider=2, confidence=0, provider_target=A), target, mispredict=True)
    checker.capture_input(SimpleNamespace(tick=0), Events(feedback=feedback))
    assert coverage.groups['reached'].report()['points'][0]['counts']['zero-confidence-new-region-retarget'] == 1
    assert coverage.groups['checked'].coverage == 0
    checker.capture_output(SimpleNamespace(tick=1), IttagePrediction(0, 0, {'valid': 0}), visible=False)
    for tick in (2, 4, 6):
        checker.capture_input(SimpleNamespace(tick=tick), Events())
        checker.capture_output(SimpleNamespace(tick=tick + 1), IttagePrediction(0, 0, {'valid': 0}), visible=False)
    checker.model.prediction = checker.model.inspect(PC)
    checker.input_tick = 8
    actual = actual_value(checker.model.prediction)
    if wrong:
        actual = replace(actual, target=0x40001400,
                         meta={**actual.meta, 'providerTarget_addr': 0x40001400})
    checker.capture_output(SimpleNamespace(tick=9), actual, visible=True)
    if wrong:
        with pytest.raises(ScoreboardMismatch):
            checker.raise_failure()
    else:
        checker.raise_failure()
    checked = coverage.groups['checked'].report()['points'][0]['counts']
    assert checked['zero-confidence-new-region-retarget'] == int(not wrong)


def test_reset_cannot_check_a_target_obligation_from_the_previous_epoch():
    coverage = TargetLearningCoverage()
    model = IttageReference()
    target = 0x41001400
    event = Events(feedback=Outcome(PC, Context(), Metadata(provider=2, confidence=0,
                   provider_target=A), target, mispredict=True))
    coverage.accept(event, model, 0)
    assert len(coverage.pending) == 1
    model.advance(Events(reset=True))
    coverage.accept(Events(reset=True), model, 2)
    install(model, 2, target=target)  # A different epoch's unrelated allocation.
    coverage.consume(model.inspect(PC), 9)
    assert not coverage.pending and coverage.groups['checked'].coverage == 0


@pytest.mark.parametrize('invalid', [lambda: Events(context=0), lambda: Events(reset=1),
                                  lambda: Events(feedback=1),
                                  lambda: Outcome(PC, Context(), Metadata(), A, taken=1)])
def test_signal_like_values_are_not_silently_accepted_as_semantic_events(invalid):
    with pytest.raises(TypeError):
        invalid()


@pytest.mark.parametrize('invalid', [lambda: Context.from_recent(-1), lambda: Context.from_recent(1 << 31),
                                  lambda: coordinates(PC + 1, Context(), 0),
                                  lambda: Metadata(provider=3), lambda: Metadata(confidence=4)])
def test_out_of_contract_inputs_raise(invalid):
    with pytest.raises(ValueError):
        invalid()
