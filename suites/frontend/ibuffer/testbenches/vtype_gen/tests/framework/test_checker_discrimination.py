"""VTypeGen checker discrimination controls."""

from __future__ import annotations

import pytest
from toffee.scoreboard import ScoreboardMismatch

from suites.frontend.ibuffer.testbenches.vtype_gen.model import INIT_VTYPE
from suites.frontend.ibuffer.testbenches.vtype_gen.model import Outputs as VTOutputs
from suites.frontend.ibuffer.testbenches.vtype_gen.model import VType
from suites.frontend.ibuffer.testbenches.vtype_gen.checker import check_outputs as check_vtype


@pytest.mark.feature("IBUF-ENV-002")
def test_vtype_checker_rejects_one_field_bit():
    expected = VTOutputs(vtype=(INIT_VTYPE,) * 8, specvtype=(INIT_VTYPE,) * 8)
    broken = list(expected.vtype)
    broken[3] = VType(1, 0, 0, 0, 1)
    actual = VTOutputs(vtype=tuple(broken), specvtype=expected.specvtype)
    with pytest.raises(ScoreboardMismatch):
        check_vtype(expected, actual, phase="discrimination")
    broken = list(expected.specvtype)
    broken[7] = VType(0, 1, 0, 2, 1)
    actual = VTOutputs(vtype=expected.vtype, specvtype=tuple(broken))
    with pytest.raises(ScoreboardMismatch):
        check_vtype(expected, actual, phase="discrimination")
    check_vtype(expected, expected, phase="discrimination")
