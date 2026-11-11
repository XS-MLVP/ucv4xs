"""Checker discrimination controls: a one-bit lie must be rejected."""

from __future__ import annotations

import pytest
from toffee.scoreboard import ScoreboardMismatch

from suites.frontend.instr_uncache.testbenches.instr_uncache.checker import check_outputs as check_top_outputs
from suites.frontend.instr_uncache.testbenches.instr_uncache.model import Outputs as TopOutputs


def _top(addr=0x3A00_0000, data=0):
    return TopOutputs(0, 1, addr, 0, 0, 0, data, 0, 0, 0, 1)


@pytest.mark.feature("INC-ENV-002")
def test_top_checker_rejects_need_resend_bit():
    expected = TopOutputs(0, 0, 0, 0, 0, 1, 0xCAFF, 0, 0, 1, 1)
    actual = TopOutputs(0, 0, 0, 0, 0, 1, 0xCAFF, 0, 0, 0, 1)
    with pytest.raises(ScoreboardMismatch):
        check_top_outputs(expected, actual, phase="discrimination")
