"""CtrlUnit UT driven by docs/functional-points-ctrl-unit.md.

Register accesses run over the real TileLink register port; pseudo-error
outputs are checked cycle by cycle against the semantic rules (capture clears
ese, delay counter, persist reload, consumer backpressure).
"""
from __future__ import annotations

import random

import pytest

from dcacheverify.common.runtime import execution
from dcacheverify.ctrl_unit.coverage import CtrlUnitCoverage
from dcacheverify.ctrl_unit.env import BANKS, CtrlFields, CtrlUnitEnv, TAG_MASK_BITS


@pytest.fixture
def cu(dut_factory):
    dut = dut_factory("ctrl_unit")
    return CtrlUnitEnv(dut, CtrlUnitCoverage())


def bank_mask(*banks: int) -> int:
    return sum(1 << bank for bank in banks)


# CU-FP-001
async def test_reset_defaults(cu):
    async with execution(cu.dut):
        await cu.reset()
        assert cu.pe_tag()[0] == 0
        assert cu.pe1["valid"].value == 0
        for index in range(11):
            assert await cu.read(index) == 0, f"index {index} not zero after reset"


# CU-FP-002, CU-FP-004
async def test_ctrl_bitfield_roundtrip(cu):
    async with execution(cu.dut):
        await cu.reset()
        patterns = [
            0x0,
            0x2,                      # persist
            0x4,                      # ede
            0x8,                      # comp
            0x6,
            0xC,
            bank_mask(0) << 4,
            (bank_mask(1, 5, 31) << 4),
            0xF << 4,
            0xFF_FFFF_FFFF,           # bank bits only, ese=0
            0xFFFF_FFFF_FFF0,         # padding bits above the bank field
        ]
        for value in patterns:
            await cu.write(0, value)
            got = await cu.read(0)
            assert got == value, f"ctrl {value:#x} read back {got:#x}"
        # ese alone is consumed by the capture pipeline even with bank=0:
        # channel valid rises, payload bank0 stays low, and ctrl reads back 0.
        await cu.quiesce()
        await cu.write(0, 0x1)
        await cu.edge()
        valid, bank0, _ = cu.pe_tag()
        assert valid == 1, "capture is decided by ese/comp, not by bank bits"
        assert bank0 == 0, "bank0 payload must stay disabled"
        assert await cu.read(0) == 0, "single-shot ese is cleared at capture"
        cu.set_pe_ready(0, True)
        await cu.edge()
        cu.set_pe_ready(0, False)


# CU-FP-003, CU-FP-004
async def test_delay_and_mask_registers_roundtrip(cu):
    async with execution(cu.dut):
        await cu.reset()
        for delay in (0, 1, 7, 0x0123_4567_89AB_CDEF):
            await cu.write(1, delay)
            assert await cu.read(1) == delay
        # tagMask keeps only the low 40 bits of a 64-bit write.
        await cu.write(2, 0xFFFF_FFFFFF)
        assert await cu.read(2) == 0xFF_FFFFFFFF
        await cu.write(2, 0xABCD_EF12_3456)
        assert await cu.read(2) == 0xCD_EF123456
        # Eight groups of four 16-bit data masks, each independently readable.
        groups = [0x1111_2222_3333_4444 << (8 * group) for group in range(8)]
        groups = [value & ((1 << 64) - 1) for value in groups]
        for group, value in enumerate(groups):
            await cu.write(3 + group, value)
        for group, value in enumerate(groups):
            assert await cu.read(3 + group) == value, f"data mask group {group}"


# CU-FP-003
async def test_partial_write_masks_are_ignored(cu):
    async with execution(cu.dut):
        await cu.reset()
        await cu.write(0, 0x8)
        await cu.write(0, 0xFFFF_FFFF, mask=0x0F)
        assert await cu.read(0) == 0x8
        await cu.write(1, 5)
        await cu.write(1, 9, mask=0xF0)
        assert await cu.read(1) == 5
        tag_old = 0x0F0F0F0F0F & ((1 << 40) - 1)
        await cu.write(2, tag_old)
        await cu.write(2, 0xF0F0F0F0F0, mask=0x0F)
        assert await cu.read(2) == tag_old
        # Data mask group: only banks whose 2-byte half is fully masked update.
        await cu.write(3, 0x1111_2222_3333_4444)
        await cu.write(3, 0xAAAA_BBBB_CCCC_DDDD, mask=0x0F)
        assert await cu.read(3) == 0x1111_2222_CCCC_DDDD
        await cu.write(3, 0xEEEE_FFFF_9999_8888, mask=0xF0)
        assert await cu.read(3) == 0xEEEE_FFFF_CCCC_DDDD
        await cu.write(3, 0x0, mask=0x00)
        assert await cu.read(3) == 0xEEEE_FFFF_CCCC_DDDD


# CU-FP-005, CU-FP-009
async def test_tag_injection_single_shot_and_hold(cu):
    async with execution(cu.dut):
        await cu.reset()
        await cu.program_tag_mask((1 << TAG_MASK_BITS) - 1)
        await cu.program_ctrl(CtrlFields(ese=True, comp=0, bank=bank_mask(0)))
        await cu.edge()  # capture into the one-stage pipeline
        valid, bank0_valid, mask = cu.pe_tag()
        assert valid == 1 and bank0_valid == 1
        assert mask == (1 << TAG_MASK_BITS) - 1
        # ese is cleared at capture, before the consumer accepts.
        assert await cu.read(0) == (bank_mask(0) << 4)
        for _ in range(3):
            await cu.edge()
            assert cu.pe_tag()[0] == 1, "request must hold while consumer is not ready"
            assert cu.pe_tag()[2] == (1 << TAG_MASK_BITS) - 1
        cu.coverage.sample_inject("tag", bank_mask(0), 0, False,
                                  "backpressured", (1 << TAG_MASK_BITS) - 1)
        cu.set_pe_ready(0, True)
        await cu.edge()
        assert cu.pe_tag()[0] == 0
        for _ in range(4):
            await cu.edge()
            assert cu.pe_tag()[0] == 0, "single-shot injection must not repeat"
        # bank0 low: the channel still captures (and consumes ese), but the
        # payload bank0 bit is low, so no tag error is actually injected.
        await cu.program_ctrl(CtrlFields(ese=True, comp=0, bank=bank_mask(1, 2)))
        await cu.edge()
        valid, bank0, _ = cu.pe_tag()
        assert valid == 1 and bank0 == 0
        cu.coverage.sample_inject("tag", bank_mask(1, 2), 0, False,
                                  "backpressured", 0)
        cu.set_pe_ready(0, True)
        await cu.edge()
        cu.set_pe_ready(0, False)
        # bank=0 is the 'none' case: valid channel, all payload bits low.
        await cu.program_ctrl(CtrlFields(ese=True, comp=0, bank=0))
        await cu.edge()
        valid, bank0, _ = cu.pe_tag()
        assert valid == 1 and bank0 == 0
        cu.coverage.sample_inject("tag", 0, 0, False, "backpressured", 0)
        cu.set_pe_ready(0, True)
        await cu.edge()
        cu.set_pe_ready(0, False)
        # All banks selected: only bank0 is routed out, but the channel payload
        # must show bank0 valid.
        await cu.program_ctrl(CtrlFields(ese=True, comp=0, bank=(1 << BANKS) - 1))
        await cu.edge()
        valid, bank0, _ = cu.pe_tag()
        assert valid == 1 and bank0 == 1
        cu.coverage.sample_inject("tag", (1 << BANKS) - 1, 0, False,
                                  "backpressured", 0)
        cu.set_pe_ready(0, True)
        await cu.edge()
        cu.set_pe_ready(0, False)


# CU-FP-005
async def test_tag_mask_shapes(cu):
    async with execution(cu.dut):
        await cu.reset()
        for mask in (0, 1, 0x0F0F_0F0F0F, (1 << TAG_MASK_BITS) - 1):
            await cu.program_tag_mask(mask)
            await cu.program_ctrl(CtrlFields(ese=True, comp=0, bank=bank_mask(0)))
            await cu.edge()
            valid, _, got = cu.pe_tag()
            assert valid == 1
            assert got == (mask & ((1 << TAG_MASK_BITS) - 1))
            cu.coverage.sample_inject("tag", bank_mask(0), 0, False,
                                      "immediate", mask)
            cu.set_pe_ready(0, True)
            await cu.edge()
            cu.set_pe_ready(0, False)
        # Final zero capture so every tag-mask output bit returns 1 -> 0.
        await cu.program_tag_mask(0)
        await cu.program_ctrl(CtrlFields(ese=True, comp=0, bank=bank_mask(0)))
        await cu.edge()
        assert cu.pe_tag() == (1, 1, 0)
        cu.set_pe_ready(0, True)
        await cu.edge()
        cu.set_pe_ready(0, False)


# CU-FP-006
async def test_data_injection_banks_and_masks(cu):
    async with execution(cu.dut):
        await cu.reset()
        for group in range(8):
            pattern = 0x1111_2222_3333_4444 * (group + 1)
            await cu.program_data_mask(group, pattern & ((1 << 64) - 1))
        expected = {}
        for group in range(8):
            value = (0x1111_2222_3333_4444 * (group + 1)) & ((1 << 64) - 1)
            for bank in range(4):
                expected[4 * group + bank] = (value >> (16 * bank)) & 0xFFFF
        # single bank
        await cu.program_ctrl(CtrlFields(ese=True, comp=1, bank=bank_mask(2)))
        await cu.edge()
        data = cu.pe_data()
        assert cu.pe1["valid"].value
        assert [bank for bank, (valid, _) in enumerate(data) if valid] == [2]
        assert data[2][1] == expected[2]
        cu.coverage.sample_inject("data", bank_mask(2), 0, False,
                                  "backpressured", 0)
        cu.set_pe_ready(1, True)
        await cu.edge()
        cu.set_pe_ready(1, False)
        # multi bank
        selected = (0, 5, 31)
        await cu.program_ctrl(CtrlFields(ese=True, comp=1, bank=bank_mask(*selected)))
        await cu.edge()
        data = cu.pe_data()
        active = [bank for bank, (valid, _) in enumerate(data) if valid]
        assert active == list(selected)
        for bank in selected:
            assert data[bank][1] == expected[bank]
        cu.coverage.sample_inject("data", bank_mask(*selected), 0, False,
                                  "backpressured", 0)
        cu.set_pe_ready(1, True)
        await cu.edge()
        cu.set_pe_ready(1, False)
        # all banks
        await cu.program_ctrl(CtrlFields(ese=True, comp=1, bank=(1 << BANKS) - 1))
        await cu.edge()
        data = cu.pe_data()
        assert all(valid for valid, _ in data)
        assert [mask for _, mask in data] == [expected[bank] for bank in range(BANKS)]
        cu.coverage.sample_inject("data", (1 << BANKS) - 1, 0, False,
                                  "backpressured", 0)
        cu.set_pe_ready(1, True)
        await cu.edge()
        cu.set_pe_ready(1, False)
        # No bank selected: the channel still captures (consuming ese), but all
        # per-bank payload valid bits are low.
        await cu.program_ctrl(CtrlFields(ese=True, comp=1, bank=0))
        await cu.edge()
        assert cu.pe1["valid"].value == 1
        assert all(valid == 0 for valid, _ in cu.pe_data())
        cu.coverage.sample_inject("data", 0, 0, False, "backpressured", 0)
        cu.set_pe_ready(1, True)
        await cu.edge()
        cu.set_pe_ready(1, False)


# CU-FP-007, CU-FP-008
async def test_delay_and_persist_matrix(cu):
    async with execution(cu.dut):
        await cu.reset()
        for delay in (0, 1, 3, 10):
            for persist in (False, True):
                await cu.quiesce()
                await cu.program_delay(delay)
                await cu.program_ctrl(CtrlFields(ese=True, persist=persist, ede=True,
                                                  comp=0, bank=bank_mask(0)))
                # Counter starts at `delay`; the pipeline adds one cycle.
                first = None
                for cycle in range(1, delay + 4):
                    await cu.edge()
                    if cu.pe_tag()[0]:
                        first = cycle
                        break
                assert first == delay + 1, (delay, persist, first)
                cu.coverage.sample_inject("tag", bank_mask(0), delay, persist,
                                          "backpressured", 0)
                cu.set_pe_ready(0, True)
                await cu.edge()
                cu.set_pe_ready(0, False)
                if persist:
                    cu.set_pe_ready(0, True)
                    samples = []
                    for _ in range(3 * (delay + 1) + 2):
                        await cu.edge()
                        samples.append(cu.pe_tag()[0])
                    cu.set_pe_ready(0, False)
                    if delay == 0:
                        # No counter reload latency: a fresh request every cycle.
                        assert all(value == 1 for value in samples), samples
                    else:
                        ones = [index for index, value in enumerate(samples) if value]
                        assert len(ones) >= 3, (delay, samples)
                        gaps = {b - a for a, b in zip(ones, ones[1:])}
                        assert gaps == {delay + 1}, (delay, samples, gaps)
                else:
                    for _ in range(3):
                        await cu.edge()
                        assert cu.pe_tag()[0] == 0, "single-shot must not repeat"


# CU-FP-009
async def test_consumer_backpressure_holds_request(cu):
    async with execution(cu.dut):
        await cu.reset()
        await cu.program_tag_mask(0x0F0F0F0F0F)
        await cu.program_ctrl(CtrlFields(ese=True, comp=0, bank=bank_mask(0)))
        await cu.edge()
        assert cu.pe_tag()[0] == 1
        for _ in range(4):
            await cu.edge()
            assert cu.pe_tag() == (1, 1, 0x0F0F0F0F0F)
        cu.set_pe_ready(0, True)
        await cu.edge()
        assert cu.pe_tag()[0] == 0


# CU-FP-002
async def test_d_channel_backpressure_and_single_outstanding(cu):
    async with execution(cu.dut):
        await cu.reset()
        await cu.send_write(1, 0x1234)
        # D not accepted yet: queue is full, A must not accept a new request.
        assert await cu.try_write_while_full(0, 0x1) is False
        assert cu.d["valid"].value
        await cu.edge()
        assert cu.d["valid"].value, "D response must stay while d_ready is low"
        cu.d["ready"].Set(1)
        await cu.edge()
        assert cu.d["valid"].value == 0
        cu.d["ready"].Set(0)
        assert await cu.read(1) == 0x1234
        # Held read keeps the data stable and blocks A.
        await cu.write(1, 0x55)
        assert await cu.read_held(1) == 0x55


# CU-FP-002, CU-FP-004
async def test_random_register_traffic(cu):
    rng = random.Random(0xC7A_2026)
    async with execution(cu.dut):
        await cu.reset()
        model = {"ctrl": 0, "delay": 0, "tag_mask": 0, "data": [0] * 8}
        indices = list(range(11))
        for step in range(120):
            index = rng.choice(indices)
            if rng.random() < 0.5:
                value = rng.getrandbits(64)
                if index == 0:
                    # Keep bank=0 so the random control value never starts an
                    # injection; injection is covered by its own scenarios.
                    value &= ~(((1 << BANKS) - 1) << 4)
                if index == 2:
                    value &= (1 << 40) - 1
                await cu.write(index, value)
                if index == 0:
                    model["ctrl"] = value
                elif index == 1:
                    model["delay"] = value
                elif index == 2:
                    model["tag_mask"] = value
                else:
                    model["data"][index - 3] = value
            else:
                got = await cu.read(index)
                if index == 0:
                    want = model["ctrl"]
                elif index == 1:
                    want = model["delay"]
                elif index == 2:
                    want = model["tag_mask"]
                else:
                    want = model["data"][index - 3]
                assert got == want, (step, index, hex(got), hex(want))


# CU-FP-002, CU-FP-004
async def test_alias_address_and_source_echo(cu):
    async with execution(cu.dut):
        await cu.reset()
        # The register decoder uses the low address bits; upper bits are aliases.
        bases = (0x0, 0x80, 0x15555_500, 0x2AAAA_A80, 0x3FFFF_F80)
        for index, value in ((0, 0x8), (1, 0x1234), (2, 0x0F0F0F0F0F), (3, 0x0123_4567_89AB_CDEF)):
            await cu.write(index, value)
            for source in (0, 1, 7, 15):
                for base in bases:
                    got = await cu.read(index, addr=base | (index * 8), source=source)
                    assert got == value, (index, source, hex(base), hex(got))
        # Every address bit above the decode field must alias.
        for bit in range(7, 30):
            addr = (1 << bit) | (1 * 8)
            assert await cu.read(1, addr=addr, source=3) == 0x1234, f"alias bit {bit}"
        # A write through an alias address must hit the same register.
        await cu.write(1, 0x7777, addr=0x2AAAA_A88, source=9)
        assert await cu.read(1) == 0x7777


# CU-FP-004, CU-FP-006
async def test_full_width_register_and_mask_bit_sweep(cu):
    async with execution(cu.dut):
        await cu.reset()
        full = (1 << 64) - 1
        await cu.write(0, full & ~0x1)   # ese=0, all other ctrl bits set
        assert await cu.read(0) == (full & ~0x1)
        await cu.write(0, 0)
        await cu.write(1, full)
        assert await cu.read(1) == full
        await cu.write(1, 0)
        await cu.write(2, (1 << 40) - 1)
        assert await cu.read(2) == (1 << 40) - 1
        await cu.write(2, 0)
        # Every data mask bank sees all 16 bits high and low.
        for group in range(8):
            await cu.write(3 + group, full)
        for group in range(8):
            assert await cu.read(3 + group) == full
            cu.coverage.sample_regs("data_mask", "match")
        # Capture all banks twice with masks all-ones then all-zero so every
        # 16-bit data-mask output toggles in both directions.
        for group in range(8):
            await cu.write(3 + group, full)
        await cu.program_ctrl(CtrlFields(ese=True, comp=1, bank=(1 << BANKS) - 1))
        await cu.edge()
        assert [mask for _, mask in cu.pe_data()] == [0xFFFF] * BANKS
        cu.set_pe_ready(1, True)
        await cu.edge()
        cu.set_pe_ready(1, False)
        for group in range(8):
            await cu.write(3 + group, 0)
        await cu.program_ctrl(CtrlFields(ese=True, comp=1, bank=(1 << BANKS) - 1))
        await cu.edge()
        assert [mask for _, mask in cu.pe_data()] == [0] * BANKS
        cu.set_pe_ready(1, True)
        await cu.edge()
        cu.set_pe_ready(1, False)
        for group in range(8):
            assert await cu.read(3 + group) == 0
