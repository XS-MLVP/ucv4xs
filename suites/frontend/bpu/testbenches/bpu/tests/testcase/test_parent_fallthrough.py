"""Given real S0 inputs, check the existing FallThroughPredictor in its parent.

Guard/sign-opposed targets are a predictor-port domain, not full FTQ/program
reachability. The internal leaf target never substitutes for public DCE target.
"""
import json

import pytest

from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuRedirect
from suites.frontend.bpu.testbenches.shared.env.artifacts import write_output
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT

PC = 0x40000800
TARGETS = (0x40001007, 0x400017e0, 0x400017f0, 0x400017ff,
           (1 << 49) + 0x400017f0, (1 << 50) - 1)


@pytest.mark.feature('BPU-INT-002')
async def test_parent_fallthrough_extent_and_hold_keep_page_guard_and_fire_owner(bpu_agent, request):
    evidence = {}
    try:
        async with bpu_agent.observe_parent_primitives() as evidence:
            await bpu_agent.configure_predictors(ubtb=False, abtb=False, mbtb=False,
                tage=False, sc=False, ittage=False, ras=False, settle=True)
            await bpu_agent.reset(PC)
            source = await bpu_agent.next_transaction(start_pc=PC)
            for target in TARGETS:
                await bpu_agent.set_ready(prediction=False, meta=True)
                # Each supplied recovery is an indirect jump at the original
                # CFI with unchanged metadata; no constant fabrication.
                boundary = await bpu_agent.redirect(BpuRedirect(target, source.meta.redirect,
                    cfi_pc=PC + 1, taken=1, branch_type=3))
                await bpu_agent.wait_cycles(3)
                await bpu_agent.set_ready(prediction=True, meta=True)
                _, actual = await bpu_agent.next_prediction(start_pc=target, after_tick=boundary)
                assert actual.target is None and actual.taken == 0
                await bpu_agent.wait_cycles(1)
    finally:
        write_output(REPO_ROOT / 'results/bpu/parent-fallthrough-disabled-from-reset.json',
                     json.dumps(evidence, sort_keys=True))
        request.node.user_properties.append(('parent_fallthrough_given_s0', json.dumps(evidence, sort_keys=True)))
    seen = {frame['pc'] for frame in evidence['lookups'] if frame['fire']}
    assert set(TARGETS) <= seen
    assert evidence['counts']['fetch_held'] > 0
    assert any(frame['offered_pc'] != frame['pc'] and not frame['fire'] for frame in evidence['lookups'])
    assert {15, 31} <= {frame['actual']['position'] for frame in evidence['lookups']}


@pytest.mark.feature('BPU-INT-101')
async def test_disabled_retained_microbtb_hit_cannot_redirect_a_new_parent_query(bpu_agent, request):
    """A known cold → learned → disabled sequence, not random startup payload.

    Same-target self loop proves an actual UBTB taken hit before disabling it.
    A fresh PC after the delay must not select that source. Preserve the FAIL
    if it does; no state writes, synthetic metadata, reset, or XFAIL allowance.
    """
    from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuTraining
    from suites.frontend.bpu.testbenches.bpu.model.parent_primitives import ENABLES
    evidence = {}
    try:
        async with bpu_agent.observe_parent_primitives() as evidence:
            await bpu_agent.reset(PC)
            await bpu_agent.configure_predictors(ubtb=True, abtb=False, mbtb=False,
                tage=False, sc=False, ittage=False, ras=False, settle=True)
            cold = await bpu_agent.next_transaction(start_pc=PC)
            assert cold.prediction.taken == 0
            await bpu_agent.train(BpuTraining(PC, 4, PC, cold.meta.resolve,
                                            branch_type=3), prediction_pause=True)
            boundary = await bpu_agent.redirect(BpuRedirect(PC, cold.meta.redirect,
                cfi_pc=PC + 4, taken=1, branch_type=3))
            _, learned = await bpu_agent.next_prediction(start_pc=PC, after_tick=boundary)
            assert learned.taken == 1
            # A self-loop remains a known taken hit throughout the two-edge
            # control transition. It is not replaced by a younger cold read.
            await bpu_agent.configure_predictors(**dict.fromkeys(ENABLES, False), settle=True)
            await bpu_agent.set_ready(prediction=False, meta=True)
            target = PC + 0x1000
            boundary = await bpu_agent.redirect(BpuRedirect(target, cold.meta.redirect,
                cfi_pc=PC + 4, taken=1, branch_type=3))
            await bpu_agent.set_ready(prediction=True, meta=True)
            _, prediction = await bpu_agent.next_prediction(start_pc=target, after_tick=boundary)
            assert prediction.taken == 0, ('disabled original UBTB hit was reused at a fresh PC', prediction)
    finally:
        write_output(REPO_ROOT / 'results/bpu/parent-disable-retained-hit.json',
                     json.dumps(evidence, sort_keys=True))
        request.node.user_properties.append(('parent_disable_known_hit', json.dumps(evidence, sort_keys=True)))
