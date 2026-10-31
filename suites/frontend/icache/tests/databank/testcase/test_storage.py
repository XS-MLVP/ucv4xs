"""Storage semantics of ICacheDataBank."""

from __future__ import annotations

import pytest

from suites.frontend.icache.databank.model.bank import DataEntry


@pytest.mark.feature("ICACHE-DATABANK-002")
async def test_write_then_read_returns_the_same_entry(databank_agent):
    agent = databank_agent
    await agent.write(0x10, 0b0001, data=0x1122_3344_5566_7788, code=1)
    entries = await agent.check_read(0x10)
    assert entries[0] == DataEntry(0x1122_3344_5566_7788, 1)
    assert entries[1:] == (DataEntry(0, 0),) * 3, "unwritten ways stay zero"


@pytest.mark.feature("ICACHE-DATABANK-001")
async def test_waymask_selects_exactly_the_written_ways(databank_agent):
    agent = databank_agent
    await agent.write(0x20, 0b1111, data=0xAAAA, code=0)
    await agent.write(0x20, 0b0100, data=0x5555, code=1)
    entries = await agent.check_read(0x20)
    assert [entry.data for entry in entries] == [0xAAAA, 0xAAAA, 0x5555, 0xAAAA]
    assert [entry.code for entry in entries] == [0, 0, 1, 0]

    await agent.write(0x20, 0b1001, data=0x1234, code=1)
    entries = await agent.check_read(0x20)
    assert [entry.data for entry in entries] == [0x1234, 0xAAAA, 0x5555, 0x1234]


@pytest.mark.feature("ICACHE-DATABANK-003")
async def test_sets_are_independent(databank_agent):
    agent = databank_agent
    for set_index in range(0, 256, 17):
        await agent.write(set_index, 0b1111, data=0x1000 + set_index, code=set_index & 1)
    for set_index in range(0, 256, 17):
        entries = await agent.check_read(set_index)
        assert [entry.data for entry in entries] == [0x1000 + set_index] * 4
        assert [entry.code for entry in entries] == [set_index & 1] * 4


@pytest.mark.feature("ICACHE-DATABANK-004")
async def test_code_is_stored_verbatim(databank_agent):
    agent = databank_agent
    # A deliberately wrong parity code must read back unchanged: the bank is
    # storage, not a checker.
    await agent.write(0x30, 0b0010, data=0xDEAD_BEEF_0000_0001, code=1)
    entries = await agent.check_read(0x30)
    assert entries[1] == DataEntry(0xDEAD_BEEF_0000_0001, 1)
    await agent.write(0x30, 0b0010, data=0x0, code=0)
    entries = await agent.check_read(0x30)
    assert entries[1] == DataEntry(0x0, 0)


@pytest.mark.feature("ICACHE-DATABANK-005")
async def test_read_ready_drops_while_a_write_is_offered(databank_agent):
    agent = databank_agent
    await agent.write(0x40, 0b0001, data=0x1, code=0)
    agent.write_driver.set({
        "valid": 1, "setIdx": 0x41, "waymask": 0b0001, "data": 0x2, "code": 0,
    })
    try:
        await agent._edge()
        assert agent.read_ready() == 0, "a write in flight must block the read port"
        assert agent.write_ready() == 1
    finally:
        agent.write_driver.set({
            "valid": 0, "setIdx": 0, "waymask": 0, "data": 0, "code": 0,
        })
        await agent._edge()
    await agent.wait_for(lambda: agent.read_ready() == 1, what="read ready to return")


@pytest.mark.feature("ICACHE-DATABANK-007")
async def test_reset_restores_every_way_to_zero(databank_agent):
    """The macro reset sweep clears all four way arrays."""
    agent = databank_agent
    for set_index in range(0, agent.model.sets, 13):
        await agent.write(set_index, 0b1111,
                          data=0xABCD_0000 + set_index, code=1)
    await agent.reset()
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the reset sweep to finish")
    for set_index in range(0, agent.model.sets, 13):
        entries = await agent.read(set_index)
        assert entries == (DataEntry(0, 0),) * 4, (
            f"set {set_index} kept {entries} after reset")


@pytest.mark.feature("ICACHE-DATABANK-005")
async def test_write_in_the_read_response_cycle_does_not_corrupt_the_read(databank_agent):
    """The single port serves the accepted read even if a write follows it.

    The macro registers the read address and drives the response one cycle
    later; a write accepted on that edge only changes the address register for
    the cycle after it.  A design that let the write through one cycle earlier
    would silently return the refill word for an already-accepted read.
    """
    agent = databank_agent
    set_index = 0x70
    await agent.write(set_index, 0b1111, data=0x1111)

    agent.read_driver.set({"valid": 1, "setIdx": (set_index,) * 4,
                           "waymask": 0b1111})
    await agent.wait_for(lambda: agent.read_ready() == 1, what="read ready")
    await agent._edge()
    agent.read_driver.set({"valid": 0, "setIdx": (0,) * 4, "waymask": 0})
    await agent._edge()                  # the array samples the read
    agent.write_driver.set({"valid": 1, "setIdx": set_index,
                            "waymask": 0b1111, "data": 0x2222, "code": 0})
    during = agent.read_entries()
    assert all(entry.data == 0x1111 for entry in during), (
        f"a write in the response cycle replaced the accepted read: {during}")
    await agent._edge()                  # the write commits here
    agent.write_driver.set({"valid": 0, "setIdx": 0, "waymask": 0,
                            "data": 0, "code": 0})
    agent.model.write(set_index, 0b1111, DataEntry(0x2222, 0))
    await agent._edge()

    after = await agent.check_read(set_index)
    assert all(entry.data == 0x2222 for entry in after), (
        "the write did not take effect after the read")
