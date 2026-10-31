"""Dedicated MicroRAS functional-coverage closure scenario."""

from __future__ import annotations

from suites.frontend.bpu.uras.transaction.types import UrasCycle
from suites.frontend.bpu.uras.transaction.types import UrasResult
from suites.frontend.bpu.uras.coverage.catalog import uras_coverage_model
from suites.frontend.bpu.uras.coverage.catalog import write_uras_coverage
from suites.frontend.bpu.uras.checker.assertions import pushed
from suites.frontend.bpu.uras.case.definitions import CALL_A
from suites.frontend.bpu.uras.case.definitions import CALL_B
from suites.frontend.bpu.uras.case.definitions import MAIN_TOP
from suites.frontend.bpu.uras.case.definitions import pending_s3_pop_cycles
from suites.frontend.bpu.uras.case.definitions import younger_s2_push_cycles
from suites.frontend.bpu.runtime.paths import REPO_ROOT


async def test_uras_functional_coverage_closes_defined_bins(uras_agent):
    coverage = uras_coverage_model()
    await uras_agent.reset()
    scenarios = (
        (UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP), "main_ras", 1, 0),
        (UrasCycle(s1_fire=1, spec_start_pc=CALL_A.start_pc, spec_position=CALL_A.position, spec_action=2), "s1", 1, 2),
        (UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP, spec_action=1), "s1", 1, 1),
        (UrasCycle(has_redirect=1), "redirect", 0, 0),
        (UrasCycle(s2_valid=1, s2_start_pc=CALL_B.start_pc, s2_position=CALL_B.position, s2_action=2), "s2_override", 1, 2),
        (UrasCycle(s2_valid=1, s2_action=1), "s2_override", 0, 1),
        (UrasCycle(s3_valid=1, s3_start_pc=CALL_A.start_pc, s3_position=CALL_A.position, s3_action=2), "s3_override", 1, 2),
        (UrasCycle(s3_valid=1, s3_action=1), "s3_override", 0, 1),
    )
    for transaction, source, result, action in scenarios:
        observed = await uras_agent.cycle(transaction)
        assert observed.usable == result, (source, observed)
        coverage.sample({"source": source, "result": observed.usable, "action": action})

    await uras_agent.reset()
    assert await uras_agent.pulse(
        UrasCycle(
            s1_fire=1,
            spec_start_pc=CALL_A.start_pc,
            spec_position=CALL_A.position,
            spec_action=2,
        )
    ) == pushed(CALL_A)
    s2 = await uras_agent.pulse(UrasCycle(s2_fire=1))
    assert s2 == pushed(CALL_A)
    coverage.sample({"source": "s2_advance", "result": s2.usable, "action": 0})
    s3 = await uras_agent.pulse(UrasCycle(s3_fire=1))
    assert s3 == pushed(CALL_A)
    coverage.sample({"source": "s3_clear", "result": s3.usable, "action": 0})

    await uras_agent.reset()
    assert await uras_agent.pulse(UrasCycle(
        s1_fire=1,
        spec_start_pc=CALL_A.start_pc,
        spec_position=CALL_A.position,
        spec_action=2,
    )) == pushed(CALL_A)
    assert await uras_agent.pulse(UrasCycle(s2_fire=1)) == pushed(CALL_A)
    neutral = await uras_agent.pulse(UrasCycle(s2_valid=1, full_ret_addr=MAIN_TOP))
    assert neutral == pushed(CALL_A)
    coverage.sample({"source": "s2_neutral_s3_push", "result": neutral.usable, "action": 0})
    for _ in range(3):
        paired_pop = await uras_agent.cycle(
            UrasCycle(s2_valid=1, s2_action=1, full_ret_addr=MAIN_TOP)
        )
    assert paired_pop == UrasResult(1, MAIN_TOP)
    coverage.sample({"source": "s2_pop_s3_push", "result": paired_pop.usable, "action": 1})

    await uras_agent.reset()
    adjacent = await uras_agent.stream((
        UrasCycle(
            s1_fire=1,
            spec_start_pc=CALL_A.start_pc,
            spec_position=CALL_A.position,
            spec_action=2,
        ),
        UrasCycle(s2_fire=1),
        UrasCycle(s1_fire=1, spec_action=1, full_ret_addr=MAIN_TOP),
        UrasCycle(s1_fire=1, full_ret_addr=MAIN_TOP),
        UrasCycle(),
    ))
    assert adjacent[3] == UrasResult(1, MAIN_TOP)
    coverage.sample({"source": "s1_pop_s3_push", "result": adjacent[3].usable, "action": 1})

    await uras_agent.reset()
    pending_pop = await uras_agent.stream(pending_s3_pop_cycles())
    assert pending_pop[4].usable == 0
    assert pending_pop[5].usable == 0
    assert pending_pop[7] == UrasResult(1, MAIN_TOP)
    coverage.sample({"source": "s3_pop_s1_neutral", "result": pending_pop[4].usable, "action": 0})
    coverage.sample({"source": "s3_pop_s2_neutral", "result": pending_pop[5].usable, "action": 0})

    await uras_agent.reset()
    younger_push = await uras_agent.stream(younger_s2_push_cycles())
    assert younger_push[4] == pushed(CALL_B)
    assert younger_push[5].usable == 0
    assert younger_push[7] == UrasResult(1, MAIN_TOP)
    coverage.sample({"source": "s2_push_s3_pop", "result": younger_push[4].usable, "action": 2})

    coverage.assert_coverage(100.0)
    write_uras_coverage(coverage, REPO_ROOT)
