"""Missing FTQ resolve stimulus found through native RTL line gaps."""
from dataclasses import replace

import pytest

from suites.frontend.bpu.ubtb.transaction.types import BranchTraining
from suites.frontend.bpu.ubtb.transaction.types import UbtbBatchTraining
from suites.frontend.bpu.ubtb.transaction.types import UbtbBranchFeedback
from suites.frontend.bpu.ubtb.transaction.types import UbtbPrediction
from suites.frontend.bpu.ubtb.coverage.catalog import ubtb_resolve_slot_coverage_model
from suites.frontend.bpu.ubtb.coverage.catalog import write_ubtb_resolve_slot_coverage
from suites.frontend.bpu.ubtb.coverage.catalog import ubtb_resolve_arbitration_coverage_model
from suites.frontend.bpu.ubtb.coverage.catalog import write_ubtb_resolve_arbitration_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.ubtb.checker.assertions import assert_miss


def resolve_at(pc, slot, branch):
    """Earlier branches execute correctly; later branches are FTQ-masked."""
    earlier = tuple(
        UbtbBranchFeedback(pc + 0x400 + index * 2, 0, (index * 4 + 2) % 32, 1)
        for index in range(slot)
    )
    return UbtbBatchTraining(pc, (*earlier, branch))


def expected(branch):
    return UbtbPrediction(1, 1, branch.target, branch.position,
                          branch.branch_type, branch.ras_action)


@pytest.mark.feature('BPU-UBTB-016')
async def test_resolve_all_slots_preserve_payload_attributes_and_taken_selection(ubtb_agent):
    coverage = ubtb_resolve_slot_coverage_model()
    await ubtb_agent.reset()
    residents = []
    # Legal instruction attributes: conditional, jump, call, indirect,
    # return, indirect call, coroutine return-and-call, and another jump.
    attributes = ((1, 0), (2, 0), (2, 2), (3, 0), (3, 1), (3, 2), (3, 3), (2, 0))
    for slot, (branch_type, ras_action) in enumerate(attributes):
        pc = 0x80010000 + slot * 0x40
        branch = UbtbBranchFeedback(pc + 0x1000 + slot * 2, 1, slot * 4,
                                    branch_type, ras_action, mispredict=1)
        await ubtb_agent.train_resolve(resolve_at(pc, slot, branch))
        assert await ubtb_agent.predict(pc) == expected(branch), f'selected slot {slot}'
        residents.append((pc, expected(branch)))
        coverage.sample({'slot': slot, 'case': 'attributes'})

        conditional_pc = 0x80020000 + slot * 0x40
        conditional = UbtbBranchFeedback(conditional_pc + 0x1800, 1,
                                         slot * 4 + 1, 1, mispredict=1)
        await ubtb_agent.train_resolve(resolve_at(conditional_pc, slot, conditional))
        assert await ubtb_agent.predict(conditional_pc) == expected(conditional)
        for decrement in range(1, 4):
            await ubtb_agent.train_resolve(
                resolve_at(conditional_pc, slot, replace(conditional, taken=0))
            )
            if decrement < 3:
                assert await ubtb_agent.predict(conditional_pc) == expected(conditional)
            else:
                await assert_miss(ubtb_agent, conditional_pc)
        coverage.sample({'slot': slot, 'case': 'conditional_aging'})

    # Pipelined readback must retain every independently selected payload.
    for pc, prediction in residents:
        ubtb_agent.submit_predict(pc, expected=prediction)
    await ubtb_agent.drain_predictions()
    coverage.assert_coverage(100.0)
    write_ubtb_resolve_slot_coverage(coverage, REPO_ROOT)


@pytest.mark.feature('BPU-UBTB-017')
async def test_resolve_arbitration_checks_actual_same_beat_sources_and_enable(ubtb_agent):
    coverage = ubtb_resolve_arbitration_coverage_model()
    pc = 0x80040000
    fast_pc = pc + 0x200
    resolve = UbtbBranchFeedback(pc + 0x2000, 1, 6, 3, ras_action=1, mispredict=1)
    batch = resolve_at(pc, 3, resolve)
    fast = BranchTraining(fast_pc, fast_pc + 0x3000, 1, 9, 2, ras_action=2)
    fast_expected = UbtbPrediction(1, 1, fast.target, fast.position,
                                   fast.branch_type, fast.ras_action)
    await ubtb_agent.reset()
    await ubtb_agent.train_resolve(batch, fast_train=fast)
    assert await ubtb_agent.predict(pc) == expected(resolve)
    await assert_miss(ubtb_agent, fast_pc)
    coverage.sample({'phase': 'resolve_priority_distinct_pc'})

    await ubtb_agent.reset()
    await ubtb_agent.train_resolve(batch, fast_train=replace(fast, pc=pc))
    assert await ubtb_agent.predict(pc) == expected(resolve)
    coverage.sample({'phase': 'resolve_priority_same_pc'})

    for phase, unqualified in (
        ('correct_branch_fast_fallback', replace(resolve, mispredict=0)),
        ('invalid_mispredict_fast_fallback', replace(resolve, valid=0)),
        ('t0_gated_fast_fallback', resolve),
    ):
        await ubtb_agent.reset()
        feedback = resolve_at(pc, 3, unqualified)
        if phase == 't0_gated_fast_fallback':
            feedback = replace(feedback, fire=0)
        await ubtb_agent.train_resolve(feedback, fast_train=fast)
        assert await ubtb_agent.predict(fast_pc) == fast_expected
        await assert_miss(ubtb_agent, pc)
        coverage.sample({'phase': phase})

    # Without fastTrain, correct feedback is not a MicroBTB update.
    await ubtb_agent.train_resolve(resolve_at(fast_pc, 3, replace(resolve, mispredict=0)))
    assert await ubtb_agent.predict(fast_pc) == fast_expected
    await ubtb_agent.train_resolve(resolve_at(pc, 3, replace(resolve, mispredict=0)))
    await assert_miss(ubtb_agent, pc)
    coverage.sample({'phase': 'unqualified_resolve_preserves_entry'})

    await ubtb_agent.set_enabled(False)
    await ubtb_agent.train_resolve(batch, fast_train=replace(fast, target=fast.target + 0x100))
    await ubtb_agent.set_enabled(True)
    await assert_miss(ubtb_agent, pc)
    assert await ubtb_agent.predict(fast_pc) == fast_expected
    coverage.sample({'phase': 'disabled_sources_blocked'})
    await ubtb_agent.train_resolve(batch)
    assert await ubtb_agent.predict(pc) == expected(resolve)
    assert await ubtb_agent.predict(fast_pc) == fast_expected
    coverage.sample({'phase': 'reenabled_resolve_allocates'})
    coverage.assert_coverage(100.0)
    write_ubtb_resolve_arbitration_coverage(coverage, REPO_ROOT)
