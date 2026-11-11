"""InstrUncache response arbiter checker discrimination controls."""

from __future__ import annotations

import pytest
from toffee.scoreboard import ScoreboardMismatch

from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.checker import check_outputs as check_arbiter_outputs
from suites.frontend.instr_uncache.testbenches.instr_uncache_resp_arbiter.model import Outputs as ArbiterOutputs


@pytest.mark.feature("INC-ENV-002")
def test_arbiter_checker_rejects_corrupt_bit():
    expected = ArbiterOutputs(1, 0xDEAD_BEEF, 1, 0, 0)
    actual = ArbiterOutputs(1, 0xDEAD_BEEF, 0, 0, 0)
    with pytest.raises(ScoreboardMismatch):
        check_arbiter_outputs(expected, actual)
