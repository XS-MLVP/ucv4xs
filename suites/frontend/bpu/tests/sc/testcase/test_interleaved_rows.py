"""Opposite SC directions must stay associated with four pending indices."""

from __future__ import annotations

import pytest

from bpuverify.sc.coverage.catalog import sc_interleaved_rows_coverage_model
from bpuverify.sc.coverage.catalog import write_sc_interleaved_rows_coverage
from bpuverify.sc.checker.assertions import learn_interleaved_rows
from bpuverify.sc.checker.assertions import sc_row_indices
from bpuverify.sc.case.definitions import NOT_TAKEN_ATTEMPTS
from bpuverify.sc.case.definitions import POSITION
from bpuverify.sc.case.definitions import SAME_BANK_PCS
from bpuverify.common.env.paths import REPO_ROOT


OUTCOMES = (0, 1, 0, 1)
CONTEXTS = tuple((pc, POSITION, outcome) for pc, outcome in zip(SAME_BANK_PCS, OUTCOMES))


def require_learned(prediction, outcome):
    assert prediction.meta["tagePredValid"][0] == 1, prediction
    assert prediction.meta["scPred"][0] == outcome, prediction
    assert (prediction.used, prediction.taken) == (1, outcome), prediction


@pytest.mark.feature("BPU-SC-017")
async def test_four_interleaved_rows_learn_opposite_sc_directions(sc_agent):
    coverage = sc_interleaved_rows_coverage_model()
    adjacent_rounds, cold, adjacent_results = await learn_interleaved_rows(
        sc_agent, CONTEXTS, adjacent=True, limit=NOT_TAKEN_ATTEMPTS,
    )
    routes = tuple(map(sc_row_indices, cold))
    # Public metadata proves all five table families use four distinct rows;
    # opposite outputs alone would not prove the pending-index premise.
    for table_rows in zip(*routes):
        assert len(set(table_rows)) == 4, routes
    for index, prediction in enumerate(cold):
        assert prediction.meta["tagePredValid"][0] == 1, prediction
        assert prediction.meta["scPred"][0] == 1, prediction
        assert (prediction.used, prediction.taken) == (0, 1), prediction
        coverage.sample({"phase": "cold", "context": index})
    for index, (prediction, outcome) in enumerate(zip(adjacent_results, OUTCOMES)):
        assert sc_row_indices(prediction) == routes[index], prediction
        require_learned(prediction, outcome)
        coverage.sample({"phase": "adjacent_learned", "context": index})

    serial_rounds, serial_cold, serial_results = await learn_interleaved_rows(
        sc_agent, CONTEXTS, adjacent=False, limit=adjacent_rounds,
    )
    assert serial_cold == cold
    # SC may read stale SRAM during a burst. Require all four contexts to
    # converge, but do not claim an independent accumulated update per beat.
    assert serial_rounds <= adjacent_rounds
    for index, (prediction, outcome) in enumerate(zip(serial_results, OUTCOMES)):
        assert sc_row_indices(prediction) == routes[index], prediction
        require_learned(prediction, outcome)
        assert (prediction.used, prediction.taken) == (
            adjacent_results[index].used, adjacent_results[index].taken,
        )
        coverage.sample({"phase": "serial_control", "context": index})
    coverage.assert_coverage(100.0)
    write_sc_interleaved_rows_coverage(coverage, REPO_ROOT)
