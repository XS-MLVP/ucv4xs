"""BPU halfwords convert once to the independent MicroBTB byte model."""
from types import SimpleNamespace

import pytest

from suites.frontend.bpu.bpu.model.micro_sources import MicroSources
from suites.frontend.bpu.ubtb.model.semantic import UbtbEvents
from suites.frontend.bpu.ubtb.transaction.types import BranchTraining, PredictRequest


@pytest.mark.parametrize('pc,target,expected', (
    (0x40000800, 0x40202340, 0x40202340),  # Byte bit22 is still local.
    (0x40000800, 0x40402340, 0x40002340),  # Raw bit22 crosses the local region.
    ((1 << 49) - 0x800, (1 << 49) - 1, (1 << 49) - 1),
))
def test_composed_micro_source_keeps_raw_bit21_and_expands_only_once(pc, target, expected):
    sources = MicroSources()
    sources.micro.advance(UbtbEvents(fast_feedback=BranchTraining(pc * 2, target * 2, 1, 3, 2)))
    sources.micro.advance(UbtbEvents())
    sources.micro.advance(UbtbEvents(predict=PredictRequest(pc * 2)))
    decision = sources.choose(SimpleNamespace(pc=pc), 1, (True, False, False, False, False, False, False))
    assert decision.source == 'micro'
    assert decision.branch.target == expected
    assert sources.micro.lookup.pc == pc * 2
