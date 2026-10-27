from __future__ import annotations

from collections import Counter

from bpuverify.tage.transaction.types import TageTraining
from bpuverify.tage.case.definitions import HIGHEST_TABLE
from bpuverify.tage.case.definitions import PC
from bpuverify.tage.case.definitions import POSITION
from bpuverify.tage.case.definitions import PRESSURE_POSITION
from bpuverify.tage.case.definitions import TAGGED_TABLES
from bpuverify.tage.case.definitions import USEFUL_RESET_COUNTER_MAX
from bpuverify.tage.case.definitions import USEFUL_SET_POSITIONS
from bpuverify.tage.case.definitions import WAYS_PER_TABLE


def provider_counter(prediction) -> int:
    return prediction.meta["providerTakenCtr_value"]


def require_provider(prediction) -> None:
    assert prediction.meta["hasProvider"] == 1, prediction


def require_miss(prediction) -> None:
    assert prediction.meta["hasProvider"] == 0, prediction


def provider_depth(prediction) -> str:
    if not prediction.meta["hasProvider"]:
        return "none"
    if prediction.meta["providerTableIdx"] == HIGHEST_TABLE:
        return "highest"
    return "nonhighest"


async def allocate_weak_pair_in_one_table(agent, outcomes: tuple[int, ...], desired: tuple[int, int]):
    """Allocate two ordered weak providers in distinct ways of one table."""

    prior = []
    for position, taken in enumerate(outcomes):
        assert taken in (0, 1)
        base = 1 - taken
        cold = await agent.predict(PC, position, base, base_conf=1)
        require_miss(cold)
        await agent.train(TageTraining(PC, position, taken, base, cold.meta))
        weak = await agent.predict(PC, position, base, base_conf=1)
        require_provider(weak)
        assert provider_counter(weak) == (4 if taken else 3)
        if taken == desired[1]:
            for candidate, prior_taken in prior:
                if prior_taken != desired[0]:
                    continue
                earlier = await agent.predict(PC, candidate, 1 - prior_taken, base_conf=1)
                if (
                    earlier.meta["hasProvider"]
                    and provider_counter(earlier) == (4 if prior_taken else 3)
                    and earlier.meta["providerTableIdx"] == weak.meta["providerTableIdx"]
                    and earlier.meta["providerWayIdx"] != weak.meta["providerWayIdx"]
                ):
                    return candidate, position
        prior.append((position, taken))
    raise AssertionError(f"no ordered weak TAGE pair for {desired=} in {outcomes=}")


async def allocate(agent):
    cold = await agent.predict(PC, POSITION, 0)
    await agent.train(TageTraining(PC, POSITION, 1, 0, cold.meta))
    prediction = await agent.predict(PC, POSITION, 0)
    assert prediction.meta["hasProvider"] == 1
    return prediction


async def reach_highest_provider(agent, *, pc: int = PC, position: int = POSITION):
    """Escalate through real mispredictions until no longer-history table exists."""

    prediction = await agent.predict(pc, position, 0)
    for _ in range(12):
        if (
            prediction.meta["hasProvider"]
            and prediction.meta["providerTableIdx"] == HIGHEST_TABLE
        ):
            return prediction
        actual_taken = 1 - prediction.taken
        await agent.train(
            TageTraining(pc, position, actual_taken, 0, prediction.meta, 1)
        )
        prediction = await agent.predict(pc, position, 0)
    raise AssertionError(f"highest TAGE table not reached: {prediction!r}")


async def prepare_highest_provider(agent, *, pc: int, position: int, taken: int):
    """A strong highest-table provider cannot allocate a longer replacement."""

    highest = await reach_highest_provider(agent, pc=pc, position=position)
    cell = highest.meta["providerTableIdx"], highest.meta["providerWayIdx"]
    counter = 5 if taken else 2
    for _ in range(8):
        prediction = await agent.predict(pc, position, taken)
        assert (prediction.meta["providerTableIdx"], prediction.meta["providerWayIdx"]) == cell
        if provider_counter(prediction) == counter and (prediction.valid, prediction.taken) == (1, taken):
            return prediction
        observed = prediction.taken if prediction.valid else taken
        await agent.train(TageTraining(
            pc, position, taken, taken, prediction.meta,
            mispredict=int(observed != taken),
        ))
    raise AssertionError(f"highest provider did not reach {counter=}: {prediction!r}")


async def fill_useful_set(agent, *, pc: int = PC):
    """Use real predictions to occupy both ways of every table at one index."""

    for position in USEFUL_SET_POSITIONS:
        cold = await agent.predict(pc, position, 0)
        require_miss(cold)
        await agent.train(TageTraining(pc, position, 1, 0, cold.meta, 1))
        allocated = await agent.predict(pc, position, 0)
        require_provider(allocated)

        # The weak taken provider can lose to the not-taken base. Correct
        # training still raises its useful counter without replacing it.
        await agent.train(
            TageTraining(
                pc, position, 1, 0, allocated.meta,
                mispredict=int((allocated.taken if allocated.valid else 0) != 1),
            )
        )
        strengthened = await agent.predict(pc, position, 0)
        require_provider(strengthened)
        assert strengthened.meta["providerUsefulCtr_value"] > 0
        assert strengthened.meta["providerTakenCtr_value"] >= 5

    residents = {
        position: await agent.predict(pc, position, 0)
        for position in USEFUL_SET_POSITIONS
    }
    assert Counter(
        prediction.meta["providerTableIdx"] for prediction in residents.values()
    ) == Counter({table: WAYS_PER_TABLE for table in range(TAGGED_TABLES)})
    assert all(
        prediction.meta["hasProvider"]
        and prediction.meta["providerUsefulCtr_value"] > 0
        for prediction in residents.values()
    )
    return residents


async def train_until_useful_reset_reopens_set(agent, prediction, *, already_failed: int):
    """Keep a new branch blocked until the 8-bit reset counter releases it."""

    require_miss(prediction)
    if already_failed < 0:
        raise ValueError("already_failed must be nonnegative")
    for attempt in range(already_failed + 1, USEFUL_RESET_COUNTER_MAX + 6):
        await agent.train(
            TageTraining(PC, PRESSURE_POSITION, 1, 0, prediction.meta, 1)
        )
        prediction = await agent.predict(PC, PRESSURE_POSITION, 0)
        if prediction.meta["hasProvider"]:
            assert attempt > USEFUL_RESET_COUNTER_MAX
            return attempt, prediction
        require_miss(prediction)
    raise AssertionError("TAGE useful reset did not reopen the full set")
