"""Reusable MainBTB enable-gate stimuli and immutable observations."""

from __future__ import annotations

from dataclasses import dataclass

from bpuverify.mbtb.transaction.types import MbtbPrediction
from bpuverify.mbtb.checker.assertions import assert_miss
from bpuverify.mbtb.checker.assertions import assert_vector_hit
from bpuverify.mbtb.checker.assertions import train
from bpuverify.mbtb.case.definitions import BranchVector
from bpuverify.mbtb.case.definitions import DIRECT
from bpuverify.mbtb.case.definitions import INDIRECT
from bpuverify.mbtb.case.definitions import MISS_PC


@dataclass(frozen=True, slots=True)
class LookupGateObservation:
    held: MbtbPrediction
    disabled: MbtbPrediction
    restored: MbtbPrediction


@dataclass(frozen=True, slots=True)
class TrainingGateObservation:
    before: MbtbPrediction
    disabled_update: MbtbPrediction
    enabled_update: MbtbPrediction
    changed: BranchVector


async def observe_lookup_gate(agent) -> LookupGateObservation:
    await agent.reset()
    cold = await agent.predict(DIRECT.pc)
    assert_miss(cold)
    await train(agent, DIRECT, cold.meta_entries)
    assert_vector_hit(await agent.predict(DIRECT.pc), DIRECT)
    assert_miss(await agent.predict(MISS_PC))

    await agent.set_enabled(False)
    held = await agent.sample_prediction()
    disabled = await agent.predict(DIRECT.pc)
    await agent.set_enabled(True)
    restored = await agent.predict(DIRECT.pc)
    return LookupGateObservation(held, disabled, restored)


async def observe_training_gate(agent) -> TrainingGateObservation:
    await agent.reset()
    cold = await agent.predict(INDIRECT.pc)
    assert_miss(cold)
    await train(agent, INDIRECT, cold.meta_entries)
    before = await agent.predict(INDIRECT.pc)
    assert_vector_hit(before, INDIRECT)
    changed = BranchVector(
        INDIRECT.pc, INDIRECT.target + 0x200, INDIRECT.position, INDIRECT.branch_type
    )

    await agent.set_enabled(False)
    await train(agent, changed, before.meta_entries)
    await agent.set_enabled(True)
    disabled_update = await agent.predict(INDIRECT.pc)
    await train(agent, changed, disabled_update.meta_entries)
    enabled_update = await agent.predict(changed.pc)
    return TrainingGateObservation(before, disabled_update, enabled_update, changed)
