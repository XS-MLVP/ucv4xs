from __future__ import annotations

from suites.frontend.bpu.sc.coverage.catalog import sc_coverage_model
from suites.frontend.bpu.sc.coverage.catalog import write_sc_coverage
from suites.frontend.bpu.sc.checker.assertions import learn
from suites.frontend.bpu.sc.case.definitions import PC
from suites.frontend.bpu.sc.case.definitions import POSITION
from suites.frontend.bpu.sc.case.definitions import TAGE_COUNTER
from suites.frontend.bpu.runtime.paths import REPO_ROOT


async def test_sc_functional_coverage_closes_defined_bins(sc_agent):
    coverage = sc_coverage_model()
    await sc_agent.reset()
    taken = await learn(sc_agent, 1)
    assert (taken.used, taken.taken) == (1, 1)
    coverage.sample({
        "decision": "used",
        "sc_direction": taken.taken,
        "training": 1,
        "qualification": "valid_conditional",
    })

    not_taken = await learn(sc_agent, 0)
    assert (not_taken.used, not_taken.taken) == (1, 0)
    coverage.sample({
        "decision": "used",
        "sc_direction": not_taken.taken,
        "training": 0,
        "qualification": "valid_conditional",
    })

    for qualification, overrides in (
        ("provider_invalid", {"provider_valid": 0}),
        ("mbtb_miss", {"mbtb_valid": 0}),
        ("nonconditional", {"branch_type": 2}),
    ):
        prediction = await sc_agent.predict(
            PC, POSITION, TAGE_COUNTER, **overrides
        )
        assert prediction.used == 0, (qualification, prediction)
        coverage.sample({
            "decision": "not_used",
            "sc_direction": prediction.taken,
            "training": "none",
            "qualification": qualification,
        })
    coverage.assert_coverage(100.0)
    write_sc_coverage(coverage, REPO_ROOT)
