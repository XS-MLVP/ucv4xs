"""Independent table algorithms, temporal ownership and negative comparisons."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from bpuverify.utage.model.semantic import Base, Context, Entry, Events, Feedback, RecentUpdates, Source, UtageReference, indices, tag
from bpuverify.utage.agent.main import UtageAgent
from bpuverify.utage.coverage.semantic import SemanticCoverage
from bpuverify.utage.checker.semantic import UtageSemanticChecker, prediction_values
from bpuverify.utage.transaction.types import UtagePrediction


PC = 0x40000000
BASES = (Base(True, 5, False, 1), Base(), Base(), Base())
POSITIONS = (5, 6, 7, 8)


def lookup(model, pc=PC, history=0, *, read_pc=None, read_history=None, bases=BASES):
    event = Events(pc if read_pc is None else read_pc,
        Context.from_recent(history if read_history is None else read_history), True,
        pc, Context.from_recent(history), POSITIONS, bases, advance=True)
    model.advance(event)
    model.advance(event)
    return model.prediction


def feedback(prediction, *, taken=True, kind=1):
    frame = prediction.frame
    providers = frame.providers()
    sources = tuple(Source(base.valid and base.kind == 1, frame.positions[slot], provider is not None,
        provider or 0, frame.read.entries[provider].counter if provider is not None else 0,
        bool(provider is not None and frame.read.entries[provider].counter >= 4), base.taken)
        for slot, (base, provider) in enumerate(zip(prediction.bases, providers, strict=True)))
    return Feedback(frame.pc, frame.context, frame.read.indices, sources, 5, taken, kind)


def learn(model, request):
    model.advance(Events(feedback=request))
    model.advance()
    model.advance()


def test_algorithm_has_no_native_driver_or_framework_dependency():
    tree = ast.parse(Path('bpuverify/utage/model/semantic.py').read_text())
    assert [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)] == [
        'dataclasses', 'bpuverify.common.model.configuration', 'bpuverify.common.model.folded_history']
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))


@pytest.mark.parametrize('history', (0, 1, 63, 64, 255, 511, 4095, (1 << 31) - 1))
def test_history_features_use_bit_parity_not_driver_chunk_algorithm(history):
    context = Context.from_recent(history)
    low, high = history & 31, history & 511
    assert indices(PC, context) == (low, high)
    assert context.folds[0] == history & 15


@pytest.mark.parametrize('pc,expected', ((PC, (0, 0)), (PC | 2, (32, 0)), (PC | 8, (128, 0)), (PC | 1024, (16, 32)), (PC | 16384, (0, 128))))
def test_tag_preserves_configured_eight_bit_address_features(pc, expected):
    assert tuple(tag(pc, Context(), table) for table in range(2)) == expected


@pytest.mark.parametrize('direction', (False, True))
def test_allocation_then_same_context_learning_saturates_direction(direction):
    model = UtageReference()
    bases = (replace(BASES[0], taken=not direction), *BASES[1:])
    cold = lookup(model, bases=bases)
    learn(model, feedback(cold, taken=direction))
    for _ in range(8):
        prediction = lookup(model, bases=bases)
        learn(model, feedback(prediction, taken=direction))
    final = lookup(model, bases=bases)
    assert final.frame.providers()[0] == 0
    assert final.frame.read.entries[0].counter == (7 if direction else 0)
    assert model.useful[0][0] == 3


def test_longest_history_provider_and_allocation_excludes_lower_depths():
    model = UtageReference()
    cold = lookup(model)
    learn(model, feedback(cold))
    short = lookup(model)
    learn(model, feedback(short, taken=False))
    both = lookup(model)
    assert both.frame.providers()[0] == 1
    assert both.frame.read.entries[0].counter == 3
    assert both.frame.read.entries[1].counter == 3
    assert model.useful[1][0] == 2


@pytest.mark.parametrize('kind', (2, 3))
def test_resolved_nonconditional_at_same_position_has_no_direction_learning(kind):
    model = UtageReference()
    learn(model, feedback(lookup(model)))
    before = deepcopy(model.useful)
    source = lookup(model)
    learn(model, feedback(source, taken=False, kind=kind))
    assert lookup(model).frame.read.entries[0].counter == 4
    assert model.useful == before


def test_later_jump_proves_earlier_taken_conditional_was_not_taken():
    model = UtageReference()
    bases = (replace(BASES[0], taken=True), *BASES[1:])
    source = lookup(model, bases=bases)
    outcome = replace(feedback(source, taken=True, kind=3), position=7)
    learn(model, outcome)
    result = lookup(model, bases=bases)
    assert result.frame.providers()[0] == 0
    assert result.frame.read.entries[0].counter == 3


def test_index_and_tag_ancestors_are_independent_and_maximum_index_is_not_truncated():
    model = UtageReference()
    source = lookup(model, read_pc=PC + 511, read_history=0)
    assert source.frame.read.indices == (511, 511)
    assert source.frame.pc == PC
    learn(model, feedback(source))
    result = lookup(model, read_pc=PC + 511, read_history=0)
    assert result.frame.providers()[0] == 0
    assert result.frame.read.entries[0].tag == 0


def test_query_snapshot_is_immutable_when_write_overwrites_retained_slot():
    cache = RecentUpdates()
    for index in range(8):
        cache.advance((index + 1) % 4, (index, Entry(True, index, 5, 3)))
    old = cache.newest(0)
    cache.advance(1, (8, Entry(True, 8, 5, 4)))
    assert old.entry == Entry(True, 0, 5, 3)
    assert cache.newest(0) is None
    assert cache.newest(8).entry.counter == 4


def test_superseded_write_cannot_clear_new_same_key_obligation():
    cache = RecentUpdates()
    for count in range(12):
        cache.advance(0, (0, Entry(True, 0, 5, min(7, count))))
    assert cache.newest(0).entry.counter == 7
    assert cache.newest(0).sequence in cache.dirty
    retired = []
    for _ in range(10):
        write = cache.advance(1)
        if write is not None:
            retired.append(write.entry.counter)
    assert retired == [7]


def test_bank_pressure_protects_dirty_versions_before_cache_eviction():
    cache = RecentUpdates()
    writes = []
    for number in range(20):
        retiring = cache.advance(0, (number * 4, Entry(True, number, 5, 4)))
        if retiring is not None:
            writes.append(retiring.index)
    assert writes and writes == sorted(writes)
    assert len(cache.outstanding) <= 8


def test_reset_cancels_offered_learning_and_recent_updates():
    model = UtageReference()
    source = lookup(model)
    model.advance(Events(feedback=feedback(source)))
    model.advance(Events(reset=True))
    for _ in range(4):
        model.advance()
    assert model.memory == [{}, {}] and model.useful == [{}, {}]
    assert model.updates[0].recent == []


def actual_prediction(prediction):
    frame = prediction.frame
    providers = frame.providers()
    hits = tuple(int(provider is not None) for provider in providers)
    takens = tuple(int(provider is not None and frame.read.entries[provider].counter >= 4) for provider in providers)
    meta = dict(readIndex=frame.read.indices, foldedPathHistForTrain_hist=tuple(
        dict(foldedHist=value) for value in frame.context.folds), abtbResult=tuple(dict(
        valid=int(base.valid and base.kind == 1), baseTaken=int(base.taken), baseIsStrongBias=int(base.strong),
        hit=int(base.valid and provider is not None), predTaken=takens[slot], cfiPosition=frame.positions[slot],
        tableId=provider or 0, takenCtr_value=frame.read.entries[provider].counter if provider is not None else 0)
        for slot, (base, provider) in enumerate(zip(prediction.bases, providers, strict=True))))
    return UtagePrediction(hits[0], takens[0], meta, hits, takens)


def test_miss_payload_is_not_an_oracle_for_undefined_priority_mux_bits():
    model = UtageReference()
    prediction = lookup(model)
    actual = actual_prediction(prediction)
    actual = replace(actual, takens=(1,) * 4)
    for slot in actual.meta['abtbResult']:
        slot['predTaken'], slot['tableId'], slot['takenCtr_value'] = 1, 1, 7
    expected, observed = prediction_values(prediction, actual, 0)
    assert expected == observed


@pytest.mark.parametrize('field', ('hit', 'taken', 'counter', 'provider', 'indices', 'history', 'useful', 'low'))
def test_faulted_actual_rejected_without_seeding_or_resynchronization(field):
    checker = UtageSemanticChecker()
    checker.initialized = True
    learn(checker.model, feedback(lookup(checker.model)))
    prediction = lookup(checker.model)
    actual = actual_prediction(prediction)
    if field == 'hit':
        actual = replace(actual, hits=(0,) * 4)
    elif field == 'taken':
        actual = replace(actual, takens=(0,) * 4)
    elif field in ('counter', 'provider'):
        key = 'takenCtr_value' if field == 'counter' else 'tableId'
        actual.meta['abtbResult'][0][key] ^= 1
    elif field == 'indices':
        actual.meta['readIndex'] = (1, 0)
    elif field == 'history':
        actual.meta['foldedPathHistForTrain_hist'] = (dict(foldedHist=1),) * 19
    checker.events, checker.input_tick = Events(), 1
    before = deepcopy(checker.model.state())
    useful = {(0, 0): 0 if field == 'useful' else checker.model.useful[0][0]}
    counters = dict(low=1 if field == 'low' else checker.model.low_tick)
    checker.capture_output(SimpleNamespace(tick=2), actual, 1, counters=counters, useful=useful)
    with pytest.raises(AssertionError):
        checker.raise_failure()
    assert checker.model.state() == before


def test_empty_upstream_beats_do_not_define_raw_correction_payloads():
    model = UtageReference()
    learn(model, feedback(lookup(model)))
    prediction = lookup(model, bases=(Base(),) * 4)
    actual = actual_prediction(prediction)
    actual = replace(actual, hits=(0,) * 4, takens=(1,) * 4)
    expected, observed = prediction_values(prediction, actual, 0)
    assert expected == observed


def test_short_and_long_age_policies_transform_a_common_old_protection_state():
    model = UtageReference()
    model.useful = [{0: 3, 511: 1}, {0: 3, 511: 1}]
    model.low_tick, model.high_tick = 128, 128
    model.advance()
    assert model.useful == [{0: 2, 511: 0}, {0: 1, 511: 0}]
    assert model.low_tick == 0 and model.high_tick == 128
    assert model.aged


def test_allocation_failure_uses_owned_usefulness_not_a_dut_counter():
    model = UtageReference()
    model.useful = [{0: 3}, {0: 3}]
    cold = lookup(model)
    for _ in range(128):
        learn(model, feedback(cold))
    # The pulse matures on the clock following the threshold; the source
    # counter is not a DUT observation used to schedule this event.
    model.advance()
    assert model.low_tick == 0 and model.high_tick == 128
    assert model.useful == [{0: 2}, {0: 1}]


def test_s3_override_uses_pre_boundary_older_snapshot_not_newly_advanced_frame():
    model = UtageReference()
    first = lookup(model)
    learn(model, feedback(first))
    old = lookup(model)
    different = lookup(model, history=4)
    source = model.older
    model.advance(Events(select=True, advance=True, override='s3', override_pc=PC,
                         override_context=source.context, positions=POSITIONS, bases=BASES))
    assert model.frame.read == source.read
    assert model.frame.read != different.frame.read


def test_full_tag_entry_survives_eviction_from_recent_versions_without_truncation():
    model = UtageReference()
    pc = PC | 8
    learn(model, feedback(lookup(model, pc)))
    entry = model.updates[0].newest(8).entry
    assert entry.tag == 128
    # Model-only retirement and eight different keys replace retained versions.
    for index in range(16, 25):
        write = model.updates[0].advance(index % 4, (index, Entry(True, index, 5, 4)))
        if write is not None:
            model.memory[0][write.index] = write.entry
    assert model.updates[0].newest(8) is None
    assert model.memory[0][8].tag == 128


def test_learning_hold_indices_are_still_obligations_for_actual_comparison():
    model = UtageReference()
    cold = lookup(model)
    learn(model, feedback(cold))
    source = lookup(model, bases=(replace(BASES[0], taken=True), *BASES[1:]))
    learn(model, feedback(source))
    assert model.effects == ()
    assert model.checked_indices == ((0, 0), (1, 0))


def test_checked_credit_is_separate_from_public_offer_credit(tmp_path):
    coverage = SemanticCoverage('resolved-type')
    coverage.record('reached', 'resolved-direct-same-position', offered_tick=10)
    assert coverage.groups['reached'].coverage == 50
    assert coverage.groups['checked'].coverage == 0
    coverage.write(tmp_path)


def test_boundary_coverage_preserves_full_physical_denominators():
    coverage = SemanticCoverage('boundary')
    for group, denominator in ((coverage.physical_allocation, 2048),
                               (coverage.physical_update, 8192)):
        cross, = group.report()['crosses']
        assert cross['name'] == 'all_dimensions'
        assert len([item for item in cross['bins'] if item['kind'] == 'normal']) == denominator
    assert coverage.physical_allocation.coverage == coverage.physical_update.coverage == 0


async def test_result_task_cleanup_retrieves_all_duplicates_without_second_failure():
    import asyncio
    failure = AssertionError('already delivered semantic mismatch')
    async def fail():
        raise failure
    tasks = {asyncio.create_task(fail()) for _ in range(3)}
    await asyncio.sleep(0)
    fake = SimpleNamespace(_result_tasks=tasks,
                           reference=SimpleNamespace(failure=failure, failure_observed=True))
    await UtageAgent._drain_result_tasks(fake)
    assert not tasks


async def test_result_task_cleanup_does_not_hide_an_unrelated_failure():
    import asyncio
    async def fail():
        raise ValueError('unrelated task error')
    tasks = {asyncio.create_task(fail()) for _ in range(2)}
    await asyncio.sleep(0)
    fake = SimpleNamespace(_result_tasks=tasks,
                           reference=SimpleNamespace(failure=AssertionError('first'), failure_observed=True))
    with pytest.raises(ValueError, match='unrelated'):
        await UtageAgent._drain_result_tasks(fake)
    assert not tasks
