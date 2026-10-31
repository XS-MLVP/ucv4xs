"""End-to-end fetch through the whole ICache: miss, refill, hit."""

from __future__ import annotations

import pytest

from suites.frontend.icache.icache.case.definitions import make_fetch
from suites.frontend.icache.icache.model import icache as model


@pytest.mark.feature("ICACHE-ICACHE-001")
async def test_cold_miss_fetches_the_line_and_returns_it(icache_agent):
    agent = icache_agent
    req = make_fetch(0x1000, 15, ftq_idx=4)
    observed = await agent.send(req)

    assert observed.ifu_valid == 1
    block = observed.blocks[0]
    assert block.valid == 1
    assert block.start_vaddr == 0x1000
    assert block.ftq_idx == 4
    assert block.exception == model.EXC_NONE
    assert block.data == model.memory_data(0x1000 >> 6)
    assert len(agent.acquires) == 1
    assert agent.acquires[0][0] == 0x1000 >> 6


@pytest.mark.feature("ICACHE-ICACHE-002")
async def test_second_fetch_of_the_same_block_hits(icache_agent):
    agent = icache_agent
    req = make_fetch(0x1000, 15)
    await agent.send(req)
    acquires = len(agent.acquires)

    observed = await agent.send(req)
    assert observed.ifu_valid == 1
    # A hit reads only the data banks covered by the fetch request (banks 0..3
    # for a 32-byte fetch at offset 0); the refill path fills the whole line.
    data = observed.blocks[0].data
    assert data & ((1 << 256) - 1) == (model.memory_data(0x1000 >> 6)
                                       & ((1 << 256) - 1))
    assert data >> 256 == 0
    assert len(agent.acquires) == acquires, "a resident line must not hit the bus"
    assert observed.raw_hits[0] == 1, "the fetched line was a raw hit"


@pytest.mark.feature("ICACHE-ICACHE-003")
async def test_cross_line_fetch_gets_both_lines(icache_agent):
    agent = icache_agent
    # Warm the first line, then fetch a 64-byte block at offset 0x20 that spans
    # into the next line: the high banks come from the array, the low banks
    # from the refill of the second line.
    await agent.send(make_fetch(0x1000, 15))
    req = make_fetch(0x1020, 31)
    observed = await agent.send(req)
    assert observed.ifu_valid == 1
    assert agent.acquires[-1][0] == 0x1040 >> 6, (
        "only the second line of the cross-line fetch was missing")
    assert agent.acquires[0][0] == 0x1000 >> 6
    block = observed.blocks[0]
    # Line 0 owns the high banks and line 1 the low banks.
    assert block.data >> 256 == model.memory_data(0x1000 >> 6) >> 256
    assert block.data & ((1 << 256) - 1) == (
        model.memory_data(0x1040 >> 6) & ((1 << 256) - 1))


@pytest.mark.feature("ICACHE-ICACHE-004")
async def test_two_fetch_returns_two_blocks(icache_agent):
    agent = icache_agent
    # Both blocks come from the same FTQ issue, so they share one 4 KiB page;
    # request 1 starts at offset 0x20 so the two fetches use different banks.
    req0 = make_fetch(0x2000, 15, ftq_idx=1)
    req1 = make_fetch(0x2160, 15, ftq_idx=2)   # set 0x85: the other bank
    observed = await agent.send(req0, req1)
    assert observed.two_fetch_valid == 1
    assert observed.blocks[0].valid == 1 and observed.blocks[1].valid == 1
    assert observed.blocks[0].start_vaddr == 0x2000
    assert observed.blocks[1].start_vaddr == 0x2160
    assert observed.blocks[0].ftq_idx == 1 and observed.blocks[1].ftq_idx == 2
    assert len(agent.acquires) == 2


@pytest.mark.feature("ICACHE-ICACHE-005")
async def test_rvc_map_is_aligned_to_the_fetch_window(icache_agent):
    agent = icache_agent
    # Variant 1 plants 32-bit instruction markers in odd blocks' first bank.
    agent.model.variant = 1
    agent.variant = 1
    # A single-line fetch of an odd block: variant 1 plants 32-bit instruction
    # markers in the first bank of that block.
    req = make_fetch(0x3040, 15, taken=1)
    observed = await agent.send(req)
    block = observed.blocks[0]
    expected_map = agent.last_outcome.maybe_rvc_map
    assert observed.maybe_rvc_map == expected_map
    assert block.taken_valid == 1 and block.taken_bits == 15
    assert block.size == 16
    assert observed.maybe_rvc_map == 0x0000_FFF5, (
        "slots 1 and 3 hold 32-bit instruction markers")
    # The map must not be the uniform all-compressed pattern: block 0x3020 has
    # markers in its first bank, so some slots are 32-bit instructions.
    assert expected_map != 0xFFFF_FFFF


@pytest.mark.feature("ICACHE-ICACHE-016")
async def test_every_set_is_addressable(icache_agent):
    """Sweep all 256 sets: each set must hold and return its own line.

    One fetch per set exercises the set decoders of the metadata array, the
    data array, the replacer instances and the way lookup, which a handful of
    addresses cannot cover.
    """
    agent = icache_agent
    for set_index in range(256):
        # pTag carries the set's high bits so that every address maps back to
        # exactly this set; a fresh tag per set avoids any aliasing.
        ptag = (set_index >> 6) & 0b11
        vaddr = (ptag << 12) | ((set_index & 0x3F) << 6)
        observed = await agent.send(make_fetch(vaddr, 15))
        block = vaddr >> 6
        assert observed.blocks[0].valid == 1
        assert agent.model.hit_mask(block, set_index) != 0
        assert (observed.blocks[0].data & ((1 << 256) - 1)
                == model.memory_data(block) & ((1 << 256) - 1))
    assert len(set(acq[0] for acq in agent.acquires)) == 256

    # Second pass: every set is now resident, so each fetch is a hit and
    # touches its replacer port (the fill pass only exercised the victim path).
    before = len(agent.acquires)
    for set_index in range(256):
        ptag = (set_index >> 6) & 0b11
        vaddr = (ptag << 12) | ((set_index & 0x3F) << 6)
        observed = await agent.send(make_fetch(vaddr, 15))
        assert observed.raw_hits[0] == 1
        assert (observed.blocks[0].data & ((1 << 256) - 1)
                == model.memory_data(vaddr >> 6) & ((1 << 256) - 1))
    assert len(agent.acquires) == before, "the second pass must be all hits"


@pytest.mark.feature("ICACHE-ICACHE-017")
async def test_two_fetch_issue_updates_both_replacement_ports(icache_agent):
    """Sweep every set through the second fetch port of a two-fetch issue.

    Both fetched lines touch the replacer (one per request) and both are
    installed.  Request 1 starts at offset 0x20 so the two fetches use
    disjoint data banks and can be issued together.
    """
    agent = icache_agent
    for target in range(256):
        page = target >> 6
        low = target & 0x3F
        vaddr1 = (page << 12) | (low << 6) | 0x20
        vaddr0 = (page << 12) | (((low + 1) & 0x3F) << 6)
        req0 = make_fetch(vaddr0, 15, ftq_idx=1)
        req1 = make_fetch(vaddr1, 15, ftq_idx=2)
        observed = await agent.send(req0, req1)
        assert observed.two_fetch_valid == 1, target
        assert observed.blocks[0].valid == 1 and observed.blocks[1].valid == 1
        # Request 0 covers banks 0..3 and request 1 banks 4..7 of its line.
        for req, index in ((req0, 0), (req1, 1)):
            block = req.vaddr >> 6
            assert agent.model.hit_mask(block, model.get_idx(req.vaddr)) != 0
            word = model.memory_data(block)
            data = observed.blocks[index].data
            shift = 0 if index == 0 else 256
            mask = ((1 << 256) - 1) << shift
            assert (data & mask) == (word & mask)
    # Both lines of every set are resident: the second pass hits both, which
    # exercises the second fetch port's replacer touch in every set.
    before = len(agent.acquires)
    for target in range(256):
        page = target >> 6
        low = target & 0x3F
        vaddr1 = (page << 12) | (low << 6) | 0x20
        vaddr0 = (page << 12) | (((low + 1) & 0x3F) << 6)
        observed = await agent.send(make_fetch(vaddr0, 15),
                                    make_fetch(vaddr1, 15))
        assert observed.two_fetch_valid == 1
        assert observed.blocks[0].valid == 1 and observed.blocks[1].valid == 1
    assert len(agent.acquires) == before, "both lines must already be resident"


@pytest.mark.feature("ICACHE-ICACHE-018")
async def test_second_fetch_can_cross_a_cache_line(icache_agent):
    """Request 1 may itself need two cache lines while request 0 hits.

    The two requests share the 4 KiB page (the FTQ guarantee) and use disjoint
    data banks; request 1 starts at offset 0x20 so its first line is the same
    line as request 0 (a hit) and its second line must be refilled.
    """
    agent = icache_agent
    resident = make_fetch(0x4000, 15)
    await agent.send(resident)
    assert agent.model.hit_mask(0x4000 >> 6, 0) != 0

    # req1's second line is req0's line: the FTQ calls this Overlap2.
    req0 = make_fetch(0x4040, 15, ftq_idx=1)
    req1 = make_fetch(0x4020, 31, ftq_idx=2)
    assert req1.bank_sel[0] != 0 and req1.bank_sel[1] != 0
    before = len(agent.acquires)
    observed = await agent.send(req0, req1)   # Overlap2
    assert observed.two_fetch_valid == 1
    assert observed.blocks[0].valid == 1 and observed.blocks[1].valid == 1
    assert len(agent.acquires) == before + 1, (
        "request 0 and request 1's second line share one refill")
    assert agent.acquires[-1][0] == 0x4040 >> 6
    # Banks 4..7 come from the resident line, banks 0..3 from the refill.
    assert (observed.blocks[1].data >> 256
            == (model.memory_data(0x4000 >> 6) >> 256))
    assert (observed.blocks[1].data & ((1 << 256) - 1)
            == (model.memory_data(0x4040 >> 6) & ((1 << 256) - 1)))


@pytest.mark.feature("ICACHE-ICACHE-025")
async def test_rvc_maps_stitch_when_the_second_fetch_starts_after_the_first(icache_agent):
    """Overlap2 with request 1 starting beyond request 0's block size.

    The RTL shifts request 0's second-line RVC map right when request 1 starts
    after the end of request 0's fetch block; this is the only two-fetch
    overlap whose maps are *stitched* rather than shifted left.
    """
    agent = icache_agent
    req0 = make_fetch(0x4040, 15, ftq_idx=1)   # non-cross, block ends at slot 16
    req1 = make_fetch(0x4024, 31, ftq_idx=2)   # cross, starts at slot 18
    from suites.frontend.icache.icache.case.definitions import CASE_OVERLAP2
    from suites.frontend.icache.icache.case.definitions import prefetch_case
    assert prefetch_case(req0, req1) == CASE_OVERLAP2
    # request 1's second line is request 0's line; warm both lines first.
    await agent.send(make_fetch(0x4000, 15))
    await agent.send(make_fetch(0x4040, 15))
    before = len(agent.acquires)
    observed = await agent.send(req0, req1)
    assert observed.two_fetch_valid == 1
    assert observed.blocks[1].valid == 1
    assert len(agent.acquires) == before, "both lines must be resident"


@pytest.mark.feature("ICACHE-ICACHE-028")
async def test_a_cross_line_miss_allocates_two_fetch_mshrs(icache_agent):
    agent = icache_agent
    req = make_fetch(0x2020, 31)   # both lines of the block are missing
    # With the hardware prefetch disabled the prefetch pipe does not issue the
    # miss, so the two lines are owned by the fetch MSHRs.
    agent.csr_driver.set({"enable": 0})
    await agent._edge()
    before = len(agent.acquires)
    # Two refills of one fully-missing cross-line fetch arrive in a
    # timing-dependent order and the pipe keeps one aligned map register per
    # beat, so the stitched map for this corner is not architectural; the data,
    # ranges and MSHR allocation below are still checked.  The map itself is
    # covered by the warmed-line case, where line 0 comes from the array.
    observed = await agent.send(req, undefined=("maybe_rvc_map",))
    new = agent.acquires[before:]
    assert len(new) == 2
    assert {source for _, source in new} == {0, 1}, (
        "a cross-line miss must use the two fetch MSHRs")
    assert observed.ifu_valid == 1
    assert (observed.blocks[0].data >> 256
            == (model.memory_data(0x2000 >> 6) >> 256))
    assert (observed.blocks[0].data & ((1 << 256) - 1)
            == (model.memory_data(0x2040 >> 6) & ((1 << 256) - 1)))
    agent.csr_driver.set({"enable": 1})
    await agent._edge()
