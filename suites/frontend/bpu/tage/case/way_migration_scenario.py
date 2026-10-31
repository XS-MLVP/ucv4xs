"""Real provider-way migration, accepted feedback, and neighbor preservation."""
from suites.frontend.bpu.models.configuration import *

from suites.frontend.bpu.tage.transaction.types import TageTraining
from suites.frontend.bpu.tage.checker.assertions import fill_useful_set
from suites.frontend.bpu.tage.case.definitions import HIGHEST_TABLE
from suites.frontend.bpu.tage.case.definitions import USEFUL_RESET_COUNTER_MAX


class MisassociatedProviderUseful(AssertionError):
    """Captured provider-way metadata modifies another tag's useful state."""


def as_misassociated_useful(error):
    """Re-label only the known useful-only mismatch detected by the reference.

    The independent semantic checker can observe the captured-way defect one
    boundary before this scenario finishes its own matrix. Only an all-useful
    difference set is re-labelled; any other mismatch returns None so the
    caller re-raises the original object, preserving ordinary failure.
    """

    differences = tuple(getattr(error, "differences", ()))
    paths = tuple(str(getattr(item, "path", "")) for item in differences)
    if not differences or not all(path.endswith("useful") for path in paths):
        return None
    return MisassociatedProviderUseful(
        f"semantic reference detected the captured-way useful misassociation first: {paths}"
    )


def cell(prediction):
    assert prediction.meta["hasProvider"] == 1, prediction
    return prediction.meta["providerTableIdx"], prediction.meta["providerWayIdx"]


def snapshot(prediction):
    # Only slot zero belongs to this scalar request. Invalid other slots can
    # still expose tags of other positions and are not part of its response.
    return {"valid": prediction.valid, "taken": prediction.taken,
            "provider_counter_valid": prediction.provider_counter_valid, "meta": prediction.meta}


async def read_grid(agent, pc, *, repeated=False, positions=tuple(range((2 * TAGE_TABLES + 2)))):
    coordinates = list(positions)
    if repeated:
        coordinates += list(reversed(coordinates))
    transfers = [agent.submit_predict(pc, position, 0) for position in coordinates]
    await agent.drain_predictions()
    ticks = [transfer.accepted_event.tick for transfer in transfers]
    assert ticks == list(range(ticks[0], ticks[0] + 2 * len(ticks), 2)), ticks
    assert [transfer.completed_event.tick for transfer in transfers] == [tick + 4 for tick in ticks]
    predictions = {}
    for position, transfer in zip(coordinates, transfers, strict=True):
        prediction = await transfer
        if position in predictions:
            assert snapshot(prediction) == snapshot(predictions[position]), (pc, position, prediction)
        predictions[position] = prediction
    residents = {position: prediction for position, prediction in predictions.items()
                 if prediction.meta["hasProvider"]}
    assert len(residents) == len({cell(p) for p in residents.values()}) == 2 * TAGE_TABLES, (pc, residents)
    return residents


async def protect(agent, pc, position, before, send):
    for _ in range(5):
        prediction = await agent.predict(pc, position, 0)
        assert cell(prediction) == cell(before), (pc, position, before, prediction)
        if prediction.meta["providerUsefulCtr_value"] == 3:
            return prediction
        await send(TageTraining(pc, position, 1, 0, prediction.meta,
                   mispredict=int((prediction.taken if prediction.valid else 0) != 1)))
    raise AssertionError(("useful protection failed", pc, position, prediction))


async def set_unprotected_counter(agent, pc, position, expected_cell, counter):
    for _ in range(5):
        prediction = await agent.predict(pc, position, 1, base_conf=1)
        assert cell(prediction) == expected_cell, (pc, position, prediction)
        assert prediction.meta["providerUsefulCtr_value"] == 0, prediction
        if prediction.meta["providerTakenCtr_value"] == counter:
            return
        assert prediction.meta["providerTakenCtr_value"] < counter, prediction
        await agent.train(TageTraining(pc, position, 1, 1, prediction.meta, mispredict=0))
    raise AssertionError(("unprotected counter did not converge", pc, position, counter, prediction))


async def prepare_unprotected_highest_ways(agent, pc, origin_way):
    await agent.reset()
    await fill_useful_set(agent, pc=pc)
    cold = await agent.predict(pc, 2 * TAGE_TABLES, 0)
    assert cold.meta["hasProvider"] == 0, cold
    for attempt in range(USEFUL_RESET_COUNTER_MAX + 6):
        await agent.train(TageTraining(pc, 2 * TAGE_TABLES, 1, 0, cold.meta, mispredict=1))
        newcomer = await agent.predict(pc, 2 * TAGE_TABLES, 0)
        if newcomer.meta["hasProvider"]:
            assert attempt + 1 > USEFUL_RESET_COUNTER_MAX, (pc, attempt, newcomer)
            break
    else:
        raise AssertionError(("useful reset did not release the full set", pc, newcomer))
    # Set zero can reopen before the 128-set useful clear finishes. Sixteen
    # pipelined, read-only all-grid rounds give the existing sweep time to
    # finish before any reinforcement; no reset occurs after capture.
    for _ in range((TAGE_ROWS + 2 * TAGE_TABLES) // (2 * TAGE_TABLES + 1)):
        residents = await read_grid(agent, pc, positions=tuple(range((2 * TAGE_TABLES + 1))))
    assert all(p.meta["providerUsefulCtr_value"] == 0 for p in residents.values()), residents
    for position, prediction in residents.items():
        if cell(prediction)[0] != HIGHEST_TABLE:
            await protect(agent, pc, position, prediction, agent.train)
    original_position = next(pos for pos, p in residents.items() if cell(p) == (HIGHEST_TABLE, origin_way))
    other_position = next(pos for pos, p in residents.items() if cell(p) == (HIGHEST_TABLE, 1 - origin_way))
    await set_unprotected_counter(agent, pc, other_position, (HIGHEST_TABLE, 1 - origin_way), 7)
    await set_unprotected_counter(agent, pc, original_position, (HIGHEST_TABLE, origin_way), 5)
    return original_position


async def check_way_migration(agent, coverage, *, pc, context, origin_way, mode):
    original_position = await prepare_unprotected_highest_ways(agent, pc, origin_way)
    async with agent.observe_training() as observed:
        async def send(transaction):
            first = len(observed)
            await agent.train(transaction)
            samples = observed[first:]
            assert len(samples) == 1, ("feedback beat count", transaction, samples)
            actual = samples[0].value
            assert actual["ready"] == 1, ("feedback not accepted", samples[0])
            assert actual["bits"]["start_pc"] == transaction.pc, (transaction, samples[0])
            assert actual["bits"]["tage_meta"][0] == transaction.meta, (
                "genuine captured metadata changed on the wire", transaction, samples[0],
            )
            branches = [branch for branch in actual["bits"]["branches"] if branch["valid"]]
            assert len(branches) == 1 and (
                branches[0]["position"], branches[0]["taken"], branches[0]["mispredict"],
            ) == (transaction.position, transaction.actual_taken, transaction.mispredict), (
                "resolved branch identity changed on the wire", transaction, samples[0],
            )
            assert actual["bits"] == agent.encode_training(transaction), (
                "accepted feedback identity/metadata", transaction, samples[0],
            )

        capture = agent.submit_predict(pc, original_position, 0)
        captured = await capture
        assert cell(captured) == (HIGHEST_TABLE, origin_way), captured
        assert (captured.valid, captured.taken, captured.meta["useProvider"]) == (1, 1, 1), captured
        assert (captured.meta["providerTakenCtr_value"], captured.meta["providerUsefulCtr_value"],
                captured.meta["altOrBasePred"], captured.meta["hasAlt"]) == (5, 0, 0, 0), captured

        weakener = await agent.predict(pc, original_position, 0)
        await send(TageTraining(pc, original_position, 0, 0, weakener.meta, mispredict=1))
        weakened = await agent.predict(pc, original_position, 0)
        assert cell(weakened) == (HIGHEST_TABLE, origin_way)
        assert (weakened.meta["providerTakenCtr_value"], weakened.meta["providerUsefulCtr_value"]) == (4, 0)
        cold = await agent.predict(pc, (2 * TAGE_TABLES + 1), 0)
        assert cold.meta["hasProvider"] == 0, cold
        await send(TageTraining(pc, (2 * TAGE_TABLES + 1), 1, 0, cold.meta, mispredict=1))
        replacement = await agent.predict(pc, (2 * TAGE_TABLES + 1), 0)
        assert cell(replacement) == (HIGHEST_TABLE, origin_way), replacement
        assert (await agent.predict(pc, original_position, 0)).meta["hasProvider"] == 0
        await protect(agent, pc, (2 * TAGE_TABLES + 1), replacement, send)
        missing = await agent.predict(pc, original_position, 0)
        assert missing.meta["hasProvider"] == 0, missing
        await send(TageTraining(pc, original_position, 1, 0, missing.meta, mispredict=1))
        migrated = await agent.predict(pc, original_position, 0)
        assert cell(migrated) == (HIGHEST_TABLE, 1 - origin_way), migrated
        assert (migrated.valid, migrated.taken) == (1, 1), migrated
        before = await read_grid(agent, pc)
        assert (before[original_position].meta["providerTakenCtr_value"],
                before[original_position].meta["providerUsefulCtr_value"]) == (4, 0)
        assert (before[(2 * TAGE_TABLES + 1)].meta["providerTakenCtr_value"], before[(2 * TAGE_TABLES + 1)].meta["providerUsefulCtr_value"]) == (7, 3)
        failures = []
        phases = {}

        def check_phase(predictions, phase):
            target, neighbor = predictions[original_position], predictions[(2 * TAGE_TABLES + 1)]
            state = (pc, context, origin_way, mode, phase, target, neighbor)
            assert set(predictions) == set(before), state
            assert cell(target) == (HIGHEST_TABLE, 1 - origin_way), state
            assert cell(neighbor) == (HIGHEST_TABLE, origin_way), state
            assert (target.valid, target.taken, neighbor.valid, neighbor.taken) == (1, 1, 1, 1), state
            counter = 4 if phase == "migrated" else 5
            assert target.meta["providerTakenCtr_value"] == counter, state
            assert neighbor.meta["providerTakenCtr_value"] == 7, state
            # A stale useful update may be dropped or redirected to the
            # current tag. It must not modify the unrelated resident tag.
            allowed_useful = (0,) if phase == "migrated" else ((0, 1) if mode == "captured" else (1,))
            assert target.meta["providerUsefulCtr_value"] in allowed_useful, state
            for position in before:
                if position not in (original_position, (2 * TAGE_TABLES + 1)):
                    assert snapshot(predictions[position]) == snapshot(before[position]), (state, position)
            old_neighbor_meta = {k: v for k, v in before[(2 * TAGE_TABLES + 1)].meta.items() if k != "providerUsefulCtr_value"}
            assert {k: v for k, v in neighbor.meta.items() if k != "providerUsefulCtr_value"} == old_neighbor_meta, state
            actual_useful = neighbor.meta["providerUsefulCtr_value"]
            neighbor_held = actual_useful == 3
            if not neighbor_held:
                assert mode == "captured" and phase != "migrated" and actual_useful == 1, state
                failures.append({"pc": pc, "context": context, "origin_way": origin_way, "phase": phase,
                    "neighbor_position": (2 * TAGE_TABLES + 1), "expected_useful": 3, "actual_useful": actual_useful,
                    "neighbor_before": snapshot(before[(2 * TAGE_TABLES + 1)]), "neighbor_after": snapshot(neighbor),
                    "target_after": snapshot(target)})
            for check in ("target_counter", "target_useful", "neighbor_counter", "neighbor_useful", "other_neighbors"):
                if check != "neighbor_useful" or neighbor_held:
                    coverage.sample({"context": context, "origin_way": origin_way, "phase": phase, "check": check})
            phases[phase] = {"target": snapshot(target), "neighbor": snapshot(neighbor), "six_neighbors_held": True}

        check_phase(before, "migrated")
        training_meta = captured.meta if mode == "captured" else migrated.meta
        await send(TageTraining(pc, original_position, 1, 0, training_meta, mispredict=0))
        assert len(observed) == 7, ("bounded feedback lifetime", pc, origin_way, observed)
        check_phase(await read_grid(agent, pc), "feedback")
        check_phase(await read_grid(agent, pc, repeated=True), "mixed_pipeline")
        return {"pc": pc, "context": context, "origin_way": origin_way, "destination_way": 1 - origin_way,
            "mode": mode, "original_position": original_position,
            "captured_prediction": snapshot(captured), "migrated_prediction": snapshot(migrated),
            "capture_tick": capture.completed_event.tick, "last_feedback_tick": observed[-1].event.tick,
            "accepted_feedback_count_after_capture": len(observed),
            "actual_last_feedback": observed[-1].value, "phases": phases, "mismatches": failures}
