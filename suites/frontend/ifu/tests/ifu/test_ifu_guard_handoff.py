"""Interface-handoff probe: what the pinned baseline can and cannot convey.

Upstream commit ``b716aade`` ("fix(core): carry true PC guard bit", 2026-10-27)
is 57 commits ahead of the pinned baseline ``893e1580b`` and changes exactly
two truncations in ``Ifu.scala`` plus the width of ``FrontendRedirect.pc``.  It
exists because a redirect PC truncated to ``VAddrBits`` loses the guard bit of
a ``GuardedPc``, so the FTQ reconstructs a PC one bit short.

On this baseline the observation port itself is 50 bits wide, so the DUT
*cannot* express the corrected value: the probe records the exact truncation
rather than pretending the handoff was verified.  The hardware pass rate must
not include it; the residual is tracked in ``docs/upstream-review-20261029.md``
with the next action (baseline upgrade + re-run).
"""

from __future__ import annotations

import pytest

from suites.frontend.ifu.model.fetch import aligned_lanes
from suites.frontend.ifu.model.fetch import build_window
from suites.frontend.ifu.model.isa import jal
from suites.frontend.ifu.ifu.types import FetchRequest
from suites.frontend.ifu.uncache_unit.types import BusReply

GUARD_PC = (1 << 51) - 2  # GuardedPc with the guard bit set, low bits all ones
LOW_50 = (1 << 50) - 1


@pytest.mark.feature("IFU-ENV-005")
async def test_redirect_pc_drops_the_guard_bit_on_this_baseline(ifu_agent):
    # Port widths fix the contract before any stimulus: the request carries
    # GuardedPc[50:1] (bit 0 is implicit), the redirect PC carries VAddrBits.
    assert ifu_agent.interface.request_pc_bits == 51
    assert ifu_agent.interface.redirect_pc_bits == 50
    assert ifu_agent.interface.redirect_target_bits == 51
    assert (GUARD_PC >> 50) & 1 == 1

    window = build_window([(jal(1, 0x40), 0)], GUARD_PC, ftq0=(0, 1))
    result = await ifu_agent.fetch(FetchRequest(window))
    beat, redirect = result.beat, result.redirect
    assert beat is not None and redirect is not None
    # The instruction stream is unaffected; only the PC handoff is lossy.
    assert beat.instrs[0] == window.instructions[0].out_data
    assert redirect.pc == GUARD_PC & LOW_50
    assert redirect.pc != GUARD_PC  # the guard bit is absent by construction
    # The 51-bit target field still performs full GuardedPc arithmetic, so the
    # truncation is specific to pc, matching the upstream patch shape.
    _, prediction, *_ = aligned_lanes(window, 0)
    assert redirect.target == prediction.redirect.target


@pytest.mark.feature("IFU-ENV-005")
async def test_uncache_redirect_uses_the_same_truncated_pc_path(ifu_agent):
    window = build_window([(jal(1, 0x40), 0)], GUARD_PC, pbmt0=1)
    result = await ifu_agent.read_uncached(FetchRequest(window, physical_address=0x2000), BusReply(0x0001))
    beat, redirect = result.beat, result.redirect
    assert beat is not None
    assert redirect is not None
    assert redirect.pc == GUARD_PC & LOW_50
    assert redirect.pc != GUARD_PC
