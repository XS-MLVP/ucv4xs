"""A seventeenth target region exercises real, capacity-limited replacement."""
from dataclasses import replace
from functools import partial

import pytest

from suites.frontend.bpu.ittage.model.region import IttageRegionModel
from suites.frontend.bpu.ittage.transaction.types import IttageTraining
from suites.frontend.bpu.ittage.coverage.catalog import ittage_region_replacement_coverage_model
from suites.frontend.bpu.ittage.coverage.catalog import write_ittage_region_replacement_coverage
from suites.frontend.bpu.ittage.checker.assertions import require_snapshot
from suites.frontend.bpu.ittage.case.definitions import PC
from suites.frontend.bpu.ittage.case.definitions import POSITION
from suites.frontend.bpu.ittage.case.definitions import REGION_WIDTH
from tests.ittage.testcase.test_region_capacity import CONTEXTS
from tests.ittage.testcase.test_region_capacity import require_target
from suites.frontend.bpu.runtime.paths import REPO_ROOT


async def allocate_region(agent, model, pc, target):
    cold = await agent.predict(pc)
    assert cold.hit == 0 and cold.meta['allocate']['valid'] == 1, (pc, cold)
    allocation = model.allocate(target)  # Before any result influences the reference.
    await agent.train(IttageTraining(pc, POSITION, target, cold.meta, 1))
    actual = await agent.predict(pc)
    require_target(actual, target)
    return allocation, actual


async def check_residents(agent, model, residents):
    for pc, pointer, offset, snapshot in reversed(residents):
        target = model.decode(pointer, offset)
        expected = replace(snapshot, target=target,
                           meta={**snapshot.meta, 'providerTarget_addr': target})
        agent.submit_predict(pc, expected=partial(require_snapshot, expected=expected))
    await agent.drain_predictions()


@pytest.mark.feature('BPU-ITTAGE-018')
@pytest.mark.feature('BPU-ITTAGE-017')
async def test_two_full_region_replacements_follow_plru_and_preserve_other_pointers(ittage_agent):
    coverage = ittage_region_replacement_coverage_model()
    mask = (1 << REGION_WIDTH) - 1
    for touch in (0, 15):
        await ittage_agent.reset()
        model = IttageRegionModel()
        residents = []
        for pc, target in CONTEXTS:
            allocation, snapshot = await allocate_region(ittage_agent, model, pc, target)
            assert allocation.evicted_region is None and not allocation.reused
            residents.append((pc, allocation.pointer, target & mask, snapshot))
        await check_residents(ittage_agent, model, residents)

        # A packed neighbor reuses an existing region. Only real region writes
        # touch the policy: prediction read order must not change the victim.
        target = (CONTEXTS[touch][1] & ~mask) | 0x240
        allocation, snapshot = await allocate_region(ittage_agent, model, PC + 4, target)
        assert allocation.reused and allocation.evicted_region is None
        residents.append((PC + 4, allocation.pointer, target & mask, snapshot))
        await check_residents(ittage_agent, model, residents)

        victims = []
        for step in (1, 2):
            pc = PC + step * 8  # Previously unused predictor index.
            target = ((0x42F + step) << REGION_WIDTH) | (0x300 + step * 0x60)
            before = model.regions
            allocation, snapshot = await allocate_region(ittage_agent, model, pc, target)
            assert not allocation.reused and allocation.evicted_region is not None
            assert sum(a != b for a, b in zip(before, model.regions, strict=True)) == 1
            victims.append(allocation.pointer)
            # Old entries retain this pointer. Changed high target bits are
            # the designed capacity effect, not an assumed invalidation.
            assert any(pointer == allocation.pointer for _, pointer, _, _ in residents)
            residents.append((pc, allocation.pointer, target & mask, snapshot))
            await check_residents(ittage_agent, model, residents)
            for observation in ('victim_redecoded', 'survivor_retained'):
                coverage.sample({'touch': touch, 'step': step, 'observation': observation,
                                 'victim_half': 'low' if allocation.pointer < 8 else 'high'})
        assert len(set(victims)) == 2
        assert {pointer // 8 for pointer in victims} == {0, 1}
    coverage.assert_coverage(100.0)
    write_ittage_region_replacement_coverage(coverage, REPO_ROOT)
