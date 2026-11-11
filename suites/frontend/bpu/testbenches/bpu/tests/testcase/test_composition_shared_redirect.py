"""One redirect must be compared against *both* predictor windows and empty both.

``BPU-ABTB-054`` and ``BPU-UTAGE-026`` prove each predictor flushes its own
window.  Neither proves the composition: that a single ``io.fromFtq.redirect``
reaches ABTB and MicroTAGE in the same cycle, that the independent checker
compares both windows on that cycle, and that both windows are actually empty on
the following cycle.

This case is a witness for exactly that, and nothing more.  It does not invent an
RTL expectation; it counts cycles where the redirect pulse is asserted **and**
both ``ahead`` and ``early_direction`` appear in the compared expectation, then
requires the next lossless cycle to report no live entry in either window.  A
zero count means the composition cell was never checked, however green the run
looks.
"""

from __future__ import annotations

import json

import pytest

from suites.frontend.bpu.testbenches.shared.env.artifacts import write_output
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT

PC = 0x40000000


def _live(window):
    return (window['ahead_meta_valid'] == 1
            or any(hit == 1 for hit in window['ahead_hits'] if hit is not None)
            or any(hit == 1 for hit in window['early_hits'] or ()))


@pytest.mark.feature("BPU-INT-108")
async def test_one_redirect_is_compared_against_both_predictor_windows(bpu_agent):
    witness = await bpu_agent.compare_early_composition(pc=PC, probe='shared-redirect')
    cycles, post = witness['cycles'], witness['post_redirect']
    assert cycles, ("no redirect cycle compared both predictor windows", witness['counts'])
    assert any(row['ahead_meta_valid'] == 1 for row in cycles), cycles
    assert any(any(hit == 1 for hit in row['ahead_hits']) for row in cycles), cycles
    assert post, ("no post-redirect cycle compared both predictor windows", cycles)
    live_before = [row for row in post
                   if _live(next(pre for pre in cycles if pre['tick'] == row['after']))]
    assert live_before, ("no post-redirect pair had a live pre-redirect window", post)
    for row in post:
        assert row['ahead_meta_valid'] == 0, row
        assert all(value == 0 for value in row['ahead_valids']), row
        assert all(value == 0 for value in row['early_valids']), row
        assert not any(hit == 1 for hit in row['early_hits'] or ()), row

    write_output(REPO_ROOT / "results" / "bpu" / "shared-redirect-witness.json",
                 json.dumps(dict(pc=hex(PC), cycles=cycles, post_redirect=post),
                            indent=2, sort_keys=True) + "\n")
