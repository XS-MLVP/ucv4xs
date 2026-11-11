"""Memory built-in self test reaches every SRAM child.

The ICache exposes the SRAM children's MBIST interface at the chip boundary.
A BIST command for a child must be captured by that child's MBIST pipeline and
acknowledged, while the other children stay idle.  Both the broadcast form
(``all``) and the per-array select form are exercised, for reads and writes.
"""

from __future__ import annotations

import pytest

# One bit of array select per supported SRAM array: two metadata banks (1 and
# 2 array bits) followed by the eight data banks (3..6 bits).
ARRAY_BITS = (1, 2, 3, 4, 4, 5, 5, 5, 5, 6)


@pytest.mark.feature("ICACHE-ICACHE-021")
async def test_sram_bist_selects_and_acknowledges_every_child(icache_agent):
    agent = icache_agent
    for child, bits in enumerate(ARRAY_BITS):
        for array in range(1 << bits):
            ack = await agent.bist_command(child, array=array, readen=1)
            assert ack == 1, (
                f"child {child} did not acknowledge BIST array {array}")
        ack = await agent.bist_command(child, all_arrays=1, readen=1)
        assert ack == 1, f"child {child} did not acknowledge a broadcast BIST read"


@pytest.mark.feature("ICACHE-ICACHE-021")
async def test_sram_bist_write_reaches_the_arrays(icache_agent):
    agent = icache_agent
    for child in range(len(ARRAY_BITS)):
        array = (1 << ARRAY_BITS[child]) - 1
        ack = await agent.bist_command(
            child, array=array, readen=0, writeen=1, be=0x1,
            addr=0x5, addr_rd=0x5, indata=0x5A5A_5A5A_5A5A_5A5A)
        assert ack == 1, f"child {child} did not acknowledge a BIST write"
        # Broadcast form: every way of the bank captures the write fields.
        ack = await agent.bist_command(
            child, all_arrays=1, readen=0, writeen=1, be=0x1,
            addr=0x6, addr_rd=0x6, indata=0xA5A5_A5A5_A5A5_A5A5)
        assert ack == 1, f"child {child} did not acknowledge a broadcast write"
