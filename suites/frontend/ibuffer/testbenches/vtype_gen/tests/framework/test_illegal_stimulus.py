"""VTypeGen illegal-stimulus guards."""

from __future__ import annotations

import pytest

from suites.frontend.ibuffer.testbenches.vtype_gen.model import Inputs as VTypeInputs
from suites.frontend.ibuffer.testbenches.vtype_gen.model import StimulusError as VTypeStimulusError


@pytest.mark.feature("IBUF-ENV-003")
def test_vtype_lane_count_is_enforced():
    with pytest.raises(VTypeStimulusError, match="8 lanes"):
        VTypeInputs(insts=((0, 0),) * 7)
    VTypeInputs(insts=((0, 0),) * 8)
