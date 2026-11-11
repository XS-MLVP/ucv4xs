"""DelayN is covered at its real Bpu parent, not a separate functional ID."""
import json

import pytest

from suites.frontend.bpu.testbenches.bpu.model.parent_primitives import ENABLES
from suites.frontend.bpu.testbenches.shared.env.artifacts import write_output
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT

pytestmark = pytest.mark.selftest


async def test_parent_checks_all_seven_enable_lanes_at_exact_two_edge_delay(bpu_agent, request):
    patterns = (0, 127, *(1 << lane for lane in range(7)),
                *(127 ^ (1 << lane) for lane in range(7)), 0, 127, 0)
    async with bpu_agent.observe_parent_primitives() as evidence:
        await bpu_agent.reset(0x40000800)
        for pattern in patterns:
            await bpu_agent.configure_predictors(**{
                name: bool(pattern & (1 << lane)) for lane, name in enumerate(ENABLES)})
        await bpu_agent.wait_cycles(3)
    frames = evidence['controls']
    offered = {tuple(frame['inputs'][name] for name in ENABLES) for frame in frames}
    assert {tuple(int(bool(pattern & (1 << lane))) for lane in range(7))
            for pattern in patterns} <= offered
    for name in ENABLES:
        transitions = {(left['actual'][name], right['actual'][name])
                       for left, right in zip(frames, frames[1:])}
        assert {(0, 1), (1, 0)} <= transitions, (name, transitions)
    assert evidence['counts']['delay_checked'] == evidence['counts']['paired_edges'] - 1
    write_output(REPO_ROOT / 'results/bpu/parent-delay-exact-edges.json',
                 json.dumps(evidence, sort_keys=True))
    request.node.user_properties.append(('parent_delay_exact_edges', json.dumps(evidence, sort_keys=True)))


async def test_parent_fallthrough_given_inputs_after_a_real_enabled_cold_query(bpu_agent):
    """Leaf extent/hold only; independent of disabling a retained taken hit.

    Prime a genuine enabled cold lookup so this companion does not rely on the
    unreset UBTB hit latch. The separate disabled-from-reset FAIL is untouched.
    """
    from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuRedirect
    pc = 0x40000800
    targets = (0x40001007, 0x400017e0, 0x400017f0, 0x400017ff,
               (1 << 49) + 0x400017f0, (1 << 50) - 1)
    evidence = {}
    try:
        async with bpu_agent.observe_parent_primitives() as evidence:
            await bpu_agent.reset(pc)
            source = await bpu_agent.next_transaction(start_pc=pc)
            await bpu_agent.configure_predictors(**dict.fromkeys(ENABLES, False), settle=True)
            for target in targets:
                await bpu_agent.set_ready(prediction=False, meta=True)
                boundary = await bpu_agent.redirect(BpuRedirect(target, source.meta.redirect,
                    cfi_pc=pc + 1, taken=1, branch_type=3))
                await bpu_agent.wait_cycles(3)
                await bpu_agent.set_ready(prediction=True, meta=True)
                _, prediction = await bpu_agent.next_prediction(start_pc=target, after_tick=boundary)
                assert prediction.target is None and prediction.taken == 0
            await bpu_agent.wait_cycles(2)
    finally:
        write_output(REPO_ROOT / 'results/bpu/parent-fallthrough-primed-cold.json',
                     json.dumps(evidence, sort_keys=True))
    assert set(targets) <= {row['pc'] for row in evidence['lookups'] if row['fire']}
    assert evidence['counts']['fetch_held'] > 0
    assert any(not row['fire'] and row['offered_pc'] != row['pc'] for row in evidence['lookups'])
