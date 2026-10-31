"""Disabled MicroRAS must not offer a usable return target."""
import pytest

from suites.frontend.bpu.uras.case.definitions import CALL_A
from suites.frontend.bpu.uras.checker.assertions import pushed
from suites.frontend.bpu.uras.coverage.enable_gate import EnableGateCoverage
from suites.frontend.bpu.uras.transaction.types import UrasCycle
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT


@pytest.mark.feature("BPU-URAS-017")
async def test_disabled_micro_ras_withholds_the_armed_return_target(uras_agent):
    """A parent CSR disable must make the public prediction unusable.

    The pending call is established while enabled. Idle disabled beats must
    hide the target; re-enabling must restore the same retained target, so the
    gate is a use qualification rather than a destructive flush.
    """

    coverage = EnableGateCoverage()
    try:
        await uras_agent.reset()
        armed = await uras_agent.pulse(
            UrasCycle(
                enable=1,
                s1_fire=1,
                spec_start_pc=CALL_A.start_pc,
                spec_position=CALL_A.position,
                spec_action=2,
            )
        )
        assert armed == pushed(CALL_A)
        coverage.record("reached", "armed-target-published", target=armed.target)

        disabled = []
        for _ in range(3):
            disabled.append(await uras_agent.cycle(UrasCycle(enable=0)))
        coverage.record("reached", "disabled-target-suppressed")
        for actual in disabled:
            assert actual.usable == 0, (
                "MicroRAS exposed a usable return target while the parent "
                f"enable was low: {actual!r}"
            )
        coverage.record("checked", "disabled-target-suppressed")

        retained = await uras_agent.cycle(UrasCycle(enable=1))
        assert retained == pushed(CALL_A)
        coverage.record("reached", "re-enabled-target-retained", target=retained.target)
        coverage.record("checked", "armed-target-published")
        coverage.record("checked", "re-enabled-target-retained")
    finally:
        coverage.write(output_directory(REPO_ROOT, "uras"))
