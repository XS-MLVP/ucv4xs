"""Dedicated MicroTAGE functional-coverage closure scenario."""

from __future__ import annotations

from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.coverage.catalog import utage_coverage_model
from bpuverify.utage.coverage.catalog import write_utage_coverage
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.checker.assertions import allocate
from bpuverify.utage.checker.assertions import counter
from bpuverify.utage.case.definitions import PASSING_PC
from bpuverify.utage.case.definitions import POSITION
from bpuverify.utage.case.definitions import SATURATION_ATTEMPTS


async def test_utage_functional_coverage_closes_defined_bins(utage_agent):
    coverage = utage_coverage_model()
    await utage_agent.reset()
    cold = await utage_agent.predict(PASSING_PC, POSITION, 0)
    assert (cold.hit, cold.taken) == (0, 0)
    coverage.sample({
        "lookup": "miss", "direction": cold.taken,
        "operation": "idle", "recovery": "normal",
        "history": "zero",
    })
    prediction = await allocate(utage_agent, PASSING_PC, POSITION)
    coverage.sample({
        "lookup": "hit", "direction": prediction.taken,
        "operation": "allocate", "recovery": "normal",
        "history": "zero",
    })

    for _ in range(SATURATION_ATTEMPTS):
        await utage_agent.train(UtageTraining(PASSING_PC, POSITION, 0, prediction.meta))
        prediction = await utage_agent.predict(PASSING_PC, POSITION, 1)
    assert (prediction.hit, prediction.taken, counter(prediction)) == (1, 0, 0)
    coverage.sample({
        "lookup": "hit", "direction": prediction.taken,
        "operation": "update", "recovery": "normal",
        "history": "zero",
    })

    for _ in range(SATURATION_ATTEMPTS):
        await utage_agent.train(UtageTraining(PASSING_PC, POSITION, 1, prediction.meta))
        prediction = await utage_agent.predict(PASSING_PC, POSITION, 0)
    assert (prediction.hit, prediction.taken, counter(prediction)) == (1, 1, 7)
    coverage.sample({
        "lookup": "hit", "direction": prediction.taken,
        "operation": "update", "recovery": "normal",
        "history": "zero",
    })

    for stage in ("s2", "s3"):
        primed = await utage_agent.predict(PASSING_PC, POSITION, 0)
        assert (primed.hit, primed.taken) == (1, 1)
        retagged = await utage_agent.recover_prediction(
            PASSING_PC, POSITION, 0,
            stage=stage, override_pc=PASSING_PC + 0x20,
        )
        assert retagged.hit == 0
        coverage.sample({
            "lookup": "miss", "direction": retagged.taken,
            "operation": "idle", "recovery": f"{stage}_override",
            "history": "zero",
        })

    await utage_agent.reset()
    history = 0b1000
    cold_history = await utage_agent.predict(
        PASSING_PC, POSITION, 0, folded_history=history
    )
    assert cold_history.hit == 0
    await utage_agent.train(
        UtageTraining(PASSING_PC, POSITION, 1, cold_history.meta)
    )
    trained_history = await utage_agent.predict(
        PASSING_PC, POSITION, 0, folded_history=history
    )
    assert (trained_history.hit, trained_history.taken) == (1, 1)
    coverage.sample({
        "lookup": "hit", "direction": trained_history.taken,
        "operation": "allocate", "recovery": "normal",
        "history": "nonzero",
    })
    coverage.assert_coverage(100.0)
    write_utage_coverage(coverage, REPO_ROOT)
