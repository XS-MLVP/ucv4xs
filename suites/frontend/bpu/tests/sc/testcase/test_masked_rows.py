"""Masked way updates must preserve both pending rows and neighbor ways."""

from __future__ import annotations
from bpuverify.common.model.configuration import *

import pytest

from bpuverify.sc.coverage.catalog import sc_masked_rows_coverage_model
from bpuverify.sc.coverage.catalog import write_sc_masked_rows_coverage
from bpuverify.sc.checker.assertions import learn_masked_rows
from bpuverify.sc.case.definitions import MASKED_POSITIONS
from bpuverify.sc.case.definitions import NOT_TAKEN_ATTEMPTS
from bpuverify.common.env.paths import REPO_ROOT


def sample_rows(coverage, phase, snapshots, slots):
    for slot in slots:
        for row, prediction in enumerate(snapshots):
            position = MASKED_POSITIONS[slot]
            coverage.sample({
                "phase": phase,
                "context": row,
                "way": (position % SC_WAYS) ^ (position // SC_WAYS),
                "bias": prediction.meta["scBiasLowerBits"][slot],
            })


@pytest.mark.feature("BPU-SC-018")
async def test_masked_way_updates_preserve_four_pending_rows_and_neighbor_ways(sc_agent):
    coverage = sc_masked_rows_coverage_model()
    cold, adjacent_stages, adjacent_rounds = await learn_masked_rows(
        sc_agent, adjacent=True, limits=(NOT_TAKEN_ATTEMPTS,) * SC_WAYS,
    )
    sample_rows(coverage, "cold", cold, range(SC_WAYS))
    for slot, snapshots in enumerate(adjacent_stages):
        sample_rows(coverage, "adjacent_learned", snapshots, (slot,))

    serial_cold, serial_stages, serial_rounds = await learn_masked_rows(
        sc_agent, adjacent=False, limits=adjacent_rounds,
    )
    assert serial_cold == cold
    for slot, (serial, adjacent) in enumerate(zip(serial_stages, adjacent_stages, strict=True)):
        assert serial_rounds[slot] <= adjacent_rounds[slot]
        for actual, expected in zip(serial, adjacent, strict=True):
            assert (actual.useds, actual.takens) == (expected.useds, expected.takens)
        sample_rows(coverage, "serial_control", serial, (slot,))
    coverage.assert_coverage(100.0)
    write_sc_masked_rows_coverage(coverage, REPO_ROOT)
