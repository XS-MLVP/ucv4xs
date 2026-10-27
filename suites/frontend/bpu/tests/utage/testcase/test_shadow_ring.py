"""Separate bypass correctness from SRAM persistence, without hiding either."""

from __future__ import annotations
import ucv.runtime as ucv_paths

from bpuverify.common.env.artifacts import output_path
from bpuverify.common.env.artifacts import write_output

import json

import pytest

from bpuverify.utage.coverage.catalog import utage_shadow_ring_coverage_model
from bpuverify.utage.coverage.catalog import write_utage_shadow_ring_coverage
from bpuverify.utage.coverage.catalog import utage_shadow_persistence_coverage_model
from bpuverify.utage.coverage.catalog import write_utage_shadow_persistence_coverage
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.case.shadow_ring_scenario import LostShadowWriteback
from bpuverify.utage.case.shadow_ring_scenario import check_shadow_eviction
from bpuverify.utage.case.shadow_ring_scenario import check_shadow_ring_mode


@pytest.mark.feature("BPU-UTAGE-015")
async def test_both_tables_keep_eight_rows_through_immediate_bypass_and_ring_wrap(utage_agent):
    coverage = utage_shadow_ring_coverage_model()
    for table in range(2):
        for bank in range(4):
            adjacent = await check_shadow_ring_mode(utage_agent, coverage, table=table, bank=bank, adjacent=True)
            serial = await check_shadow_ring_mode(utage_agent, coverage, table=table, bank=bank, adjacent=False)
            assert serial.stages == adjacent.stages, (table, bank, serial.stages, adjacent.stages)
    coverage.assert_coverage(100.0)
    write_utage_shadow_ring_coverage(coverage, REPO_ROOT)


@pytest.mark.feature("BPU-UTAGE-016")
@pytest.mark.rtl_defect
@pytest.mark.xfail(
    strict=True,
    raises=LostShadowWriteback,
    reason="MicroTAGE ring-slot reuse can clear the newly enqueued dirty entry before SRAM writeback",
)
async def test_saturated_rows_survive_full_shadow_replacement_in_both_tables_and_all_banks(utage_agent):
    coverage = utage_shadow_persistence_coverage_model()
    failures = []
    matrix = []
    for table in range(2):
        for bank in range(4):
            for adjacent in (True, False):
                # All bypass, metadata, latency and new-row preconditions are
                # ordinary assertions, not the exception caught by XFAIL.
                run = await check_shadow_ring_mode(
                    utage_agent, utage_shadow_ring_coverage_model(),
                    table=table, bank=bank, adjacent=adjacent,
                )
                states, mismatches = await check_shadow_eviction(
                    utage_agent, coverage, run, table=table, bank=bank, adjacent=adjacent,
                )
                failures.extend(mismatches)
                matrix.append({
                    "table": table, "bank": bank, "mode": "adjacent" if adjacent else "serial",
                    "after_counters": [state[-1] for state in states], "mismatch_count": len(mismatches),
                })
    write_utage_shadow_persistence_coverage(coverage, REPO_ROOT)
    result = {
        "status": "KNOWN_FAIL" if failures else "PASS", "dut": "MicroTage",
        "feature": "BPU-UTAGE-016", "matrix": matrix, "mismatches": failures,
        "rtl": str(REPO_ROOT / "rtl" / "utage" / "BypassShadowBuffer.sv"),
        "scala": str(ucv_paths.source_path_for(ROOT) / "src" / "main" / "scala" / "xiangshan"
                     / "frontend" / "bpu" / "utage" / "BypassShadowBuffer.scala"),
        "declared_allowances": list(utage_agent.allowed_reference_events),
    }
    write_output(REPO_ROOT / "results" / "utage" / "shadow-persistence-known-fail.json",
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    if failures:
        raise LostShadowWriteback(
            f"{len(failures)}/128 saturated counters changed after shadow replacement; "
            f"complete table/bank/mode matrix: {matrix!r}; first mismatch: {failures[0]!r}"
        )
    coverage.assert_coverage(100.0)
