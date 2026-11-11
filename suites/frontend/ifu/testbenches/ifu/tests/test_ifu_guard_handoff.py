"""Interface-handoff probe: does the pinned baseline convey the full GuardedPc?

On baseline ``893e1580b`` the IFU redirect PC port was 50 bits wide, so a
guarded (overflow) PC could not be handed to the FTQ.  Upstream commit
``b716aade`` ("fix(core): carry true PC guard bit") removed the two
truncations in ``Ifu.scala`` and widened ``FrontendRedirect.pc`` to
``GuardedVAddrBits``.  The current pinned baseline ``a0c2a26cb`` contains that
fix, so both probes below are now positive controls for the corrected handoff.

The four probes below are positive controls for the corrected handoff.  The two
original function names are kept unchanged on purpose: the node ID is the
accounting unit against the previous baseline, where these probes recorded the
truncation and PASSed.  Renaming them would hide a contract flip behind a
"deleted + added" pair; the assertions and the docstring carry the new meaning.
"""

from __future__ import annotations

import pytest

from suites.frontend.ifu.testbenches.ifu.model.cenc import c_addi
from suites.frontend.ifu.testbenches.ifu.model.fetch import aligned_lanes
from suites.frontend.ifu.testbenches.ifu.model.fetch import build_window
from suites.frontend.ifu.testbenches.ifu.model.isa import jal
from suites.frontend.ifu.testbenches.ifu.transactions import FetchRequest
from suites.frontend.ifu.testbenches.uncache_unit.transactions import BusReply

GUARD_PC = (1 << 51) - 2  # GuardedPc with the guard bit set, low bits all ones
LOW_50 = (1 << 50) - 1


@pytest.mark.feature("IFU-ENV-005")
async def test_redirect_pc_drops_the_guard_bit_on_this_baseline(ifu_agent):
    # Port widths fix the contract before any stimulus: the request carries
    # GuardedPc[50:1] (bit 0 is implicit); the redirect PC now carries the
    # full 51-bit GuardedPc, matching the internal FrontendRedirect bundle.
    assert ifu_agent.interface.request_pc_bits == 51
    assert ifu_agent.interface.redirect_pc_bits == 51
    assert ifu_agent.interface.redirect_target_bits == 51
    assert (GUARD_PC >> 50) & 1 == 1

    window = build_window([(jal(1, 0x40), 0)], GUARD_PC, ftq0=(0, 1))
    result = await ifu_agent.fetch(FetchRequest(window))
    beat, redirect = result.beat, result.redirect
    assert beat is not None and redirect is not None
    # The instruction stream is unaffected; the PC handoff keeps the guard bit.
    assert beat.instrs[0] == window.instructions[0].out_data
    assert redirect.pc == GUARD_PC
    assert redirect.pc != GUARD_PC & LOW_50  # the guard bit is present
    # The 51-bit target field performs the same full GuardedPc arithmetic.
    _, prediction, *_ = aligned_lanes(window, 0)
    assert redirect.target == prediction.redirect.target


@pytest.mark.feature("IFU-ENV-005")
async def test_uncache_redirect_uses_the_same_truncated_pc_path(ifu_agent):
    window = build_window([(jal(1, 0x40), 0)], GUARD_PC, pbmt0=1)
    result = await ifu_agent.read_uncached(FetchRequest(window, physical_address=0x2000), BusReply(0x0001))
    beat, redirect = result.beat, result.redirect
    assert beat is not None
    assert redirect is not None
    # The uncache redirect path was the second truncation removed upstream.
    assert redirect.pc == GUARD_PC
    assert redirect.pc != GUARD_PC & LOW_50


@pytest.mark.feature("IFU-ENV-005")
async def test_second_block_redirect_keeps_the_guard_bit(ifu_agent):
    """The block-select arm of the redirect PC mux must preserve the guard bit.

    A fault in the second fetch block redirects to that block's own start PC,
    which is the other input of the ``select`` mux; carrying the guard bit there
    is a separate obligation from the first-block path.
    """

    base = (1 << 50) | 0x43000  # guard bit set for both block start PCs
    program = [(c_addi(8 + (index % 8), 1), 1) for index in range(8)]
    program[5] = (0x000080E7, 0)  # jalr x1, 0(x1) in the second block
    window = build_window(program, base, split=4, ftq0=(0, 13), ftq1=(0, 14))
    result = await ifu_agent.fetch(FetchRequest(window))
    assert result.beat is not None and result.redirect is not None
    assert result.redirect.ftq == (0, 14)  # owning block
    assert result.redirect.pc == base + 2 * 4
    assert result.redirect.pc >> 50 & 1 == 1


@pytest.mark.feature("IFU-ENV-005")
async def test_guard_bit_distinguishes_two_pcs_with_equal_low_bits(ifu_agent):
    """Discriminating control: two guarded PCs that differ only in bit 50.

    A 50-bit observation port would collapse them into one value, so this pair
    fails if the guard bit is dropped anywhere between the fetch PC and the
    redirect port. The expectation is the architectural address identity, not a
    copy of the DUT's own arithmetic.
    """

    plain = 0x43000
    guarded = (1 << 50) | plain
    observed = []
    for pc in (plain, guarded):
        window = build_window([(jal(1, 0x40), 0)], pc, ftq0=(0, 3))
        result = await ifu_agent.fetch(FetchRequest(window))
        assert result.beat is not None and result.redirect is not None
        observed.append(result.redirect.pc)
    assert observed[0] == plain
    assert observed[1] == guarded
    assert observed[0] & LOW_50 == observed[1] & LOW_50  # only bit 50 differs
    assert observed[0] != observed[1]
