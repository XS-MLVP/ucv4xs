"""Independent branch programs and negative output comparisons, without DUT."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from toffee import CheckContext, ScoreboardMode

from bpuverify.abtb.checker.semantic import AbtbSemanticChecker, prediction_values
from bpuverify.abtb.coverage.semantic import SemanticCoverage
from bpuverify.abtb.model.semantic import AbtbReference, Entry, Events, Feedback, PendingWrites, Recency, Source, Write, coordinate
from bpuverify.abtb.transaction.types import AbtbEntry, AbtbLookup, AbtbPrediction


PC = 0x40000800


def lookup(model, pc=PC, history=0):
    event = Events(read_pc=pc, history=history, select=True, match_pc=pc, consume=True, remember=True)
    model.advance(event)
    model.advance(event)
    return model.frame


def feedback(frame, *, position=3, kind=1, action=0, target=PC + 0x234, taken=True):
    return Feedback(frame.pc, target, taken, position, kind, action, frame.valid,
        frame.read.row, 1 << frame.read.bank, tuple(Source(hit, entry.position, entry.kind,
        entry.action, entry.target) for hit, entry in zip(frame.hits, frame.read.entries, strict=True)))


def learn(model, request):
    model.advance(Events(feedback=request))
    for _ in range(4):
        model.advance()


def test_algorithm_has_no_signal_or_old_implementation_audit_dependency():
    tree = ast.parse(Path('bpuverify/abtb/model/semantic.py').read_text())
    assert [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)] == ['bpuverify.common.model.configuration', 'dataclasses']
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))


@pytest.mark.parametrize('halfword,history,expected', ((PC, 0, (0, 0)), (PC, 15, (3, 3)),
    (PC + 127, 1, (3, 63)), (PC + 512, 0, (0, 0))))
def test_geometry_from_halfword_address_and_history(halfword, history, expected):
    assert coordinate(halfword, history) == expected


@pytest.mark.parametrize('kind,action', ((1, 0), (2, 0), (2, 2), (3, 1), (3, 3)))
def test_taken_branch_allocates_complete_attributes_and_local_target(kind, action):
    model = AbtbReference()
    learn(model, feedback(lookup(model), kind=kind, action=action))
    frame = lookup(model)
    assert frame.hits == (True, False, False, False)
    assert frame.counters == (2, 0, 0, 0)
    assert frame.read.entries[0] == Entry(True, PC % (1 << 24), 3, kind, action, (PC + 0x234) % (1 << 22))


def test_not_taken_miss_has_no_entry_or_replacement_effect():
    model = AbtbReference()
    learn(model, feedback(lookup(model), taken=False))
    assert not any(lookup(model).hits)
    assert model.memory == model.recency == {}


def test_four_positions_have_independent_direction_learning():
    model = AbtbReference()
    for position in (1, 4, 8, 12):
        learn(model, feedback(lookup(model), position=position))
    frame = lookup(model)
    by_position = {entry.position: way for way, entry in enumerate(frame.read.entries)}
    assert set(by_position) == {1, 4, 8, 12}
    learn(model, feedback(frame, position=8))
    frame = lookup(model)
    assert {entry.position: counter for entry, counter in zip(frame.read.entries, frame.counters)} == {
        1: 0, 4: 0, 8: 2, 12: 2}
    learn(model, feedback(frame, taken=False))
    frame = lookup(model)
    assert {entry.position: counter for entry, counter in zip(frame.read.entries, frame.counters)} == {
        1: 0, 4: 0, 8: 1, 12: 1}


@pytest.mark.parametrize('direction', (False, True))
def test_direction_is_owned_and_saturates_at_both_endpoints(direction):
    model = AbtbReference()
    learn(model, feedback(lookup(model)))
    for _ in range(8):
        learn(model, feedback(lookup(model), taken=direction))
    frame = lookup(model)
    assert frame.counters[0] == (3 if direction else 0)
    assert frame.values()['0.strong'] == 1


def test_only_indirect_targets_are_corrected_in_place():
    for kind in (1, 2, 3):
        model = AbtbReference()
        learn(model, feedback(lookup(model), kind=kind))
        source = lookup(model)
        learn(model, feedback(source, kind=kind, target=PC + 0x444))
        frame = lookup(model)
        assert frame.read.entries[0].target == (PC + (0x444 if kind == 3 else 0x234)) % (1 << 22)
        assert frame.hits == (True, False, False, False)


@pytest.mark.parametrize('pc,target,expected', ((0x407fffe0, 0x407fff00, 0x407fff00),
    (0x407fffe0, 0x40800100, 0x40400100), (0x40800000, 0x407fff00, 0x40bfff00)))
def test_target_is_reconstructed_in_pc_region_without_carry_fix(pc, target, expected):
    model = AbtbReference()
    learn(model, feedback(lookup(model, pc), kind=3, target=target))
    assert lookup(model, pc).values()['0.target'] == expected


def test_taken_feedback_not_prediction_touches_recency():
    model = AbtbReference()
    for offset in range(4):
        pc = PC + offset * 512
        learn(model, feedback(lookup(model, pc), target=PC + 0x100 * offset))
    original = deepcopy(model.recency)
    for _ in range(4):
        lookup(model)
    assert model.recency == original
    learn(model, feedback(lookup(model), target=PC))
    assert model.recency != original
    learn(model, feedback(lookup(model, PC + 4 * 512)))
    assert any(lookup(model).hits), 'feedback-touched oldest entry must be retained'


def test_recency_tree_matches_list_partition_spec_for_every_touch_pair():
    # Independent oracle: each touched partition makes its other member older.
    for first in range(4):
        for second in range(4):
            tree = Recency().touch(first).touch(second)
            older_half = 1 - second // 2
            last_in_half = next((way for way in (second, first) if way // 2 == older_half), None)
            older_member = 0 if last_in_half is None else 1 - last_in_half % 2
            assert tree.victim == 2 * older_half + older_member


def test_inflight_read_is_immutable_across_feedback_commit():
    model = AbtbReference()
    learn(model, feedback(lookup(model), kind=3))
    source = lookup(model)
    learn(model, feedback(source, kind=3, target=PC + 0x999))
    assert source.read.entries[0].target == (PC + 0x234) % (1 << 22)
    assert lookup(model).read.entries[0].target == (PC + 0x999) % (1 << 22)


def test_write_is_not_visible_until_read_pressure_ends():
    model = AbtbReference()
    source = lookup(model)
    model.advance(Events(read_pc=PC, select=True, feedback=feedback(source)))
    for _ in range(8):
        model.advance(Events(read_pc=PC, select=True, match_pc=PC, consume=True))
    assert model.memory == {}
    assert len(model.pending[0].outstanding) == 1
    model.advance()
    assert model.entries(0, 0)[0].valid


def test_destination_ownership_keeps_same_tag_different_positions_obligated():
    pending = PendingWrites()
    for way in range(4):
        pending.advance(True, Write(7, way, Entry(True, 99, way, 3, 0, way * 16), False))
    assert len(pending.outstanding) == 4
    retired = [pending.advance(False) for _ in range(4)]
    assert [(write.way, write.entry.position) for write in retired] == [(way, way) for way in range(4)]


def test_superseding_a_destination_keeps_latest_obligation_and_read_version():
    pending = PendingWrites()
    first = Write(7, 1, Entry(True, 99, 3, 3, 0, 100), False)
    second = replace(first, entry=replace(first.entry, target=200))
    pending.advance(True, first)
    version = next(iter(pending.versions.values()))
    pending.advance(True, second)
    assert version.write == first
    assert pending.advance(False) == second
    assert pending.advance(False) is None


def test_disable_and_reset_cancel_response_ownership_but_only_reset_clears_memory():
    model = AbtbReference()
    learn(model, feedback(lookup(model)))
    model.advance(Events(enabled=False))
    assert model.values()['meta_valid'] == 0
    assert model.memory
    model.advance(Events(read_pc=PC, select=True, match_pc=PC))
    assert model.values()['meta_valid'] == 0
    model.advance(Events(reset=True))
    assert model.memory == {} and model.offered is None


def actual_prediction(frame):
    values = frame.values()
    entries, meta_entries, micro = [], [], []
    for way, (entry, hit, counter) in enumerate(zip(frame.read.entries, frame.hits, frame.counters, strict=True)):
        attribute = dict(branchType=entry.kind, rasAction=entry.action)
        entries.append(AbtbEntry(int(frame.valid and hit), int(counter >= 2),
            values.get(f'{way}.target', 0), entry.position, entry.kind, entry.action))
        meta_entries.append(dict(hit=int(hit), attribute=dict(attribute), position=entry.position,
                                 targetLowerBits=entry.target))
        micro.append(dict(valid=int(frame.valid and hit), bits=dict(taken=int(counter >= 2),
            cfiPosition=entry.position, attribute=dict(attribute), isStrongBias=int(counter in (0, 3)))))
    return AbtbPrediction(tuple(entries), dict(valid=int(frame.valid), setIdx=frame.read.row,
        bankMask=1 << frame.read.bank, entries=meta_entries), dict(result=micro, fastPositions=(0,) * 4))


@pytest.mark.parametrize('field', ('taken', 'target', 'position', 'branch_type', 'ras_action',
                                  'hit', 'row', 'banks', 'strong', 'micro_taken', 'meta_position'))
def test_wrong_actual_field_raises_without_resynchronizing(field):
    checker = AbtbSemanticChecker()
    checker.initialized = True
    learn(checker.model, feedback(lookup(checker.model)))
    actual = actual_prediction(lookup(checker.model))
    if field in ('taken', 'target', 'position', 'branch_type', 'ras_action'):
        entry = actual.entries[0]
        actual = replace(actual, entries=(replace(entry, **{field: getattr(entry, field) ^ 1}), *actual.entries[1:]))
    elif field == 'hit':
        actual.meta['entries'][0]['hit'] = 0
    elif field == 'row':
        actual.meta['setIdx'] ^= 1
    elif field == 'banks':
        actual.meta['bankMask'] ^= 1
    elif field == 'meta_position':
        actual.meta['entries'][0]['position'] ^= 1
    else:
        key = 'isStrongBias' if field == 'strong' else 'taken'
        actual.micro_tage['result'][0]['bits'][key] ^= 1
    checker.events, checker.input_tick = Events(), 1
    before = deepcopy(checker.model.state())
    checker.capture_output(SimpleNamespace(tick=2), actual, enabled=True)
    with pytest.raises(AssertionError):
        checker.raise_failure()
    assert checker.model.state() == before


def test_miss_does_not_compare_undefined_entry_payloads():
    model = AbtbReference()
    frame = lookup(model)
    actual = actual_prediction(frame)
    actual = replace(actual, entries=tuple(replace(entry, target=99, position=15) for entry in actual.entries))
    expected, observed = prediction_values(model.values(), actual)
    assert expected == observed


@pytest.mark.parametrize('invalid', (lambda: Events(select=1), lambda: Events(history=32),
    lambda: Events(feedback=SimpleNamespace(as_int=lambda: 0)), lambda: Source(hit=1),
    lambda: Source(position=32), lambda: Source(kind=4),
    lambda: Source(target=1 << 22), lambda: coordinate(1 << 49)))
def test_signal_like_and_out_of_contract_inputs_are_rejected(invalid):
    with pytest.raises(ValueError):
        invalid()


def test_genuine_upstream_invalid_metadata_cannot_learn():
    model = AbtbReference()
    source = lookup(model)
    learn(model, replace(feedback(source), valid=False))
    assert model.memory == {} and model.counters == {}


def test_accepted_response_checks_history_coordinate_even_when_pc_matches():
    checker = AbtbSemanticChecker()
    frame = lookup(checker.model)
    checker.expected.append((6, frame, frame.values(), True))
    context = CheckContext(checker.board.name, ScoreboardMode.ASYNC,
                           accepted_event=SimpleNamespace(tick=2))
    compare = checker.response_expected(AbtbLookup(PC, path_hash=1), context)
    with pytest.raises(AssertionError):
        compare(actual_prediction(frame))


def test_semantic_offer_does_not_imply_successful_endpoint_credit(tmp_path):
    coverage = SemanticCoverage()
    coverage.record('reached', 'distinct-destinations-retained', offered_ticks=(10, 14))
    assert coverage.groups['reached'].coverage == 50
    assert coverage.groups['checked'].coverage == 0
    coverage.write(tmp_path)
