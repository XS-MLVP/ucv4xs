from __future__ import annotations

from bpuverify.ittage.transaction.types import IttageTraining
from bpuverify.ittage.coverage.catalog import ittage_coverage_model
from bpuverify.ittage.coverage.catalog import write_ittage_coverage
from bpuverify.ittage.checker.assertions import exhaust_allocation_candidates
from bpuverify.ittage.case.definitions import PC
from bpuverify.ittage.case.definitions import POSITION
from bpuverify.ittage.case.definitions import TARGET_A
from bpuverify.ittage.case.definitions import TARGET_B
from bpuverify.common.env.paths import REPO_ROOT


async def test_ittage_functional_coverage_closes_defined_bins(ittage_agent):
    coverage = ittage_coverage_model()
    await ittage_agent.reset()
    cold = await ittage_agent.predict(PC)
    assert cold.hit == 0 and cold.meta["provider"]["valid"] == 0
    coverage.sample({
        "lookup": "miss", "target": "none", "operation": "idle",
        "gate": 1, "provider": "none",
        "allocation": cold.meta["allocate"]["valid"],
        "history": "zero",
        "training_slot": "none",
    })
    await ittage_agent.train(IttageTraining(PC, POSITION, TARGET_A, cold.meta, 1))
    prediction = await ittage_agent.predict(PC)
    assert prediction.hit == 1 and prediction.target == TARGET_A
    assert prediction.meta["provider"]["valid"] == 1
    coverage.sample({
        "lookup": "hit", "target": "first", "operation": "allocate",
        "gate": 1, "provider": "primary",
        "allocation": prediction.meta["allocate"]["valid"],
        "history": "zero",
        "training_slot": "first",
    })
    await ittage_agent.train(IttageTraining(PC, POSITION, TARGET_B, prediction.meta, 1))
    prediction = await ittage_agent.predict(PC)
    assert prediction.hit == 1 and prediction.target == TARGET_B
    coverage.sample({
        "lookup": "hit", "target": "changed", "operation": "update",
        "gate": 1, "provider": "primary",
        "allocation": prediction.meta["allocate"]["valid"],
        "history": "zero",
        "training_slot": "first",
    })

    for _ in range(4):
        if prediction.meta["providerCnt_value"] == 0:
            break
        await ittage_agent.train(IttageTraining(PC, POSITION, TARGET_A, prediction.meta, 0))
        prediction = await ittage_agent.predict(PC)
    assert prediction.hit == 1 and prediction.target == TARGET_A
    assert prediction.meta["providerCnt_value"] == 0
    assert prediction.meta["altProvider"]["valid"] == 1
    coverage.sample({
        "lookup": "hit", "target": "first", "operation": "update",
        "gate": 1, "provider": "alternate",
        "allocation": prediction.meta["allocate"]["valid"],
        "history": "zero",
        "training_slot": "first",
    })

    await ittage_agent.set_enabled(False)
    disabled = await ittage_agent.predict(PC)
    assert disabled.hit == 0
    coverage.sample({
        "lookup": "miss", "target": "none", "operation": "idle",
        "gate": 0, "provider": "none", "allocation": "not_applicable",
        "history": "zero",
        "training_slot": "none",
    })

    await ittage_agent.reset()
    blocked = await exhaust_allocation_candidates(ittage_agent)
    assert blocked.hit == 1 and blocked.target in (TARGET_A, TARGET_B)
    coverage.sample({
        "lookup": "hit", "target": "first" if blocked.target == TARGET_A else "changed",
        "operation": "update",
        "gate": 1, "provider": "primary",
        "allocation": blocked.meta["allocate"]["valid"],
        "history": "zero",
        "training_slot": "first",
    })

    await ittage_agent.reset()
    history = 0b0100
    cold_history = await ittage_agent.predict(PC, folded_history=history)
    assert cold_history.hit == 0
    await ittage_agent.train(
        IttageTraining(PC, POSITION, TARGET_A, cold_history.meta, 1, history)
    )
    trained_history = await ittage_agent.predict(PC, folded_history=history)
    assert trained_history.hit == 1 and trained_history.target == TARGET_A
    coverage.sample({
        "lookup": "hit", "target": "first", "operation": "allocate",
        "gate": 1, "provider": "primary",
        "allocation": trained_history.meta["allocate"]["valid"],
        "history": "nonzero",
        "training_slot": "first",
    })

    await ittage_agent.reset()
    cold_later = await ittage_agent.predict(PC)
    assert cold_later.hit == 0
    later_target = 0x4080_1234
    await ittage_agent.train(
        IttageTraining(PC, POSITION, later_target, cold_later.meta, 1, branch_index=4)
    )
    trained_later = await ittage_agent.predict(PC)
    assert trained_later.hit == 1 and trained_later.target == later_target
    coverage.sample({
        "lookup": "hit", "target": "first", "operation": "allocate",
        "gate": 1, "provider": "primary",
        "allocation": trained_later.meta["allocate"]["valid"],
        "history": "zero", "training_slot": "later",
    })
    coverage.assert_coverage(100.0)
    write_ittage_coverage(coverage, REPO_ROOT)
