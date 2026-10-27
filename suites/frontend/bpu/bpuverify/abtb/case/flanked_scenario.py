"""An aged full AheadBTB set with two aged neighboring sentinels."""

from __future__ import annotations

from dataclasses import dataclass

from bpuverify.abtb.checker.assertions import age_conditional_to_not_taken
from bpuverify.abtb.checker.assertions import assert_conditional_state
from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import matching_entry
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import BranchVector
from bpuverify.abtb.case.definitions import NUM_WAYS
from bpuverify.abtb.case.definitions import three_set_neighborhood_vectors


BANKS = range(4)
CENTER_SET = 4
FLANK_SETS = (3, 5)


@dataclass(slots=True)
class AgedFlankedSet:
    agent: object
    sentinels: dict[tuple[int, int], tuple[BranchVector, int]]
    center: dict[tuple[int, int], BranchVector]
    expected_taken: dict[tuple[int, int], int]

    @classmethod
    async def prepare(cls, agent) -> "AgedFlankedSet":
        await agent.reset()
        sentinels = {}
        center = {}
        for bank in BANKS:
            for set_index in (FLANK_SETS[0], CENTER_SET, FLANK_SETS[1]):
                count = NUM_WAYS if set_index == CENTER_SET else 1
                for vector in three_set_neighborhood_vectors(
                    bank, set_index, count, center_set=CENTER_SET
                ):
                    cold = await agent.predict(vector.pc, path_hash=bank)
                    assert_miss(cold)
                    assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
                        set_index, 1 << bank
                    )
                    await train_taken(agent, vector, cold.meta)
                    observed = await assert_conditional_state(
                        agent, vector, taken=1, path_hash=bank
                    )
                    way, _ = matching_entry(
                        observed, vector.position, vector.branch_type
                    )
                    if set_index == CENTER_SET:
                        assert (bank, way) not in center
                        center[(bank, way)] = vector
                    else:
                        sentinels[(bank, set_index)] = (vector, way)
            assert {way for resident_bank, way in center if resident_bank == bank} == (
                set(range(NUM_WAYS))
            )

        assert len(center) == len(BANKS) * NUM_WAYS
        assert len(sentinels) == len(BANKS) * len(FLANK_SETS)
        for (bank, _), (vector, _) in sentinels.items():
            current = await assert_conditional_state(
                agent, vector, taken=1, path_hash=bank
            )
            await age_conditional_to_not_taken(
                agent, vector, current, path_hash=bank
            )
        for (bank, _), vector in center.items():
            current = await assert_conditional_state(
                agent, vector, taken=1, path_hash=bank
            )
            await age_conditional_to_not_taken(
                agent, vector, current, path_hash=bank
            )
        state = cls(agent, sentinels, center, {key: 0 for key in center})
        await state.assert_neighborhood()
        return state

    async def assert_neighborhood(self) -> None:
        for (bank, set_index), (vector, way) in self.sentinels.items():
            observed = await assert_conditional_state(
                self.agent, vector, taken=0, path_hash=bank
            )
            assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
                set_index, 1 << bank
            )
            assert sum(entry.valid for entry in observed.entries) == 1
            assert matching_entry(
                observed, vector.position, vector.branch_type
            )[0] == way
        for (bank, way), vector in self.center.items():
            observed = await assert_conditional_state(
                self.agent, vector, taken=self.expected_taken[(bank, way)],
                path_hash=bank,
            )
            assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
                CENTER_SET, 1 << bank
            )
            assert sum(entry.valid for entry in observed.entries) == 1
            assert matching_entry(
                observed, vector.position, vector.branch_type
            )[0] == way

    async def replace_bank(self, bank: int) -> tuple[int, BranchVector]:
        replacement = three_set_neighborhood_vectors(
            bank, CENTER_SET, NUM_WAYS + 1, center_set=CENTER_SET
        )[-1]
        cold = await self.agent.predict(replacement.pc, path_hash=bank)
        assert_miss(cold)
        assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
            CENTER_SET, 1 << bank
        )
        await train_taken(self.agent, replacement, cold.meta)
        current = await assert_conditional_state(
            self.agent, replacement, taken=1, path_hash=bank
        )
        victim_way, _ = matching_entry(
            current, replacement.position, replacement.branch_type
        )
        victim = self.center[(bank, victim_way)]
        assert self.expected_taken[(bank, victim_way)] == 0
        assert_miss(await self.agent.predict(victim.pc, path_hash=bank))
        self.center[(bank, victim_way)] = replacement
        self.expected_taken[(bank, victim_way)] = 1
        await self.assert_neighborhood()
        return victim_way, replacement
