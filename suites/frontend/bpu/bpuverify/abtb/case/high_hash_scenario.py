"""Reusable full-way same-PC grid across high hash-selected bank/set cells."""

from __future__ import annotations

from dataclasses import dataclass

from bpuverify.abtb.checker.assertions import assert_miss
from bpuverify.abtb.checker.assertions import assert_position_profile
from bpuverify.abtb.checker.assertions import fill_taken_position_set
from bpuverify.abtb.checker.assertions import matching_entry
from bpuverify.abtb.checker.assertions import maybe_matching_entry
from bpuverify.abtb.checker.assertions import train_conditional_direction
from bpuverify.abtb.checker.assertions import train_taken
from bpuverify.abtb.case.definitions import BranchVector
from bpuverify.abtb.case.definitions import HASH_SET_PC
from bpuverify.abtb.case.definitions import NUM_WAYS


SETS = range(48, 52)
BANKS = range(4)
ROUTES = tuple((set_index, bank) for set_index in SETS for bank in BANKS)
PC = HASH_SET_PC + 2 * SETS.start


def path_hash(route: tuple[int, int]) -> int:
    set_index, bank = route
    return ((set_index - SETS.start) << 2) | bank


def route_name(route: tuple[int, int]) -> str:
    set_index, bank = route
    return f"set_{set_index}_bank_{bank}"


@dataclass(slots=True)
class HighHashFullWayGrid:
    agent: object
    vectors: dict[tuple[int, int], tuple[BranchVector, ...]]
    expected: dict[tuple[int, int], dict[int, tuple[BranchVector, int, int]]]
    evicted: dict[tuple[int, int], list[BranchVector]]

    @classmethod
    async def prepare(cls, agent) -> "HighHashFullWayGrid":
        await agent.reset()
        vectors = {}
        expected = {}
        for route in ROUTES:
            set_index, bank = route
            profile = tuple(
                BranchVector(
                    pc=PC,
                    target=0x4020_0000 + path_hash(route) * 0x100
                    + position_index * 0x20,
                    position=1 + position_index * 2,
                    branch_type=1,
                )
                for position_index in range(NUM_WAYS)
            )
            cold = await agent.predict(PC, path_hash=path_hash(route))
            assert_miss(cold)
            assert (cold.meta["setIdx"], cold.meta["bankMask"]) == (
                set_index, 1 << bank
            )
            full, by_position = await fill_taken_position_set(
                agent, profile, path_hash=path_hash(route)
            )
            assert (full.meta["setIdx"], full.meta["bankMask"]) == (
                set_index, 1 << bank
            )
            vectors[route] = profile
            expected[route] = {
                vector.position: (vector, by_position[vector.position], 1)
                for vector in profile
            }
        state = cls(agent, vectors, expected, {route: [] for route in ROUTES})
        await state.assert_grid()
        return state

    async def assert_grid(self) -> None:
        for route in ROUTES:
            set_index, bank = route
            observed = await self.agent.predict(PC, path_hash=path_hash(route))
            assert (observed.meta["setIdx"], observed.meta["bankMask"]) == (
                set_index, 1 << bank
            )
            assert_position_profile(observed, self.expected[route])
            for victim in self.evicted[route]:
                assert maybe_matching_entry(
                    observed, victim.position, victim.branch_type
                ) is None

    async def age_route(self, route: tuple[int, int]) -> None:
        current = await self.agent.predict(PC, path_hash=path_hash(route))
        await train_conditional_direction(
            self.agent, self.vectors[route][0], current, taken=0
        )
        self.expected[route] = {
            position: (vector, way, 0)
            for position, (vector, way, _) in self.expected[route].items()
        }
        await self.assert_grid()

    async def recover_position(
        self, route: tuple[int, int], vector: BranchVector
    ) -> int:
        current = await self.agent.predict(PC, path_hash=path_hash(route))
        await train_taken(self.agent, vector, current.meta)
        self.expected[route] = {
            position: (resident, way, int(position == vector.position))
            for position, (resident, way, _) in self.expected[route].items()
        }
        await self.assert_grid()
        return self.expected[route][vector.position][1]

    async def replace_route(self, route: tuple[int, int]) -> int:
        newcomer = BranchVector(
            pc=PC,
            target=0x4020_0000 + path_hash(route) * 0x100 + NUM_WAYS * 0x20,
            position=1 + NUM_WAYS * 2,
            branch_type=1,
        )
        before = await self.agent.predict(PC, path_hash=path_hash(route))
        await train_taken(self.agent, newcomer, before.meta)
        after = await self.agent.predict(PC, path_hash=path_hash(route))
        new_way, entry = matching_entry(
            after, newcomer.position, newcomer.branch_type
        )
        assert (entry.taken, entry.target) == (1, newcomer.target)

        survivors = {}
        victims = []
        for position, (resident, way, _) in self.expected[route].items():
            match = maybe_matching_entry(
                after, resident.position, resident.branch_type
            )
            if match is None:
                victims.append((resident, way))
            else:
                assert match[0] == way
                survivors[position] = (resident, way, 0)
        assert len(victims) == 1
        victim, victim_way = victims[0]
        assert victim_way == new_way
        assert len(survivors) == NUM_WAYS - 1
        self.evicted[route].append(victim)
        self.expected[route] = {
            **survivors,
            newcomer.position: (newcomer, new_way, 1),
        }
        await self.assert_grid()
        return victim_way
