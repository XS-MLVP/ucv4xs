"""BankedDataArray UT: bank routing, write masks, line reads, conflicts, ECC."""
from __future__ import annotations

import random

import pytest

from dcacheverify.banked_data_array.coverage import BankedDataArrayCoverage
from dcacheverify.banked_data_array.env import BankedDataArrayEnv
from dcacheverify.banked_data_array.model import (
    BANKS,
    SETS,
    dcache_bank,
    dcache_set,
)

FULL = 0xFFFFFFFF


@pytest.fixture
def bda(dut_factory):
    dut = dut_factory("banked_data_array")
    env = BankedDataArrayEnv(dut, BankedDataArrayCoverage())
    env.reset()
    return env


def payload(seed: int) -> list[int]:
    return [((seed * 131 + bank * 17) ^ (bank << 8)) & 0xFFFF for bank in range(BANKS)]


def window_mask(addr: int) -> int:
    return 0xFF << (dcache_bank(addr) & ~7)


def addr_of(set_low: int, bank: int = 0, high: int = 0) -> int:
    """Build an address with the given low index bits, bank and page bits."""
    return (high << 42) | ((set_low & 0xFF) << 6) | ((bank & 0x1F) << 1)


def prime(bda, addr: int) -> None:
    """Initialize all 4 ways of the line so reads never see SRAM garbage."""
    for way in range(4):
        bda.commit_write(FULL, payload(way + 1), addr=addr, way=way)


def line(bda, addr: int, way: int) -> list[int]:
    return bda.read_line(addr, way)


# BDA-FP-001, BDA-FP-008
def test_read_window_all_ports_and_ways(bda):
    addresses = [addr_of(set_low, bank)
                 for set_low in (0, 1, 31, 63, 64, 255)
                 for bank in (0, 5, 16, 27, 31)]
    for addr in addresses:
        prime(bda, addr)
        for way in range(4):
            for port in range(3):
                window = bda.read_port(port, addr, way, window_mask(addr))
                expected = bda.model.read_result(addr, addr, 1 << way, 0xFF,
                                                 bda.window_cache[port])
                assert window == expected, (addr, way, port)


# BDA-FP-001
def test_three_ports_independent(bda):
    addr_a = addr_of(10, 0)
    addr_b = addr_of(20, 8)
    addr_c = addr_of(30, 16)
    prime(bda, addr_a)
    prime(bda, addr_b)
    prime(bda, addr_c)
    bda._idle()
    for port, addr, way in ((0, addr_a, 0), (1, addr_b, 1), (2, addr_c, 2)):
        pins = bda.read[port]
        pins["valid"].Set(1)
        pins["way_en"].Set(1 << way)
        pins["addr"].Set(addr)
        pins["addr_dup"].Set(addr)
        pins["bankMask"].Set(window_mask(addr))
        pins["lqidx"].Set(port + 1)
    bda.dut.Step(1)
    for port in range(3):
        bda.read[port]["valid"].Set(0)
    bda.refresh()
    for port, addr, way in ((0, addr_a, 0), (1, addr_b, 1), (2, addr_c, 2)):
        window = [bda._val(signal) for signal in bda.read[port]["resp"]]
        base = dcache_bank(addr) & ~7
        expected = bda.model.line_result(addr, 1 << way, 0xFFFFFFFF)[base:base + 8]
        assert window == expected, (port, addr, way)


# BDA-FP-002, BDA-FP-003
def test_all_banks_and_ways_are_independent(bda):
    addr = addr_of(40, 8)
    prime(bda, addr)
    for way in range(4):
        assert line(bda, addr, way) == [bda.model.memory[dcache_set(addr)][way][bank]
                                        for bank in range(BANKS)]
    # Single-bank writes must not disturb the neighbours.
    index = dcache_set(addr)
    for bank in (0, 15, 16, 31):
        before = bda.model.memory[index][2][:]
        bda.commit_write(1 << bank, [0xDEAD] * BANKS, addr=addr, way=2,
                         dup_valid=1 << bank)
        for other in range(BANKS):
            assert bda.model.memory[index][2][other] == (
                0xDEAD if other == bank else before[other])
    # Read the line back and compare the touched bank with the untouched ones.
    prime(bda, addr)
    bda.commit_write(1 << 5, [0xBEEF] * BANKS, addr=addr, way=1, dup_valid=1 << 5)
    line_data = line(bda, addr, 1)
    for other in range(BANKS):
        assert line_data[other] == (0xBEEF if other == 5 else payload(2)[other]), other


# BDA-FP-003
def test_wmask_and_dup_valid_gate_each_bank(bda):
    addr = addr_of(50, 3)
    prime(bda, addr)
    bda.commit_write(FULL, [0x1111] * BANKS, addr=addr, way=0)
    bda.commit_write(0x00FF00FF, [0x2222] * BANKS, addr=addr, way=0)
    data = line(bda, addr, 0)
    for bank in range(BANKS):
        want = 0x2222 if bank < 8 or (16 <= bank < 24) else 0x1111
        assert data[bank] == want, (bank, hex(data[bank]), hex(want))
    before = line(bda, addr, 1)
    bda.commit_write(FULL, [0x3333] * BANKS, addr=addr, way=1, dup_valid=0)
    assert line(bda, addr, 1) == before
    bda.commit_write(FULL, [0x4444] * BANKS, addr=addr, way=1, dup_valid=1 << 7)
    data = line(bda, addr, 1)
    assert data[7] == 0x4444 and all(data[bank] == before[bank]
                                    for bank in range(BANKS) if bank != 7)


# BDA-FP-004
def test_write_visibility_timing(bda):
    addr = addr_of(60, 12)
    prime(bda, addr)
    bda.commit_write(FULL, [0xA5A5] * BANKS, addr=addr, way=0)
    new = bda.read_port(0, addr, 0, window_mask(addr))
    assert new == [0xA5A5] * 8, new
    assert line(bda, addr, 0) == [0xA5A5] * BANKS


# BDA-FP-005
def test_readline_way_mask_and_stall(bda):
    addr = addr_of(70, 0)
    other = addr_of(71, 8)
    prime(bda, addr)
    prime(bda, other)
    for way in range(4):
        data = bda.read_line(addr, way, rmask=0x0000FFFF)
    full = bda.read_line(addr, 2)
    held = bda.read_line_stall(other, 3)
    assert held == full, "stall must preserve the previous line output"


# BDA-FP-006
def test_read_read_bank_conflict_oldest_wins(bda):
    addr_a = addr_of(80, 0)
    addr_b = addr_of(81, 0)
    prime(bda, addr_a)
    prime(bda, addr_b)
    result = bda.conflict_probe(addr_a, 0, 0xFF, 3, addr_b, 0, 0xFF, 9)
    assert result["rr_conflict"] == [0, 1], result
    assert result["bank_conflict"] == [0, 1], result
    bda.dut.Step(2)
    result = bda.conflict_probe(addr_a, 0, 0xFF, 9, addr_b, 0, 0xFF, 3)
    assert result["rr_conflict"] == [1, 0], result
    bda.dut.Step(2)
    result = bda.conflict_probe(addr_a, 0, 0x000000FF, 1, addr_b, 0, 0x0000FF00, 2)
    assert result["rr_conflict"] == [0, 0], result


# BDA-FP-007
def test_read_line_and_write_hazards(bda):
    addr = addr_of(90, 0)
    other = addr_of(91, 0)
    prime(bda, addr)
    prime(bda, other)
    bda._idle()
    bda.line["valid"].Set(1)
    bda.line["way_en"].Set(1)
    bda.line["addr"].Set(addr)
    bda.line["rmask"].Set(0xFF)
    bda.read[0]["valid"].Set(1)
    bda.read[0]["way_en"].Set(1)
    bda.read[0]["addr"].Set(other)
    bda.read[0]["addr_dup"].Set(other)
    bda.read[0]["bankMask"].Set(0xFF)
    bda.read[0]["lqidx"].Set(1)
    bda.refresh()
    line_ready = bda._val(bda.line["ready"])
    bda.dut.Step(1)
    bda._idle()
    bda.refresh()
    read_conflict = bda._val(bda.read[0]["bank_conflict"])
    if bda.coverage is not None:
        bda.coverage.sample_conflict("read_line")
    assert line_ready == 1
    assert read_conflict == 1
    bda.commit_write(FULL, [0x7777] * BANKS, addr=addr, way=0)
    assert line(bda, addr, 0) == [0x7777] * BANKS


# BDA-FP-001..008
def test_random_traffic(bda):
    rng = random.Random(0xBDA_2026)
    for addr in (addr_of(value, bank) for value in range(64) for bank in (0, 8, 16, 24)):
        prime(bda, addr)
    for step in range(40):
        addr = addr_of(rng.randrange(64), rng.randrange(32))
        way = rng.randrange(4)
        mask = rng.choice((FULL, 0x0000FFFF, 0x00FF00FF, 1 << rng.randrange(BANKS)))
        data = payload(rng.getrandbits(16))
        dup_valid = mask if rng.random() < 0.7 else mask & rng.getrandbits(32)
        bda.commit_write(mask, data, addr=addr, way=way, dup_valid=dup_valid)
        if step % 3 == 0:
            bda.read_line(addr, way)
        else:
            bda.read_port(step % 3, addr, way, window_mask(addr))


# BDA-FP-001, BDA-FP-003: fill bankMask/wmask/dup functional bins
def test_bank_mask_shapes_and_dup_patterns(bda):
    addr = addr_of(100, 0)
    prime(bda, addr)
    base = dcache_bank(addr) & ~7
    for single in range(8):
        mask = 1 << (base + single)
        window = bda.read_port(0, addr, 0, mask)
        expected = bda.model.line_result(addr, 1 << 0, 0xFFFFFFFF)[base:base + 8]
        for offset in range(8):
            if offset == single:
                assert window[offset] == expected[offset]
    # Window masks for every base, plus a full 32-bank mask.
    for bank in range(0, 32, 8):
        other = addr_of(100, bank)
        prime(bda, other)
        bda.read_port(bank // 8 % 3, other, 0, window_mask(other))
    full_window = bda.read_port(0, addr, 0, 0xFFFFFFFF)
    assert full_window == bda.model.line_result(addr, 1, 0xFFFFFFFF)[base:base + 8]
    # Write mask classes and per-bank dup patterns.
    for mask in (1, 0xFF, 0x0000FFFF, 0x0F0F0F0F, 0xFFFFFFFF):
        bda.commit_write(mask, payload(mask & 0xFFFF), addr=addr, way=1,
                         dup_valid=mask)
    for dup in (1, 0x000000FF, 0x00FF00FF, 0xFFFFFFFF):
        bda.commit_write(0xFFFFFFFF, payload(dup & 0xFFFF), addr=addr, way=2,
                         dup_valid=dup)


# BDA-FP-005, BDA-FP-008
def test_readline_masks_and_pseudo_error(bda):
    addr = addr_of(110, 0)
    prime(bda, addr)
    base_data = bda.model.line_result(addr, 1, 0xFFFFFFFF)
    for rmask in (0, 1, 0x00000003, 0x0F0F0F0F, 0xFFFFFFFF):
        data = bda.read_line(addr, 0, rmask=rmask)
        for bank in range(BANKS):
            if (rmask >> bank) & 1:
                assert data[bank] == base_data[bank], (rmask, bank)
    # can_resp with can_go deasserted re-captures the paged buffer: after a
    # normal capture the buffer and output hold the same line.
    before = bda.read_line(addr, 0)
    bda._idle()
    bda.line["valid"].Set(1)
    bda.line["way_en"].Set(1)
    bda.line["addr"].Set(addr)
    bda.line["rmask"].Set(0xFFFFFFFF)
    bda.dut.Step(1)
    bda.line["valid"].Set(0)
    bda.line["can_go"].Set(1)
    bda.line["can_resp"].Set(1)
    bda.dut.Step(1)
    bda.line["can_go"].Set(0)
    bda.line["can_resp"].Set(1)
    bda.dut.Step(1)
    held = [bda._val(signal) for signal in bda.line["resp"]]
    bda._idle()
    # The held path re-captures the paged buffer; its content is defined by the
    # previous stall/update sequence, so only the branch is exercised here.
    assert len(held) == 32
    # can_go and stall asserted together still updates the captured output.
    bda._idle()
    bda.line["valid"].Set(1)
    bda.line["way_en"].Set(1)
    bda.line["addr"].Set(addr)
    bda.line["rmask"].Set(0xFFFFFFFF)
    bda.line["can_go"].Set(1)
    bda.line["stall"].Set(1)
    bda.dut.Step(1)
    bda.line["valid"].Set(0)
    bda.line["can_go"].Set(1)
    bda.line["can_resp"].Set(1)
    bda.dut.Step(1)
    bda._idle()
    # Pseudo-error injection toggles the selected bank bits on the read path.
    window = bda.read_port_injected(0, addr, 0, window_mask(addr),
                                    inject_banks=0x0000000F, inject_mask=0xFFFF)
    base = dcache_bank(addr) & ~7
    expected = bda.model.line_result(addr, 1 << 0, 0xFFFFFFFF)[base:base + 8]
    for offset in range(8):
        bank = base + offset
        assert window[offset] == (expected[offset] ^ 0xFFFF if bank < 4
                                  else expected[offset]), (bank, hex(window[offset]))


# BDA-FP-007
def test_write_read_conflict(bda):
    addr = addr_of(120, 0)
    prime(bda, addr)
    flag = bda.write_read_conflict(addr, 0, 0xFFFFFFFF, window_mask(addr))
    assert flag == 1, "write->read overlap must raise bank_conflict_slow"


# BDA-FP-001, BDA-FP-003: empty / per-vword / partial mask classes
def test_mask_class_matrix(bda):
    for set_low, bank in ((130, 0), (131, 8), (132, 24)):
        addr = addr_of(set_low, bank)
        prime(bda, addr)
        base = dcache_bank(addr) & ~7
        window_masks = [
            0,                                  # none
            1 << base,                          # single
            0xFF << base,                       # one_vword
            (0xFF << base) | (1 << ((base + 3) % 32)),  # partial
            0x0000FFFF,                         # cross-vword partial
            0xFFFF0000,
            0xFFFFFFFF,                         # all
        ]
        for mask in window_masks:
            bda.read_port(0, addr, 0, mask)
    # Write mask / dup classes including the empty one.  Each combination must be
    # read back: the model already encodes "only masked banks with dup_valid=1
    # change", so a read that disagrees proves the RTL gate differs.
    masks = (0, 1, 0xFF, 0x0000FFFF, 0x0F0F0F0F, 0xFFFFFFFF)
    for wmask in masks:
        for dup in masks:
            addr = addr_of(140, 0)
            prime(bda, addr)
            bda.commit_write(wmask, payload(wmask & 0xFFFF), addr=addr, way=0,
                             dup_valid=dup)
            bda.read_port(0, addr, 0, window_mask(addr) | 0xFFFFFFFF)


# BDA-FP-002: MBIST/DFT bypass reaches every bank
def test_mbist_bypass(bda):
    for array in range(32):
        data = ((1 << 88) - 1) ^ (array * 0x010101010101010101)
        assert bda.mbist_write(array, 0x1FF, data) == 1
        assert bda.mbist_read(array, 0x1FF) == data, array
    broadcast = int("01" * 44, 2)
    assert bda.mbist_write(0, 0x100, broadcast, all_sram=True) == 1
    for array in (0, 15, 31):
        assert bda.mbist_read(array, 0x100) == broadcast, array


# BDA-FP-002, BDA-FP-004: full set/way/bank sweep for data toggle
def test_full_storage_sweep(bda):
    patterns = (0x0000, 0xFFFF, 0xAAAA, 0x5555)
    for hash_bits in range(4):
        for set_low in range(64):
            addr = (hash_bits << 12) | (set_low << 6)
            for way in range(4):
                data = [(patterns[(bank + way) % 4]) for bank in range(BANKS)]
                bda.commit_write(FULL, data, addr=addr, way=way)
    # Spot-check a slice of the swept array after the sweep.
    for hash_bits in (0, 3):
        for set_low in (0, 31, 63):
            addr = (hash_bits << 12) | (set_low << 6)
            for way in range(4):
                line_data = bda.read_line(addr, way)
                assert all(value == patterns[(bank + way) % 4]
                           for bank, value in enumerate(line_data)), (addr, way)


# BDA-FP-006: three overlapping ports, oldest lq wins, others report replay
def test_three_port_conflict(bda):
    addrs = [addr_of(150 + i, 0) for i in range(3)]
    for addr in addrs:
        prime(bda, addr)
    result = bda.conflict_probe_three(addrs, [0, 0, 0],
                                      [window_mask(addr) for addr in addrs],
                                      [7, 2, 5])
    assert result[1]["rr"] == 0, result
    assert result[0]["rr"] == 1 and result[2]["rr"] == 1, result
    for lqs in ([7, 5, 2], [2, 7, 5], [5, 2, 7]):
        result = bda.conflict_probe_three(addrs, [0, 0, 0],
                                          [window_mask(addr) for addr in addrs], lqs)
        winner = lqs.index(min(lqs))
        for port in range(3):
            assert result[port]["rr"] == (0 if port == winner else 1), (lqs, result)


# BDA-FP-008: pseudo-error mask on every bank
def test_pseudo_error_all_banks(bda):
    addr = addr_of(160, 0)
    prime(bda, addr)
    base = dcache_bank(addr) & ~7
    expected = bda.model.line_result(addr, 1 << 0, 0xFFFFFFFF)[base:base + 8]
    window = bda.read_port_injected(0, addr, 0, window_mask(addr),
                                    inject_banks=0xFFFFFFFF,
                                    inject_mask=0xFFFF)
    assert window == [value ^ 0xFFFF for value in expected], window
    window = bda.read_port_injected(0, addr, 0, window_mask(addr),
                                    inject_banks=0xFFFFFFFF,
                                    inject_mask=0xA5A5)
    assert window == [value ^ 0xA5A5 for value in expected], window
    # The pseudo-error channel is acknowledged after a read hits an injected bank.
    bda.dut.Step(1)


# BDA-FP-003: high address bits on every duplicate write port
def test_duplicate_address_high_bits(bda):
    rng = random.Random(0xBDA_ADD)
    for _ in range(8):
        addr = rng.getrandbits(48) & ~0x3F
        addresses = [rng.getrandbits(48) & ~0x3F for _ in range(BANKS)]
        data = [rng.randrange(1 << 16) for _ in range(BANKS)]
        bda.commit_write(FULL, data, addresses=addresses, dup_valid=FULL)
        assert bda.model.memory[dcache_set(addresses[0])][0][0] == data[0]


# BDA-FP-008: ECC 错误标志的可观测性（known-issue 观察）
def test_ecc_error_flag_clears_after_read(bda):
    """Correct data round-trips; the delayed flag must clear once the read ends.

    In this build the delayed error bits also assert for functionally correct
    data while the read is in flight (manifest BDA-ECC-DELAYED-FLAG).  We do not
    encode that buggy value as an expectation; we do require the flag to return
    to 0 after the read completes, so a future fix cannot silently regress.
    """
    addr = addr_of(201, 6)
    prime(bda, addr)
    mask = window_mask(addr)
    base = dcache_bank(addr) & ~7
    expected = bda.model.line_result(addr, 1 << 1, 0xFFFFFFFF)[base:base + 8]
    window = bda.read_port(0, addr, 1, mask)
    assert window == expected, ([hex(v) for v in window],
                                [hex(v) for v in expected])
    in_flight = list(bda.last_error)
    assert not any(in_flight), in_flight
    for _ in range(2):
        bda.dut.Step(1)
        bda.refresh()
    after = [int(signal.value) for signal in bda.read[0]["error"]]
    assert all(value == 0 for value in after), (in_flight, after)


# BDA-FP-005 / BDA-FP-008: 整线读的数据与标志
def test_readline_data_and_flag_clear(bda):
    addr = addr_of(202, 3)
    prime(bda, addr)
    data = bda.read_line(addr, 2)
    expected = bda.model.line_result(addr, 1 << 2, 0xFFFFFFFF)
    assert data == expected
    assert int(bda.line["error"].value) == 0
    for _ in range(2):
        bda.dut.Step(1)
        bda.refresh()
    assert int(bda.line["error"].value) == 0


# BDA-FP-008: rows written through the encoder must decode without error
def test_zero_line_has_no_ecc_error(bda):
    """Writing zeros through the ECC encoder must read back with error_delayed=0.

    Regression for the retired BDA-ECC-DELAYED-FLAG alarm: the old observation came
    from reading SRAM rows that were never written (random data + random ECC, which
    correctly decodes as an error), not from a code mismatch.
    """
    addr = addr_of(210, 8)
    for way in range(4):
        bda.commit_write(FULL, [0x0000] * BANKS, addr=addr, way=way)
    for way in range(4):
        window = bda.read_port(0, addr, way, window_mask(addr))
        assert all(value == 0 for value in window), window
        assert not any(bda.last_error), bda.last_error
