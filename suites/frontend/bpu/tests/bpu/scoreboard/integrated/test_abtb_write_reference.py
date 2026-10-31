from copy import deepcopy
from itertools import product
import pytest

from suites.frontend.bpu.abtb.model.state.counter import CounterReference
from suites.frontend.bpu.abtb.model.state.counter import touch
from suites.frontend.bpu.abtb.model.state.counter import victim
from suites.frontend.bpu.abtb.model.state.writebuffer import FIELDS
from suites.frontend.bpu.abtb.model.state.writebuffer import zero
from suites.frontend.bpu.bpu.model.abtb.write import WriteLineageReference
from suites.frontend.bpu.bpu.model.abtb.write import cleanup_request
from suites.frontend.bpu.bpu.model.abtb.write import training_requests


def transaction(bank=0, entry_set=0, *, kind=1, taken=1, way=None, target=0x40010407):
    entries = [dict(hit=0, position=0, attribute=dict(branchType=0, rasAction=0), targetLowerBits=0)
        for _ in range(4)]
    if way is not None:
        entries[way].update(hit=1, position=7, attribute=dict(branchType=kind, rasAction=0),
            targetLowerBits=target & ((1 << 22) - 1))
    return dict(pc=0x40010003, target=target, taken=taken, position=7, branch_type=kind,
        ras_action=0, meta=dict(valid=1, setIdx=entry_set, bankMask=1 << bank, entries=entries))


def advance(model, accepted=None, *, pressure=(0, 0, 0, 0), cleanup=None):
    return model.advance(reset=0, accepted=accepted, read_pressure=pressure, new_cleanup=cleanup)


def ready_model():
    model = WriteLineageReference()
    model.advance(reset=1, accepted=None, read_pressure=[0] * 4)
    for _ in range(64):
        advance(model)
    return model


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('entry_set', range(64))
def test_all_bank_set_allocations_traverse_T1_T2_buffer_and_SRAM_without_actual_response(bank, entry_set):
    model, tx = ready_model(), transaction(bank, entry_set)
    assert advance(model, tx)['writes'] == []
    assert advance(model)['actions'] == []
    buffered = advance(model)
    assert len(buffered['actions']) == 1 and buffered['roles'][bank] == 'allocate'
    assert buffered['writes'] == []
    drained = advance(model)
    assert drained['writes'] == [dict(bank=bank, set_index=entry_set, way=0, reset_counter=1)]
    assert model.sram[bank][entry_set][0] == buffered['requests'][bank]
    assert model.counter.cells[bank * 256 + entry_set * 4] == 2


@pytest.mark.parametrize('kind,taken,way,changed', tuple(product(range(4), range(2), range(4), range(2))))
def test_all_warm_hits_only_indirect_kind3_can_correct_target_even_when_not_taken(kind, taken, way, changed):
    tx = transaction(kind=kind, taken=taken, way=way)
    tx['target'] ^= changed
    requests, roles = training_requests(tx, CounterReference())
    needed = kind == 3 and changed == 1
    assert bool(requests[0]) == needed
    if needed:
        assert requests[0]['need_reset'] == 0 and requests[0]['way'] == way
        assert roles[0] == 'correct_target'
    assert requests[1:] == [None] * 3


@pytest.mark.parametrize('state', range(8))
def test_victim_is_T1_prestate_not_current_T2_PLRU(state):
    model = ready_model()
    model.counter.plru[0][0] = state  # pure contract fixture, never DUT state
    advance(model, transaction())
    advance(model)
    captured = model.request2[0]['way']
    assert captured == victim(state)
    model.counter.plru[0][0] = touch(state, captured)
    assert model.counter.plru[0][0] != state
    result = advance(model)
    assert result['requests'][0]['way'] == captured


@pytest.mark.parametrize('mask', range(16))
def test_multihit_cleanup_uses_last_matching_pair_not_first_hit(mask):
    meta = transaction()['meta']
    for way, entry in enumerate(meta['entries']):
        entry.update(hit=(mask >> way) & 1, position=5)
    pairs = [(a, b) for a in range(4) for b in range(a + 1, 4) if mask & (1 << a) and mask & (1 << b)]
    expected = None if not pairs else dict(set_index=0, bank_mask=1, way=pairs[-1][0])
    assert cleanup_request(meta, fire=1) == expected
    assert cleanup_request(meta, fire=0) is None


@pytest.mark.parametrize('field', ('position', 'attribute', 'target'))
def test_nonmatching_entry_cannot_hide_a_taken_allocation(field):
    tx = transaction(way=2)
    if field == 'position':
        tx['meta']['entries'][2]['position'] ^= 1
    elif field == 'attribute':
        tx['meta']['entries'][2]['attribute']['rasAction'] = 1
    else:
        # Direct/conditional target differences are NOT matching criteria.
        tx['target'] ^= 1
    requests, _ = training_requests(tx, CounterReference())
    assert bool(requests[0]) == (field != 'target')


def test_multiple_matching_indirect_entries_correct_the_lowest_way_only():
    tx = transaction(kind=3, way=1)
    tx['meta']['entries'][3] = deepcopy(tx['meta']['entries'][1])
    tx['meta']['entries'][1]['targetLowerBits'] ^= 1
    requests, _ = training_requests(tx, CounterReference())
    assert requests[0]['way'] == 1
    tx['meta']['entries'][1]['targetLowerBits'] ^= 1
    tx['meta']['entries'][3]['targetLowerBits'] ^= 1
    assert training_requests(tx, CounterReference())[0] == [None] * 4


def test_only_low22_target_bits_trigger_indirect_target_correction():
    tx = transaction(kind=3, way=0)
    tx['target'] ^= 1 << 30
    assert training_requests(tx, CounterReference())[0] == [None] * 4


def test_SRAM_ready_comes_from_exact64_cycle_reset_walker_not_observed_drain_ready():
    model = WriteLineageReference()
    with pytest.raises(ValueError, match='actual reset'):
        advance(model)
    model.advance(reset=1, accepted=None, read_pressure=[0] * 4)
    assert all(cell is None for bank in model.sram for row in bank for cell in row)
    for row in range(64):
        result = advance(model)
        assert result['ready'] == [False] * 4 and result['sram_reset_row'] == row
        assert all(cell == zero() for bank in model.sram for cell in bank[row])
        if row < 63:
            assert model.sram[0][row + 1][0] is None
    assert advance(model)['ready'] == [True] * 4


def test_reset_discards_inflight_training_and_cleanup_and_clears_shadow():
    model = ready_model()
    advance(model, transaction(), cleanup=dict(set_index=2, bank_mask=4, way=3))
    advance(model)
    model.advance(reset=1, accepted=None, read_pressure=[0] * 4)
    assert model.counter.pending1 is model.counter.pending2 is model.cleanup is None
    assert model.request2 == [None] * 4
    assert not any(slot['shadow_valid'] or slot['dirty'] for buffer in model.buffers for slot in buffer.slots)


@pytest.mark.parametrize('bank', range(4))
def test_cleanup_is_deferred_by_training_on_same_bank_and_new_cleanup_wins_old_applied(bank):
    model = ready_model()
    old = dict(set_index=5, bank_mask=1 << bank, way=3)
    new = dict(set_index=6, bank_mask=1 << bank, way=2)
    advance(model, transaction(bank, 7))
    advance(model, cleanup=old)
    normal = advance(model)
    assert normal['roles'][bank] == 'allocate' and model.cleanup == old
    clean = advance(model, cleanup=new)
    assert clean['roles'][bank] == 'clean_multi_hit' and model.cleanup == new
    payload = clean['requests'][bank]
    assert payload == dict(zero(), need_reset=1, set_index=5, way=3)
    advance(model)
    assert model.cleanup is None


@pytest.mark.parametrize('bank', range(4))
def test_prediction_reads_block_only_selected_bank_and_dirty_write_drains_after_release(bank):
    model = ready_model()
    pressure = [int(index == bank) for index in range(4)]
    advance(model, transaction(bank), pressure=pressure)
    advance(model, pressure=pressure)
    advance(model, pressure=pressure)
    held = advance(model, pressure=pressure)
    assert held['writes'] == [] and model.buffers[bank].slots[0]['dirty']
    assert held['ready'] == [index != bank for index in range(4)]
    assert advance(model)['writes'] == [dict(bank=bank, set_index=0, way=0, reset_counter=1)]


@pytest.mark.parametrize('bank', range(4))
def test_real_pipeline_full_dirty_overwrite_does_not_invent_a_queue_or_backpressure(bank):
    model = ready_model()
    for entry_set in range(5):
        advance(model, transaction(bank, entry_set), pressure=[1] * 4)
    actions = advance(model, pressure=[1] * 4)['actions']
    actions += advance(model, pressure=[1] * 4)['actions']
    assert actions[-1]['role'] == 'full_overwrite'
    lost = actions[-1]['old']['payload']['set_index']
    drains = [drain for _ in range(5) for drain in advance(model)['drains']]
    assert len(drains) == 4 and lost not in [row['payload']['set_index'] for row in drains]
    assert model.sram[bank][lost] == [zero() for _ in range(4)]


def test_same_cycle_drain_and_dirty_hit_uses_old_payload_then_retains_new_dirty_payload():
    model = ready_model()
    old, new = transaction(kind=3), transaction(kind=3)
    new['target'] ^= 1
    advance(model, old, pressure=[1] * 4)
    advance(model, new, pressure=[1] * 4)
    advance(model, pressure=[1] * 4)
    result = advance(model)
    assert result['actions'][0]['role'] == 'dirty_hit' and result['actions'][0]['drain_same_slot']
    assert result['drains'][0]['payload']['target_low'] == old['target'] & ((1 << 22) - 1)
    assert model.buffers[0].slots[0]['dirty'] == 1
    assert advance(model)['drains'][0]['payload']['target_low'] == new['target'] & ((1 << 22) - 1)


def test_input_and_returned_payload_mutation_cannot_rewrite_registered_reference_state():
    model, tx = ready_model(), transaction()
    advance(model, tx)
    tx['meta']['setIdx'] = 63
    result = advance(model)
    assert model.request2[0]['set_index'] == 0
    result = advance(model)
    result['requests'][0]['set_index'] = 63
    assert model.buffers[0].slots[0]['payload']['set_index'] == 0
    assert set(model.request2) == {None}


def test_bank_input_shape_is_not_silently_padded():
    with pytest.raises(ValueError, match='exactly four'):
        ready_model().advance(reset=0, accepted=None, read_pressure=[0, 0, 0])
