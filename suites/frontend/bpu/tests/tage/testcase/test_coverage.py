from __future__ import annotations

from suites.frontend.bpu.tage.transaction.types import TageTraining
from suites.frontend.bpu.tage.coverage.catalog import tage_coverage_model
from suites.frontend.bpu.tage.coverage.catalog import write_tage_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.tage.checker.assertions import allocate
from suites.frontend.bpu.tage.checker.assertions import fill_useful_set
from suites.frontend.bpu.tage.checker.assertions import provider_depth
from suites.frontend.bpu.tage.checker.assertions import reach_highest_provider
from suites.frontend.bpu.tage.checker.assertions import require_miss
from suites.frontend.bpu.tage.case.definitions import PC
from suites.frontend.bpu.tage.case.definitions import POSITION


async def test_tage_functional_coverage_closes_defined_bins(tage_agent):
    coverage = tage_coverage_model()
    await tage_agent.reset()
    cold = await tage_agent.predict(PC, POSITION, 0)
    require_miss(cold)
    assert cold.taken == 0
    coverage.sample({
        "lookup": "miss", "direction": cold.taken, "operation": "cold",
        "provider_depth": provider_depth(cold),
    })
    prediction = await allocate(tage_agent)
    assert prediction.meta["hasProvider"] == 1
    coverage.sample({
        "lookup": "provider", "direction": prediction.taken, "operation": "allocate",
        "provider_depth": provider_depth(prediction),
    })
    previous_counter = prediction.meta["providerTakenCtr_value"]
    await tage_agent.train(TageTraining(PC, POSITION, 0, 1, prediction.meta))
    prediction = await tage_agent.predict(PC, POSITION, 1)
    assert prediction.meta["hasProvider"] == 1
    assert prediction.meta["providerTakenCtr_value"] < previous_counter
    coverage.sample({
        "lookup": "provider", "direction": prediction.taken, "operation": "update",
        "provider_depth": provider_depth(prediction),
    })
    prediction = await tage_agent.predict(PC, POSITION, 0)
    previous_counter = prediction.meta["providerTakenCtr_value"]
    await tage_agent.train(TageTraining(PC, POSITION, 1, 0, prediction.meta))
    prediction = await tage_agent.predict(PC, POSITION, 0)
    assert prediction.meta["hasProvider"] == 1
    assert prediction.meta["providerTakenCtr_value"] > previous_counter
    coverage.sample({
        "lookup": "provider", "direction": prediction.taken, "operation": "update",
        "provider_depth": provider_depth(prediction),
    })

    for _ in range(10):
        if (prediction.valid, prediction.taken) == (1, 1):
            break
        await tage_agent.train(TageTraining(PC, POSITION, 1, 0, prediction.meta))
        prediction = await tage_agent.predict(PC, POSITION, 0)
    assert (prediction.valid, prediction.taken) == (1, 1)
    coverage.sample({
        "lookup": "provider", "direction": prediction.taken,
        "operation": "update", "provider_depth": provider_depth(prediction),
    })

    await tage_agent.reset()
    highest = await reach_highest_provider(tage_agent)
    assert provider_depth(highest) == "highest"
    coverage.sample({
        "lookup": "provider", "direction": highest.taken, "operation": "update",
        "provider_depth": provider_depth(highest),
    })

    await tage_agent.reset()
    residents = await fill_useful_set(tage_agent)
    nonhighest = next(
        prediction for prediction in residents.values()
        if provider_depth(prediction) == "nonhighest"
    )
    assert nonhighest.meta["hasProvider"] == 1
    coverage.sample({
        "lookup": "provider", "direction": nonhighest.taken,
        "operation": "update", "provider_depth": provider_depth(nonhighest),
    })
    coverage.assert_coverage(100.0)
    write_tage_coverage(coverage, REPO_ROOT)
