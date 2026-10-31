"""A full region table must reuse an existing region without corrupting peers."""

from __future__ import annotations

import pytest

from suites.frontend.bpu.ittage.transaction.types import IttageTraining
from suites.frontend.bpu.ittage.coverage.catalog import ittage_region_capacity_coverage_model
from suites.frontend.bpu.ittage.coverage.catalog import write_ittage_region_capacity_coverage
from suites.frontend.bpu.ittage.case.definitions import PC
from suites.frontend.bpu.ittage.case.definitions import POSITION
from suites.frontend.bpu.ittage.case.definitions import REGION_COUNT
from suites.frontend.bpu.ittage.case.definitions import REGION_WIDTH
from suites.frontend.bpu.runtime.paths import REPO_ROOT


CONTEXTS = tuple(
    (PC + 0x20 * index, ((0x410 + index) << REGION_WIDTH) | 0x120)
    for index in range(REGION_COUNT)
)
# The adjacent odd set occupies the other lane of a folded SRAM word. It
# must not alias the first resident and reuses, rather than adds, region 7.
NEIGHBOR_PC = PC + 4
NEIGHBOR_TARGET = (0x417 << REGION_WIDTH) | 0x240


def require_target(prediction, target):
    assert (prediction.hit, prediction.target) == (1, target), prediction
    assert prediction.meta["provider"]["valid"] == 1, prediction
    assert prediction.meta["providerTarget_addr"] == target, prediction


@pytest.mark.feature("BPU-ITTAGE-015")
@pytest.mark.feature("BPU-ITTAGE-017")
async def test_full_region_table_reuses_existing_region_and_preserves_packed_neighbor(ittage_agent):
    coverage = ittage_region_capacity_coverage_model()
    await ittage_agent.reset()
    assert len({target >> REGION_WIDTH for _, target in CONTEXTS}) == REGION_COUNT
    for index, (pc, target) in enumerate(CONTEXTS):
        cold = await ittage_agent.predict(pc)
        assert cold.hit == 0 and cold.meta["allocate"]["valid"] == 1, cold
        await ittage_agent.train(IttageTraining(pc, POSITION, target, cold.meta, 1))
        # Check every existing pointer after every insertion, not just the
        # newly returned target; all targets deliberately share low bits.
        for resident_pc, resident_target in CONTEXTS[:index + 1]:
            require_target(await ittage_agent.predict(resident_pc), resident_target)
    for index, (pc, target) in enumerate(CONTEXTS):
        require_target(await ittage_agent.predict(pc), target)
        coverage.sample({"phase": "filled", "region": index})

    cold = await ittage_agent.predict(NEIGHBOR_PC)
    assert cold.hit == 0 and cold.meta["allocate"]["valid"] == 1, cold
    await ittage_agent.train(IttageTraining(NEIGHBOR_PC, POSITION, NEIGHBOR_TARGET, cold.meta, 1))
    require_target(await ittage_agent.predict(NEIGHBOR_PC), NEIGHBOR_TARGET)
    for index, (pc, target) in enumerate(CONTEXTS):
        require_target(await ittage_agent.predict(pc), target)
        coverage.sample({"phase": "full_reuse", "region": index})

    # Associate mixed requests at one-cycle acceptance spacing through the
    # agent's driver/monitor scoreboard; no explicit edge waits or gather.
    order = tuple(reversed(range(REGION_COUNT)))
    transfers = [ittage_agent.submit_predict(NEIGHBOR_PC)] + [
        ittage_agent.submit_predict(CONTEXTS[index][0]) for index in order
    ]
    await ittage_agent.drain_predictions()
    require_target(await transfers[0], NEIGHBOR_TARGET)
    for transfer, index in zip(transfers[1:], order, strict=True):
        require_target(await transfer, CONTEXTS[index][1])
        coverage.sample({"phase": "interleaved", "region": index})
    coverage.assert_coverage(100.0)
    write_ittage_region_capacity_coverage(coverage, REPO_ROOT)
