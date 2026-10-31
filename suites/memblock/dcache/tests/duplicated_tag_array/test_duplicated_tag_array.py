"""DuplicatedTagArray UT: every test is driven by the semantic functional points.

See docs/functional-points-duplicated-tag-array.md. Reads are compared with an
independent tag/ECC model; functional coverage is sampled only after comparison.
"""
from __future__ import annotations

import random

import pytest

from suites.memblock.dcache.execution import execution
from suites.memblock.dcache.duplicated_tag_array.coverage import ALTERNATING, DuplicatedTagArrayCoverage
from suites.memblock.dcache.duplicated_tag_array.env import (
    DuplicatedTagArrayEnv,
    SWEEP_CYCLES,
    Write,
)
from suites.memblock.dcache.duplicated_tag_array.model import TAG_MASK, codeword, encode_ecc

SETS = 256


@pytest.fixture
def dta(dut_factory):
    dut = dut_factory("duplicated_tag_array")
    return DuplicatedTagArrayEnv(dut, DuplicatedTagArrayCoverage())


# DTA-FP-001, DTA-FP-005
async def test_reset_sweep_blocks_reads_then_clears_all_sets(dta):
    async with execution(dta):
        observed = await dta.observe_sweep()
        assert all(value == 0 for value in observed["ready_during_sweep"]), observed
        assert observed["ready_after_sweep"] == 1, observed
        # The whole 256-set array must read back the zero codeword, way by way.
        await dta.read_every_set(0)
        for port in range(4):
            words = await dta.read(port, 0, order="single")
            assert words == [0, 0, 0, 0]
        for port in range(4):
            words = await dta.read(port, 255, order="single")
            assert words == [0, 0, 0, 0]


# DTA-FP-002, DTA-FP-006
async def test_all_ports_see_the_same_four_way_tags(dta):
    async with execution(dta):
        await dta.reset()
        tags = [0x012345678, 0x0ABCDEF01, 0x0FEDCBA98, 0x000000001]
        for way, tag in enumerate(tags):
            await dta.write(0x40, 1 << way, tag,
                            target="same_set_rewrite" if way else "new_set")
        await dta.read_all_ports(0x40)
        # Rewrite one way only; every duplicate must observe the new value.
        await dta.write(0x40, 0b0100, 0x0DEADBEEF, target="same_set_rewrite")
        for port in range(4):
            words = await dta.read(port, 0x40)
            assert words[2] == codeword(0x0DEADBEEF)
            assert words[0] == codeword(tags[0])
            assert words[1] == codeword(tags[1])
            assert words[3] == codeword(tags[3])


# DTA-FP-003, DTA-FP-004
async def test_way_mask_and_set_class_matrix(dta):
    async with execution(dta):
        await dta.reset()
        representatives = {0: "boundary_0", 10: "low", 100: "mid", 200: "high",
                           255: "boundary_255"}
        for index in representatives:
            for mask in (0, 0b0001, 0b0011, 0b0111, 0b1111):
                tag = (index << 12) | (mask << 4) | 0x5
                await dta.write(index, mask, tag,
                                target="new_set")
                words = await dta.read(0, index)
                for way in range(4):
                    if (mask >> way) & 1:
                        assert words[way] == codeword(tag)
        # Every non-zero mask must leave unselected ways untouched.
        await dta.write(0x33, 0b1010, 0x0AAAAAAA1)
        await dta.write(0x33, 0b0101, 0x055555555)
        words = await dta.read(0, 0x33)
        assert words[0] == codeword(0x055555555)
        assert words[1] == codeword(0x0AAAAAAA1)
        assert words[2] == codeword(0x055555555)
        assert words[3] == codeword(0x0AAAAAAA1)


# DTA-FP-003, DTA-FP-006
async def test_set_independence_and_boundaries(dta):
    async with execution(dta):
        await dta.reset()
        writes = {0: 0x0FEDCBA98, 1: 0x001234567, 127: 0x0ABCDEF01,
                  128: 0x0F0F0F0F0, 200: 0x012345678, 254: 0x0DEADBEEF,
                  255: 0x0AAAA5555}
        for index, tag in writes.items():
            await dta.write(index, 0b1111, tag, target="new_set")
        # Every set, including all untouched ones, must match the model.
        await dta.read_every_set(0)
        # Disturb one boundary set and re-check its neighbours.
        await dta.write(0, 0b0001, 0x0FFFFFFFF, target="same_set_rewrite")
        await dta.write(255, 0b1000, 0x000000000, target="same_set_rewrite")
        for index in (0, 1, 255):
            await dta.read_all_ports(index)


# DTA-FP-005
async def test_single_port_read_write_conflict(dta):
    async with execution(dta):
        await dta.reset()
        await dta.write(7, 0b1111, 0x011111111)
        # Same-set conflict: the read must be refused, and must not corrupt the row.
        await dta.denied_read_during_write(0, 7, Write(7, 0b0010, 0x022222222),
                                           relation="same_set")
        words = await dta.read_after_write(0, 7)
        assert words[1] == codeword(0x022222222)
        # Different-set conflict: still refused because the SRAM port is busy.
        await dta.denied_read_during_write(2, 7, Write(9, 0b0001, 0x033333333),
                                           relation="different_set")
        await dta.read_all_ports(7)
        await dta.read_all_ports(9)
        # A zero-mask write still owns the port for its cycle.
        await dta.denied_read_during_write(1, 9, Write(9, 0b0000, 0x044444444),
                                           relation="same_set")
        words = await dta.read(1, 9)
        assert words[0] == codeword(0x033333333)


# DTA-FP-002, DTA-FP-005
async def test_back_to_back_reads_across_ports(dta):
    async with execution(dta):
        await dta.reset()
        for index in (3, 4, 5):
            await dta.write(index, 0b1111, 0x1000 + index, target="new_set")
        # Same set on consecutive cycles: the SRAM must return fresh data each edge.
        sequence = [(0, 3), (1, 3), (2, 3), (3, 3)]
        for port, index in sequence:
            dta._drive_reads([(port, index)])
            await dta.edge()
            words = dta.resp_words(port)
            expected = dta.model.read(index)
            assert words == expected, (port, index, words, expected)
            dta.coverage.sample_read(port, index, "back_to_back_same_set")
        dta._drive_reads([])
        # Different sets on one port back-to-back.
        for index in (3, 4, 5, 4, 3):
            words = await dta.read(0, index, order="back_to_back_diff_set")
            assert words[0] == codeword(0x1000 + index)


# DTA-FP-007
async def test_ecc_codeword_is_linear_and_single_bit_sensitive(dta):
    async with execution(dta):
        await dta.reset()
        masks = []
        for bit in range(36):
            tag = 1 << bit
            await dta.write(100, 0b0001, tag, target="same_set_rewrite")
            words = await dta.read(0, 100)
            assert words[0] == codeword(tag)
            masks.append(words[0] >> 36)
        assert all(mask != 0 for mask in masks)
        assert len(set(masks)) == len(masks), "single-bit tags must have distinct ECC"
        rng = random.Random(0xD7A_2026)
        for _ in range(64):
            a = rng.getrandbits(36)
            b = rng.getrandbits(36)
            await dta.write(100, 0b0010, a, target="same_set_rewrite")
            words = await dta.read(0, 100)
            assert words[1] == codeword(a)
            # Linearity is checked against the reference encoder, and the DUT
            # must realize the XOR of the two codewords' tag/ecc split.
            assert encode_ecc(a ^ b) == encode_ecc(a) ^ encode_ecc(b)
        for tag in (0, 0x0FFFFFFFFF, 0x000000001, 0x080000000):
            await dta.write(200, 0b1111, tag, target="new_set")
            for port in range(4):
                words = await dta.read(port, 200)
                assert words == [codeword(tag)] * 4


# DTA-FP-001..007
async def test_random_legal_traffic(dta):
    async with execution(dta):
        await dta.reset()
        rng = random.Random(0xD7A_5EED)
        written = set()
        for _ in range(400):
            roll = rng.random()
            if roll < 0.55:
                index = rng.randrange(SETS)
                mask = rng.choice((0, 1, 2, 4, 8, 3, 5, 9, 6, 10, 12, 7, 11, 13, 14, 15))
                tag = rng.getrandbits(36)
                target = "same_set_rewrite" if index in written else "new_set"
                await dta.write(index, mask, tag, target=target)
                written.add(index)
            else:
                port = rng.randrange(4)
                index = rng.randrange(SETS)
                await dta.read(port, index)
        for port in range(4):
            for index in (0, 7, 100, 255):
                await dta.read(port, index)
        await dta.read_every_set(2)


# DTA-FP-008
async def test_mbist_bypass_reaches_every_bank(dta):
    async with execution(dta):
        await dta.reset()
        payloads = {
            0x20: 0,
            0x21: ALTERNATING,
            0x22: ALTERNATING ^ ((1 << 86) - 1),
            0x23: (1 << 86) - 1,
            0x24: 0x123456789ABCDEF012345,
            0x25: 0x0FEDCBA9876543210FED,
            0x26: 1,
            0x27: 1 << 85,
        }
        for slot, array in enumerate(range(0x20, 0x28)):
            data = payloads[array]
            ack = await dta.mbist_write(array, 0x30 + slot, data)
            assert ack == 1, f"MBIST write array {array:#x} not acknowledged"
            got = await dta.mbist_read(array, 0x30 + slot)
            assert got == data, (array, hex(got), hex(data))
            # A row that was never written must read back zero.
            untouched = await dta.mbist_read(array, 0x70 + slot)
            assert untouched == 0, (array, hex(untouched))
        # Byte-mask semantics: only the selected 43-bit half of the row changes.
        low = codeword(0x011111111)
        high = codeword(0x022222222)
        await dta.mbist_write(0x20, 0x90, (high << 43) | low, be=0b01)
        got = await dta.mbist_read(0x20, 0x90)
        assert got == low, hex(got)
        await dta.mbist_write(0x20, 0x90, (high << 43) | low, be=0b10)
        got = await dta.mbist_read(0x20, 0x90)
        assert got == (high << 43) | low, hex(got)
        await dta.mbist_write(0x20, 0x90, 0, be=0b00)
        got = await dta.mbist_read(0x20, 0x90)
        assert got == (high << 43) | low, hex(got)
        # Broadcast (all SRAMs) write then per-bank read proves the spread path.
        broadcast = int("01" * 43, 2)
        ack = await dta.mbist_write(0x20, 0x60, broadcast, all_sram=True)
        assert ack == 1
        for array in range(0x20, 0x28):
            got = await dta.mbist_read(array, 0x60)
            assert got == broadcast, (array, hex(got))
        got = await dta.mbist_read(0x20, 0x60, all_sram=True)
        assert got == broadcast, hex(got)
        # Address bits: every bank's low/high rows and alternating patterns are
        # reachable, and the payload varies per bank to exercise the read mux.
        for array in range(0x20, 0x28):
            for addr in (0x000, 0x1FF, 0x0AA, 0x155, 0x0F0, 0x00F):
                data = ALTERNATING ^ ((addr & 0xFF) << 8) ^ ((array - 0x20) << 20)
                await dta.mbist_write(array, addr, data)
                assert await dta.mbist_read(array, addr) == data, (hex(array), hex(addr))
        # An array id outside the tag range selects no tag bank: the spread mux
        # keeps the previous selection's data, but no new bank is activated.
        previous = await dta.mbist_read(0x20, 0x00F)
        assert await dta.mbist_read(0x28, 0x00) == previous
        assert await dta.mbist_read(0x3F, 0x00) == previous
        assert await dta.mbist_read(0x20, 0x000) == ALTERNATING
        # Return the array-id bus to a low value so its upper bits toggle back.
        await dta.mbist_read(0x20, 0x000)
        # DFT-written raw row is visible through the functional read port:
        # bank 0 of array 0 holds ways 0/1 of set 0x50.
        low = codeword(0x012345678)
        high = codeword(0x0AAAA5555)
        await dta.mbist_write(0x20, 0x50, (high << 43) | low)
        words = await dta.read(0, 0x50, check=False)
        assert words == [low, high, 0, 0], [hex(w) for w in words]
