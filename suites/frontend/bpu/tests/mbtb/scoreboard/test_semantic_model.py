"""Independent MainBTB branch programs, not prepared actual snapshots."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from toffee import CheckContext, ScoreboardMode

from suites.frontend.bpu.mbtb.checker.semantic import MbtbSemanticChecker, prediction_values
from suites.frontend.bpu.mbtb.coverage.semantic import SemanticCoverage
from suites.frontend.bpu.mbtb.model.semantic import Branch, CounterPatch, DirectionWrites, Entry, Events, Feedback, MbtbReference, RetainedEntries, Source, Target, Write, coordinate, tag, window
from suites.frontend.bpu.mbtb.transaction.types import MbtbEntry, MbtbLookup, MbtbPrediction

PC = 0x40000000


def lookup(model, pc=PC):
    event = Events(pc, select=True, advance=True, consume=True)
    model.advance(event)
    model.advance(event)
    return model.frame


def feedback(frame, *, position=3, kind=1, action=0, target=PC + 0x234, taken=True, mispredict=True):
    sources = tuple(tuple(Source(entry.valid and entry.tag == tag(read.pc),
        read.ordinal * 16 + entry.position, entry.kind, entry.action, counter)
        for entry, counter in zip(read.entries, read.counters, strict=True)) + (Source(),) for read in frame.banks)
    return Feedback((frame.pc, (frame.pc // 16 + 1) * 16), sources,
                    (Branch(target, taken, position, kind, action, mispredict),))


def learn(model, request):
    model.advance(Events(feedback=request))
    for _ in range(9):
        model.advance()


def test_algorithm_has_no_native_or_old_prepared_snapshot_dependency():
    tree = ast.parse(Path('mbtb/model/semantic.py').read_text())
    assert {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} == {
        'dataclasses','suites.frontend.bpu.models.configuration','suites.frontend.bpu.mbtb.model.victim'}
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))


@pytest.mark.parametrize('pc,expected', ((PC, (0, 0, 0)), (PC + 16, (1, 0, 0)),
    (PC + 32, (0, 1, 0)), (PC + 128, (0, 0, 1)), (PC + 32640, (0, 0, 255))))
def test_halfword_geometry_has_distinct_alignment_bank_and_row_dimensions(pc, expected):
    assert coordinate(pc) == expected
    assert tag(pc) == 32768


@pytest.mark.parametrize('pc', (PC, PC + 3, PC + 8, PC + 11, PC + 15))
def test_window_is_contiguous_and_preserves_only_first_block_offset(pc):
    physical = window(pc)
    assert sorted(physical, key=lambda value: value[1]) == [(pc, 0), ((pc // 16 + 1) * 16, 1)]
    assert all(coordinate(address)[0] == align for align, (address, _) in enumerate(physical))


@pytest.mark.parametrize('position,kind,action', ((3, 1, 0), (5, 2, 0), (9, 3, 0), (2, 3, 1), (11, 3, 3)))
def test_allocate_complete_branch_record_and_counter(position, kind, action):
    model = MbtbReference()
    learn(model, feedback(lookup(model), position=position, kind=kind, action=action))
    values = lookup(model).values()
    active = (position // 16) * 5 + 3
    assert values[f'{active}.valid'] == 1
    assert values[f'{active}.target'] == PC + 0x234
    assert values[f'{active}.position'] == position
    assert values[f'{active}.kind'] == kind and values[f'{active}.action'] == action
    assert values[f'{active}.counter'] == 2
    assert sum(values[f'{slot}.valid'] for slot in range(10)) == 1


def test_no_mispredict_can_learn_direction_but_cannot_allocate_entry():
    model = MbtbReference()
    learn(model, feedback(lookup(model), mispredict=False))
    assert not model.memory
    learn(model, feedback(lookup(model)))
    learn(model, feedback(lookup(model), mispredict=False))
    assert lookup(model).values()['3.counter'] == 3


@pytest.mark.parametrize('taken', (False, True))
def test_owned_direction_endpoints_saturate(taken):
    model = MbtbReference()
    learn(model, feedback(lookup(model)))
    for _ in range(8):
        learn(model, feedback(lookup(model), taken=taken))
    assert lookup(model).values()['3.counter'] == (3 if taken else 0)


@pytest.mark.parametrize('delta', (-1, 0, 1))
def test_target_carry_is_an_adjacent_region_semantic_feature(delta):
    pc = 0x40000000 + (1 << 20) + 24
    target = (pc // (1 << 20) + delta) * (1 << 20) + 64
    assert Target.encode(pc, target).region_delta == delta
    assert Target.encode(pc, target).at(pc) == target


def test_batch_resolves_two_conditional_positions_independently():
    model = MbtbReference()
    learn(model, feedback(lookup(model), position=1))
    learn(model, feedback(lookup(model), position=5))
    source = feedback(lookup(model))
    batch = replace(source, branches=(Branch(PC + 0x100, False, 1, 1), Branch(PC + 0x200, True, 5, 1)))
    learn(model, batch)
    frame = lookup(model)
    actual = {read.ordinal * 16 + entry.position: counter for read in frame.banks
              for entry, counter in zip(read.entries, read.counters) if entry.valid}
    assert actual == {1: 1, 5: 3}


@pytest.mark.parametrize('kind,action,changed', ((1, 0, False), (2, 0, False), (3, 0, True), (3, 1, False), (3, 2, True), (3, 3, False)))
def test_only_ittage_base_indirects_retarget_without_attribute_change(kind, action, changed):
    model = MbtbReference()
    learn(model, feedback(lookup(model), kind=kind, action=action))
    learn(model, feedback(lookup(model), kind=kind, action=action, target=PC + 0x456))
    assert lookup(model).values()['3.target'] == PC + (0x456 if changed else 0x234)


def test_attribute_correction_replaces_record_and_resets_its_confidence():
    model = MbtbReference()
    learn(model, feedback(lookup(model)))
    learn(model, feedback(lookup(model), mispredict=False))
    assert lookup(model).values()['3.counter'] == 3
    learn(model, feedback(lookup(model), kind=3, action=2, target=PC + 0x456))
    values = lookup(model).values()
    assert (values['3.kind'], values['3.action'], values['3.counter'], values['3.target']) == (3, 2, 2, PC + 0x456)


def test_offset_and_page_filter_preserve_raw_hit_metadata():
    model = MbtbReference()
    learn(model, feedback(lookup(model), position=1))
    late = lookup(model, PC + 2).values()
    assert late['3.valid'] == 0 and late['3.raw_hit'] == 1 and late['3.meta_position'] == 1
    pc = 0x40000ff0
    model = MbtbReference()
    learn(model, feedback(lookup(model, pc), position=17, kind=2))
    filtered = lookup(model, pc).values()
    assert filtered['3.valid'] == 0 and filtered['3.raw_hit'] == 1 and filtered['3.meta_position'] == 17
    visible = lookup(model, pc + 16).values()
    assert visible['3.valid'] == 1 and visible['3.position'] == 1


def test_read_snapshot_cannot_be_rewritten_by_later_target_learning():
    model = MbtbReference()
    learn(model, feedback(lookup(model), kind=3))
    source = lookup(model)
    learn(model, feedback(source, kind=3, target=PC + 0x456))
    assert source.values()['3.target'] == PC + 0x234
    assert lookup(model).values()['3.target'] == PC + 0x456


def test_same_bank_pressure_separates_acceptance_from_visibility():
    model = MbtbReference()
    source = lookup(model)
    model.advance(Events(PC, select=True, advance=True, feedback=feedback(source)))
    for _ in range(8):
        model.advance(Events(PC, select=True, advance=True))
    assert not model.memory and not model.counters
    assert len(model.entries[0, 0].outstanding) == 1
    assert len(model.directions[0, 0].pending) == 1
    model.advance()
    assert not model.memory and model.counters[0,0,0,3] == 2
    # A miss retains the old SRAM payload before its replacement commits.
    model.advance()
    assert not model.memory
    model.advance()
    assert model.memory[0, 0, 0, 3].valid and model.counters[0, 0, 0, 3] == 2


def test_lru_is_touched_by_training_not_prediction():
    model = MbtbReference()
    pcs = tuple(PC + index*(1<<15) for index in range(5))
    for pc,way in zip(pcs,(3,2,1,0)):
        learn(model,feedback(lookup(model,pc),target=pc+0x234))
        assert lookup(model,pc).values()[f'{way}.valid'] == 1
    before = deepcopy(model.recency)
    for pc in reversed(pcs[:4]):lookup(model,pc)
    assert model.recency == before
    learn(model, feedback(lookup(model), mispredict=False))
    learn(model, feedback(lookup(model,pcs[4]),target=pcs[4]+0x234))
    assert lookup(model).values()['3.valid'] == 1
    assert lookup(model,pcs[4]).values()['2.valid'] == 1
    evicted = lookup(model,pcs[1]).values()
    assert evicted['2.valid'] == 0 and evicted['4.valid'] == 1
    assert evicted['4.target'] == pcs[1]+0x234


def test_coalescing_resets_retained_owner_not_nominated_peer():
    model = MbtbReference()
    cold = feedback(lookup(model), kind=3)
    learn(model, cold)
    # Model-only state, never a sampled DUT counter.
    model.counters[0, 0, 0, 0] = 0
    learn(model, replace(cold, branches=(replace(cold.branches[0], target=PC + 0x456),)))
    assert model.counters[0, 0, 0, 0] == 0
    assert model.counters[0, 0, 0, 3] == 2
    assert lookup(model).values()['3.target'] == PC + 0x456


def test_unmatched_same_position_feedback_cannot_train_another_tag():
    model = MbtbReference()
    learn(model, feedback(lookup(model)))
    before = deepcopy(model.counters)
    miss = feedback(lookup(model, PC + (1 << 15)), taken=False, mispredict=False)
    assert not any(source.hit for row in miss.sources for source in row)
    learn(model, miss)
    assert model.counters == before
    assert lookup(model).values()['3.counter'] == 2


def test_nonconditional_source_cannot_learn_conditional_direction_without_correction():
    model = MbtbReference()
    learn(model, feedback(lookup(model), kind=2))
    learn(model, feedback(lookup(model), kind=1, taken=False, mispredict=False))
    assert lookup(model).values()['3.counter'] == 2


def test_reset_cancels_learning_writes_and_response_snapshots():
    model = MbtbReference()
    model.advance(Events(feedback=feedback(lookup(model))))
    model.advance(Events(reset=True))
    for _ in range(9):
        model.advance()
    assert model.memory == model.counters == model.recency == {}
    assert model.frame is model.offered is None


def test_disable_holds_registered_prediction_and_gates_metadata():
    model = MbtbReference()
    learn(model, feedback(lookup(model)))
    frame = lookup(model)
    model.advance(Events(enabled=False))
    assert model.frame is frame
    assert model.frame.values(False)['3.valid'] == 1 and model.frame.values(False)['3.raw_hit'] == 0


def test_direction_fifo_flows_buffers_and_admits_full_retire_enqueue_atomically():
    writes = DirectionWrites()
    words = tuple(CounterPatch(index,(2,None,None,None)) for index in range(7))
    assert writes.advance(False, words[0]) == words[0]
    for word in words[:4]:assert writes.advance(True,word) is None
    assert writes.pending == list(words[:4]) and writes.drops == 0
    assert writes.advance(False,words[4]) == words[0]
    assert writes.pending == list(words[1:5]) and writes.drops == 0
    writes.advance(True,words[5])
    assert writes.drops == 1 and writes.pending == list(words[1:5])
    assert [writes.advance(False) for _ in range(4)] == list(words[1:5])
    assert not writes.pending


def test_retained_owner_is_logical_identity_and_old_version_is_immutable():
    cache = RetainedEntries()
    first = Write(0, 1, Entry(1, 3, 3, 0, Target(100)))
    cache.advance(True, (first,))
    old = next(iter(cache.records.values()))
    second = replace(first, way=0, entry=replace(first.entry, target=Target(200)))
    assert cache.owner(second) == 1
    cache.advance(True, (second,))
    assert old.write == first
    assert cache.advance(False) == (replace(second, way=1),)


def test_explicit_clear_cannot_alias_valid_tag_zero_position_zero_owner():
    cache = RetainedEntries()
    first = Write(0, 0, Entry(0, 0, 2, 0, Target(100)))
    cache.advance(True, (first,))
    cache.advance(True, (Write(0, 1, None),))
    assert cache.advance(False) == (first, Write(0, 1, None))


def actual_prediction(frame, enabled=True):
    values = frame.values(enabled)
    entries, sources = [], []
    for align in range(2):
        row = []
        for way in range(5):
            slot = align * 5 + way
            get = lambda key, default=0: values.get(f'{slot}.{key}', default)
            entries.append(MbtbEntry(get('valid'),get('taken'),get('target'),get('position'),get('kind'),get('action')))
            row.append(dict(rawHit=get('raw_hit'),position=get('meta_position'),
                attribute=dict(branchType=get('meta_kind'),rasAction=get('meta_action')),counter_value=get('counter')))
        sources.append(row)
    return MbtbPrediction(tuple(entries), sources)


@pytest.mark.parametrize('field', ('valid', 'taken', 'target', 'position', 'branch_type', 'ras_action',
                                  'rawHit', 'counter_value', 'meta_position', 'meta_kind', 'meta_action'))
def test_wrong_actual_field_fails_without_resynchronization(field):
    checker = MbtbSemanticChecker()
    checker.initialized = True
    learn(checker.model, feedback(lookup(checker.model)))
    actual = actual_prediction(lookup(checker.model))
    if field in ('valid', 'taken', 'target', 'position', 'branch_type', 'ras_action'):
        entry = actual.entries[3]
        actual = replace(actual, entries=(*actual.entries[:3], replace(entry, **{field: getattr(entry, field) ^ 1}),
                                         *actual.entries[4:]))
    elif field == 'meta_position':
        actual.meta_entries[0][3]['position'] ^= 1
    elif field in ('meta_kind', 'meta_action'):
        key = 'branchType' if field == 'meta_kind' else 'rasAction'
        actual.meta_entries[0][3]['attribute'][key] ^= 1
    else:
        actual.meta_entries[0][3][field] ^= 1
    checker.events, checker.input_tick = Events(), 1
    before = deepcopy(checker.model.state())
    checker.capture_output(SimpleNamespace(tick=2), actual, enabled=True)
    with pytest.raises(AssertionError):
        checker.raise_failure()
    assert checker.model.state() == before


def test_wrong_accepted_pc_is_rejected_even_when_payload_would_be_a_miss():
    checker = MbtbSemanticChecker()
    frame = lookup(checker.model)
    checker.expected.append((6, frame, frame.values(), True))
    checker.events = Events()
    compare = checker.response_expected(MbtbLookup(PC + 16), CheckContext(checker.board.name,
        ScoreboardMode.ASYNC, accepted_event=SimpleNamespace(tick=2)))
    with pytest.raises(AssertionError):
        compare(actual_prediction(frame))


@pytest.mark.parametrize('invalid', (lambda: Events(select=1), lambda: Events(pc=1 << 49),
    lambda: Events(feedback=SimpleNamespace(as_int=lambda: 0)), lambda: Source(hit=1),
    lambda: Source(counter=4), lambda: Source(position=32), lambda: Branch(0, 1, 0, 1),
    lambda: Feedback((PC, PC + 16), ((Source(),) * 2,) * 2, ())))
def test_signal_like_or_out_of_contract_semantic_inputs_are_rejected(invalid):
    with pytest.raises(ValueError):
        invalid()


@pytest.mark.parametrize('family,rule', (('miss', 'unmatched-same-position-isolation'),
                                      ('owner', 'stale-metadata-retained-owner')))
def test_public_offer_cannot_create_checked_semantic_credit(tmp_path, family, rule):
    coverage = SemanticCoverage(family)
    coverage.record('reached', rule, accepted_tick=10)
    assert coverage.groups['reached'].coverage == 50
    assert coverage.groups['checked'].coverage == 0
    coverage.write(tmp_path)


def test_duplicate_preparation_without_public_consume_has_no_accepted_cleanup():
    checker = MbtbSemanticChecker()
    checker.initialized = True
    frame = lookup(checker.model)
    first = frame.banks[0]
    duplicates = (Entry(tag(PC), 3, 3), Entry(tag(PC), 3, 3), Entry(), Entry())
    checker.model.frame = replace(frame, banks=(replace(first, entries=duplicates), frame.banks[1]))
    checker.capture_input(SimpleNamespace(tick=1), Events())
    assert not checker.accepted_cleanup
    checker.capture_input(SimpleNamespace(tick=3), Events(consume=True))
    assert list(checker.accepted_cleanup) == [dict(tick=3, align=0, bank=0, row=0, way=1, tag=32768, position=3)]
