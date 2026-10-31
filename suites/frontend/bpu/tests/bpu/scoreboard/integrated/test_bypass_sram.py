"""Pure SRAM contract tests, independent of native or captured RAM contents."""
from copy import deepcopy
import pytest
from suites.frontend.bpu.bpu.model.bypass.sram import SramReference
from suites.frontend.bpu.bpu.model.bypass.sram import pack_data
from suites.frontend.bpu.bpu.model.bypass.sram import zero_data


def request(**changes):
    value = dict(valid=0, index=0, force=0, **zero_data())
    value.update(changes)
    return value


def cleared():
    reference = SramReference()
    reference.advance(0, request(), reset=True)
    for _ in range(128):
        reference.advance(0, request())
    assert reference.reset_done == 1
    return reference


def test_each_reset_address_is_cleared_without_seeding_initial_RAM():
    reference = SramReference()
    assert reference.memory == [None] * 512
    for cycle in range(128):
        assert reference.reset_done == 0 and reference.reset_set == cycle
        reference.advance(0, request())
        assert sum(item is not None for item in reference.memory) == (cycle + 1) * 4
    assert reference.reset_done == 1 and reference.memory == [zero_data()] * 512


def test_all512_cold_reads_are_defined_only_after_real_reset_sequence():
    reference = cleared()
    for index in range(512):
        reference.advance(index, request())
        assert reference.response(dict(hit=0)) == zero_data()
        assert reference.bank_response(index % 4) == zero_data()


@pytest.mark.parametrize('bank', range(4))
@pytest.mark.parametrize('counter', (0, 4, 7))
def test_nonconflicting_write_and_later_same_bank_read(bank, counter):
    reference = cleared()
    index, other = 32 * 4 + bank, (bank + 1) % 4
    write = request(valid=1, index=index, data_valid=1, tag=37, position=5, counter=counter)
    before = deepcopy(reference.memory)
    controls = reference.controls(other, write)
    assert controls[bank]['write_valid'] == 1
    assert sum(control['write_valid'] for control in controls) == 1
    reference.advance(other, write)
    assert reference.response(dict(hit=0)) == zero_data()
    assert reference.bank_response(bank) is None  # raw write-mode response is X
    assert [i for i, (old, new) in enumerate(zip(before, reference.memory)) if old != new] == [index]
    reference.advance(index, request())
    assert reference.response(dict(hit=0)) == dict(data_valid=1, tag=37, position=5, counter=counter)


@pytest.mark.parametrize('bank', range(4))
def test_same_bank_offer_is_blocked_until_forced(bank):
    reference = cleared()
    index = 64 * 4 + bank
    write = request(valid=1, index=index, data_valid=1, tag=12, counter=6)
    assert reference.controls(bank, write)[bank]['write_valid'] == 0
    reference.advance(bank, write)
    assert reference.memory[index] == zero_data()
    forced = dict(write, force=1)
    event = reference.advance(bank, forced)
    assert event['forced_conflict'] == event['write_success'] == 1
    assert reference.response(dict(hit=0)) == dict(data_valid=0)
    reference.advance(index, request())
    assert reference.response(dict(hit=0)) == dict(data_valid=1, tag=12, position=0, counter=6)


def test_shadow_hit_overrides_undefined_forced_SRAM_response():
    reference = cleared()
    reference.advance(0, request(valid=1, index=0, force=1, data_valid=1, counter=5))
    shadow = dict(hit=1, data_valid=1, tag=9, position=2, counter=7)
    assert reference.response(shadow) == {key: shadow[key] for key in zero_data()}


def test_reset_writes_take_priority_over_normal_requests():
    reference = SramReference()
    write = request(valid=1, force=1, index=127, data_valid=1, tag=255, position=15, counter=7)
    controls = reference.controls(91, write)
    assert all(item['array']['data'] == 0 and item['array']['address'] == 0 for item in controls)
    reference.advance(91, write)
    assert reference.memory[:4] == [zero_data()] * 4
    assert reference.memory[127] is None


def test_packed_SRAM_payload_has_explicit_reserved_low_bit():
    assert pack_data(dict(data_valid=1, tag=255, position=15, counter=7)) == 131070
    assert pack_data(zero_data()) == 0


def test_malformed_read_index_rejected_before_mutating_reference():
    reference = cleared()
    memory = deepcopy(reference.memory)
    with pytest.raises(ValueError, match='nine-bit'):
        reference.advance(512, request())
    assert reference.memory == memory
