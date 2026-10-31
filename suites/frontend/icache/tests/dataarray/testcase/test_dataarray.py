"""Data-array routing and storage semantics.

Bank masks here follow the real geometry: a 64-byte line is spread over eight
8-byte banks, so a 32-byte fetch block covers four consecutive banks.
"""

from __future__ import annotations

import pytest

from suites.frontend.icache.dataarray.model.array import DataEntry
from suites.frontend.icache.dataarray.model.array import LineSelect
from suites.frontend.icache.dataarray.model.array import ReadRequest

LOW_BANKS = 0b0000_1111     # first 32 bytes of a line
HIGH_BANKS = 0b1111_0000    # second 32 bytes


def entries(pattern: int, code: int = 0) -> tuple[DataEntry, ...]:
    """One distinct entry per bank, so a bank swap is immediately visible."""
    return tuple(DataEntry(pattern + bank, code) for bank in range(8))


def line(bank_mask: int, set_index: int, way: int) -> LineSelect:
    return LineSelect(bank_mask=bank_mask, set_index=set_index, waymask=1 << way)


@pytest.mark.feature("ICACHE-DATAARRAY-001")
async def test_each_bank_keeps_its_own_entry(dataarray_agent):
    agent = dataarray_agent
    await agent.write(0x10, 0b0001, entries(0x1000))
    resp = (await agent.check_read(
        ReadRequest((line(LOW_BANKS, 0x10, 0),))))[0]
    assert [entry.data for entry in resp[:4]] == [0x1000, 0x1001, 0x1002, 0x1003]


@pytest.mark.feature("ICACHE-DATAARRAY-005")
async def test_uncovered_banks_read_as_zero(dataarray_agent):
    agent = dataarray_agent
    await agent.write(0x11, 0b0001, entries(0x2000))
    resp = (await agent.check_read(
        ReadRequest((line(LOW_BANKS, 0x11, 0),))))[0]
    assert resp[4:] == (DataEntry(0, 0),) * 4, "banks outside the mask must read zero"


@pytest.mark.feature("ICACHE-DATAARRAY-002")
async def test_waymask_selects_the_requested_way(dataarray_agent):
    agent = dataarray_agent
    for way in range(4):
        await agent.write(0x20, 1 << way, entries(0x3000 + way * 0x100, code=way & 1))
    for way in range(4):
        resp = (await agent.check_read(
            ReadRequest((line(LOW_BANKS, 0x20, way),))))[0]
        assert [entry.data for entry in resp[:4]] == [
            0x3000 + way * 0x100 + bank for bank in range(4)]
        assert all(entry.code == (way & 1) for entry in resp[:4])


@pytest.mark.feature("ICACHE-DATAARRAY-003")
async def test_one_request_reads_both_halves_of_a_line(dataarray_agent):
    agent = dataarray_agent
    await agent.write(0x30, 0b0001, entries(0x4000))
    await agent.write(0x31, 0b0001, entries(0x4100))
    resp = (await agent.check_read(ReadRequest((
        line(LOW_BANKS, 0x30, 0),
        line(HIGH_BANKS, 0x31, 0),
    ))))[0]
    assert [entry.data for entry in resp[:4]] == [0x4000, 0x4001, 0x4002, 0x4003]
    assert [entry.data for entry in resp[4:]] == [0x4104, 0x4105, 0x4106, 0x4107]


@pytest.mark.feature("ICACHE-DATAARRAY-004")
async def test_two_requests_on_disjoint_bank_groups(dataarray_agent):
    agent = dataarray_agent
    await agent.write(0x40, 0b0010, entries(0x5000))
    await agent.write(0x41, 0b0100, entries(0x6000))
    both = await agent.check_read(
        ReadRequest((line(LOW_BANKS, 0x40, 1),)),
        ReadRequest((line(HIGH_BANKS, 0x41, 2),)),
    )
    assert [entry.data for entry in both[0][:4]] == [
        0x5000 + bank for bank in range(4)]
    assert [entry.data for entry in both[1][4:]] == [
        0x6000 + bank for bank in range(4, 8)]
    assert both[0][4:] == (DataEntry(0, 0),) * 4
    assert both[1][:4] == (DataEntry(0, 0),) * 4


@pytest.mark.feature("ICACHE-DATAARRAY-004")
async def test_two_requests_read_different_ways_of_the_same_bank(dataarray_agent):
    agent = dataarray_agent
    await agent.write(0x50, 0b0011, entries(0x7000))
    await agent.write(0x50, 0b1100, entries(0x8000))
    # Both requests touch bank 2 but different ways, which the array supports.
    both = await agent.check_read(
        ReadRequest((LineSelect(bank_mask=0b0000_0100, set_index=0x50, waymask=0b0001),)),
        ReadRequest((LineSelect(bank_mask=0b0000_0100, set_index=0x50, waymask=0b0100),)),
    )
    assert both[0][2] == DataEntry(0x7002, 0)
    assert both[1][2] == DataEntry(0x8002, 0)


@pytest.mark.feature("ICACHE-DATAARRAY-006")
async def test_sets_are_independent_on_every_bank(dataarray_agent):
    agent = dataarray_agent
    for set_index in (0, 1, 0x7F, 0xFF):
        await agent.write(set_index, 0b1111, entries(0x9000 + set_index))
    for set_index in (0, 1, 0x7F, 0xFF):
        resp = (await agent.check_read(
            ReadRequest((line(0b1111_1111, set_index, 3),))))[0]
        assert [entry.data for entry in resp] == [
            0x9000 + set_index + bank for bank in range(8)]


@pytest.mark.feature("ICACHE-DATAARRAY-007")
async def test_read_ready_drops_while_a_write_is_offered(dataarray_agent):
    agent = dataarray_agent
    await agent.write(0x60, 0b0001, entries(0xA000))
    agent.start_write(0x61, 0b0001)
    try:
        await agent._edge()
        assert agent.read_ready() == 0, "a write in flight must block the read port"
    finally:
        agent.stop_write()
        await agent._edge()
    await agent.wait_for(lambda: agent.read_ready() == 1, what="read ready to return")


@pytest.mark.feature("ICACHE-DATAARRAY-008")
async def test_every_request_slot_bank_and_way_is_reachable(dataarray_agent):
    """Sweep the full (request slot, bank, way) matrix.

    The router builds one selection term per bank and per way, and request slot 1
    has its own copy. A missed term would silently return zero for that
    combination, so every one of them is read at least once.
    """
    agent = dataarray_agent
    sets = {way: 0x80 + way for way in range(4)}
    for way in range(4):
        await agent.write(sets[way], 1 << way, entries(0xB000 + way * 0x100))

    all_banks = 0b1111_1111
    for way in range(4):
        # Request slot 0 over every bank.
        resp = (await agent.check_read(
            ReadRequest((line(all_banks, sets[way], way),))))[0]
        assert [entry.data for entry in resp] == [
            0xB000 + way * 0x100 + bank for bank in range(8)]

        # Request slot 1 over every bank, with slot 0 on the opposite half.
        low = (await agent.check_read(
            ReadRequest((line(HIGH_BANKS, sets[way], way),)),
            ReadRequest((line(LOW_BANKS, sets[way], way),)),
        ))
        assert [entry.data for entry in low[1][:4]] == [
            0xB000 + way * 0x100 + bank for bank in range(4)]
        assert [entry.data for entry in low[0][4:]] == [
            0xB000 + way * 0x100 + bank for bank in range(4, 8)]


@pytest.mark.feature("ICACHE-DATAARRAY-003")
async def test_second_line_can_select_low_banks(dataarray_agent):
    """The second line of a request has its own bank mask, including banks 0-3.

    The earlier two-line case used high banks for the second line; a second
    line that covers only the low banks exercises the low half of ``bankSel_1``.
    """
    agent = dataarray_agent
    await agent.write(0x50, 0b0001, entries(0x7000))
    await agent.write(0x51, 0b0010, entries(0x8000))
    response = (await agent.check_read(ReadRequest((
        line(HIGH_BANKS, 0x50, 0),
        line(LOW_BANKS, 0x51, 1),
    ))))[0]
    assert [entry.data for entry in response[4:]] == [
        0x7000 + bank for bank in range(4, 8)]
    assert [entry.data for entry in response[:4]] == [
        0x8000 + bank for bank in range(4)]


@pytest.mark.feature("ICACHE-DATAARRAY-004")
async def test_both_requests_can_each_read_two_lines(dataarray_agent):
    """Request 1's second line has its own bank mask and set index.

    The four lines of the two requests must use disjoint banks (one read port
    per bank), so single-bank masks keep the test legal while still driving the
    second request's second-line fields.
    """
    agent = dataarray_agent
    await agent.write(0x60, 0b0001, entries(0x9000))
    await agent.write(0x61, 0b0001, entries(0x9100))
    await agent.write(0x62, 0b0001, entries(0x9200))
    first = ReadRequest((line(0x01, 0x60, 0),))
    second = ReadRequest((line(0x02, 0x61, 0), line(0x04, 0x62, 0)))
    both = await agent.check_read(first, second)
    assert both[0][0].data == 0x9000
    assert both[1][1].data == 0x9101
    assert both[1][2].data == 0x9202


@pytest.mark.feature("ICACHE-DATAARRAY-003")
async def test_second_line_bank_mask_bit_by_bit(dataarray_agent):
    """Line 1 of a request selects each of the eight banks independently.

    The router must handle any bank on either line (the two lines inside one
    request use disjoint banks, and the two requests use disjoint banks again).
    """
    agent = dataarray_agent
    for set_index in (0x70, 0x71):
        await agent.write(set_index, 0b0001, entries(0xA000 + set_index))
    for bank in range(8):
        other = (bank + 1) % 8
        # Request 0 uses one bank for line 0, request 1 uses two banks: its
        # line 0 on `other` and its line 1 on `bank`.
        first = ReadRequest((line(1 << other, 0x70, 0),))
        second = ReadRequest((line(1 << other, 0x70, 0),
                              line(1 << bank, 0x71, 0)))
        both = await agent.check_read(first, second)
        assert both[1][bank].data == 0xA000 + 0x71 + bank
        assert both[1][other].data == 0xA000 + 0x70 + other


@pytest.mark.feature("ICACHE-DATAARRAY-010")
async def test_reset_restores_every_bank_to_zero(dataarray_agent):
    """The macro's power-on reset sweep clears all storage, not just validity.

    Every SRAM wrapper holds its own reset sweep; a partial sweep would leave
    stale instruction bytes behind a reset.  Write a distinctive pattern, assert
    reset, wait for the sweep to finish, and read every set back as zero.
    """
    agent = dataarray_agent
    for set_index in range(0, agent.model.sets, 17):
        await agent.write(set_index, 0b1111,
                          tuple(DataEntry(0xDEAD_0000 + set_index + bank, 1)
                                for bank in range(agent.model.banks)))
    await agent.reset()
    # The sweep finishes when the banks advertise write-ready again.
    await agent.wait_for(lambda: agent.write_ready() == 1,
                         what="the reset sweep to finish")
    for set_index in range(0, agent.model.sets, 17):
        for way in range(agent.model.ways):
            request = ReadRequest(lines=(
                LineSelect(bank_mask=0xFF, set_index=set_index,
                           waymask=1 << way),))
            values = await agent.read(request)
            for bank in range(agent.model.banks):
                assert values[0][bank] == DataEntry(0, 0), (
                    f"set {set_index} way {way} bank {bank} kept "
                    f"{values[0][bank]} after reset")


@pytest.mark.feature("ICACHE-DATAARRAY-011")
async def test_write_in_the_read_response_cycle_does_not_corrupt_the_read(dataarray_agent):
    """A refill landing in the response cycle must not replace the read data.

    The array macro registers the read address and drives the response
    combinationally one cycle later; a write accepted on that edge updates the
    address register for the cycle after it.  The accepted read must still
    return its original word, and the write must land afterwards.
    """
    agent = dataarray_agent
    set_index = 0x70
    old, new = entries(0x1111), entries(0x2222)
    await agent.write(set_index, 0b0001, old)

    request = ReadRequest((line(0b1111_1111, set_index, 0),))
    agent.read_driver.set(agent._encode_read((request,)))
    await agent.wait_for(lambda: agent.read_ready() == 1, what="read ready")
    await agent._edge()                 # commit the request level
    agent.read_driver.set(agent._encode_read(()))
    await agent._edge()                 # the array samples it, response is valid now
    # The response is presented in this cycle; offer a refill write to the very
    # same set and way so a leak would be visible in the data.
    agent.write_driver.set({
        "valid": 1, "setIdx": set_index, "waymask": 0b0001,
        "entries": tuple({"data": e.data, "code": e.code} for e in new),
    })
    during = agent.responses()[0]
    assert during == old, (
        f"a write in the response cycle replaced the accepted read: {during}")
    await agent._edge()                 # the write commits here
    agent.write_driver.set({
        "valid": 0, "setIdx": 0, "waymask": 0,
        "entries": tuple({"data": 0, "code": 0} for _ in range(agent.model.banks)),
    })
    agent.model.write(set_index, 0b0001, new)
    await agent._edge()

    after = (await agent.check_read(request))[0]
    assert after == new, "the refill write did not take effect after the read"
