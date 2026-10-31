"""Verify event semantics through default driver/monitor/reference checks."""
import pytest

from suites.frontend.bpu.uras.case.semantic import check_held_call_repair
from suites.frontend.bpu.uras.coverage.semantic import HELD_PROFILES, HeldCallCoverage
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature('BPU-URAS-003')
@pytest.mark.parametrize('profile', HELD_PROFILES)
async def test_held_call_correction_survives_withdrawal_and_is_consumed_once(uras_agent, request, profile):
    import json
    coverage = HeldCallCoverage(profile)
    evidence = dict(profile=profile, status='INCOMPLETE')
    try:
        evidence.update(await check_held_call_repair(uras_agent, profile, coverage))
    finally:
        coverage.write(output_directory(REPO_ROOT, 'uras'))
        request.node.user_properties.append(('semantic_uras_held_call_repair', json.dumps(evidence, sort_keys=True)))

from suites.frontend.bpu.uras.case.definitions import CALL_A, CALL_B, MAIN_TOP
from suites.frontend.bpu.uras.case.semantic import concurrent_program, coroutine_correction
from suites.frontend.bpu.uras.transaction.types import UrasCycle


@pytest.mark.feature('BPU-URAS-008')
async def test_concurrent_pipeline_events_use_the_independent_stack(uras_agent):
    await uras_agent.reset()
    before = uras_agent.reference.board.status.checked
    actual = await uras_agent.stream(concurrent_program())
    assert len(actual) == len(concurrent_program())
    status = uras_agent.reference.board.status
    assert status.checked >= before + len(actual) and status.failed == 0
    assert status.passed == status.checked


@pytest.mark.feature('BPU-URAS-016')
@pytest.mark.parametrize('stage', [1, 2, 3], ids=['speculation', 'pending-correction', 'retiring-correction'])
async def test_return_and_call_replaces_top_instead_of_becoming_neutral(uras_agent, stage):
    await uras_agent.reset()
    await uras_agent.pulse(UrasCycle(s1_fire=1, spec_action=2,
        spec_start_pc=CALL_A.start_pc, spec_position=CALL_A.position, full_ret_addr=MAIN_TOP))
    await uras_agent.pulse(UrasCycle(s2_fire=1, full_ret_addr=MAIN_TOP))
    # The existing CALL_A, new CALL_B and main top are deliberately distinct.
    # No observed target is reused as the expectation. The default reference
    # must interpret PopAndPush as an operation, including on corrections.
    actual = await uras_agent.pulse(coroutine_correction(stage))
    assert actual.usable == 1
    assert actual.target != MAIN_TOP
    assert actual.target == ((CALL_B.start_pc // 8) * 8 + CALL_B.position + 1)
