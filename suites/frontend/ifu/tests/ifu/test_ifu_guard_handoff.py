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

from suites.frontend.ifu.legacy_pins import P
from suites.frontend.ifu.case_loader import load_case_module
from suites.frontend.ifu.model.fetch import LANES
from suites.frontend.ifu.model.fetch import aligned_lanes
from suites.frontend.ifu.model.fetch import build_window
from suites.frontend.ifu.model.isa import jal

GUARD_PC = (1 << 51) - 2  # GuardedPc with the guard bit set, low bits all ones
LOW_50 = (1 << 50) - 1


@pytest.mark.feature("IFU-ENV-005")
def test_redirect_pc_drops_the_guard_bit_on_this_baseline(ifu):
    cases = load_case_module("tests/ifu/test_ifu_fetch.py", "cases_guard_handoff")
    # Port widths fix the contract before any stimulus: the request carries
    # GuardedPc[50:1] (bit 0 is implicit), the redirect PC carries VAddrBits.
    assert ifu.port_width(P.p_fromICache_req_bits_info_0_startVAddr_addr) == 50
    assert ifu.port_width(P.p_toFtq_wbRedirect_bits_pc) == 50
    assert ifu.port_width(P.p_toFtq_wbRedirect_bits_target) == 51
    assert (GUARD_PC >> 50) & 1 == 1

    ifu.reset()
    window = build_window([(jal(1, 0x40), 0)], GUARD_PC, ftq0=(0, 1))
    beat, redirect = cases.fetch(ifu, window)
    assert beat is not None and redirect is not None
    # The instruction stream is unaffected; only the PC handoff is lossy.
    assert beat["instrs"][0] == window.instructions[0].out_data
    assert redirect["pc"] == GUARD_PC & LOW_50
    assert redirect["pc"] != GUARD_PC  # the guard bit is absent by construction
    # The 51-bit target field still performs full GuardedPc arithmetic, so the
    # truncation is specific to pc, matching the upstream patch shape.
    _, prediction, *_ = aligned_lanes(window, 0)
    assert redirect["target"] == prediction.redirect.target


@pytest.mark.feature("IFU-ENV-005")
def test_uncache_redirect_uses_the_same_truncated_pc_path(ifu):
    cases = load_case_module("tests/ifu/test_ifu_fetch.py", "cases_guard_uncache")
    ifu.reset()
    window = build_window([(jal(1, 0x40), 0)], GUARD_PC, pbmt0=1, paddr0=0x1000)
    cases.uncache_accept_and_send(ifu, window)
    ifu.set(io_fromUncache_resp_valid=1, io_fromUncache_resp_bits_data=0x0001,
            io_fromUncache_resp_bits_corrupt=0, io_fromUncache_resp_bits_denied=0,
            io_fromUncache_resp_bits_needResend=0)
    ifu.step(1)
    ifu.set(io_fromUncache_resp_valid=0)
    beat, redirect = cases.uncache_collect(ifu)
    assert beat is not None
    assert redirect is not None
    assert redirect["pc"] == GUARD_PC & LOW_50
    assert redirect["pc"] != GUARD_PC
