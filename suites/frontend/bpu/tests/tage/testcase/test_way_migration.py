"""Distinguish fresh provider feedback from stale physical-way association."""

from suites.frontend.bpu.runtime.artifacts import output_path
from suites.frontend.bpu.runtime.artifacts import write_output

import json

import pytest
from toffee import ScoreboardMismatch

from suites.frontend.bpu.tage.coverage.catalog import tage_way_migration_coverage_model
from suites.frontend.bpu.tage.coverage.catalog import write_tage_way_migration_coverage
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.tage.case.definitions import SAME_BANK_PCS
from suites.frontend.bpu.tage.case.way_migration_scenario import MisassociatedProviderUseful
from suites.frontend.bpu.tage.case.way_migration_scenario import as_misassociated_useful
from suites.frontend.bpu.tage.case.way_migration_scenario import check_way_migration


async def run_matrix(agent, coverage, mode):
    return [await check_way_migration(agent, coverage, pc=pc, context=context, origin_way=way, mode=mode)
            for context, pc in enumerate(SAME_BANK_PCS) for way in range(2)]


@pytest.mark.feature("BPU-TAGE-025")
async def test_fresh_feedback_after_way_migration_preserves_all_neighbors(tage_agent):
    coverage = tage_way_migration_coverage_model("current")
    matrix = await run_matrix(tage_agent, coverage, "current")
    assert all(not case["mismatches"] for case in matrix), matrix
    coverage.assert_coverage(100.0)
    write_tage_way_migration_coverage(coverage, REPO_ROOT, "current")


@pytest.mark.feature("BPU-TAGE-026")
@pytest.mark.rtl_defect
@pytest.mark.xfail(strict=True, raises=MisassociatedProviderUseful,
    reason="Captured TAGE provider way can misassociate useful feedback after its tag migrates")
async def test_captured_feedback_after_way_migration_preserves_unrelated_tag_useful(tage_agent):
    coverage = tage_way_migration_coverage_model("captured")
    try:
        matrix = await run_matrix(tage_agent, coverage, "captured")
    except ScoreboardMismatch as error:
        # The independent semantic reference can detect the same captured-way
        # useful misassociation before this scenario finishes collecting its
        # own matrix. Convert only that exact failure shape; any other
        # mismatch must stay an ordinary failure.
        translated = as_misassociated_useful(error)
        if translated is None:
            raise
        raise translated from error
    failures = [failure for case in matrix for failure in case["mismatches"]]
    write_tage_way_migration_coverage(coverage, REPO_ROOT, "captured")
    report = {"feature": "BPU-TAGE-026", "status": "KNOWN_FAIL" if failures else "PASS",
              "scope": "single-module feedback; no integrated FTQ reachability claim",
              "matrix": matrix, "mismatches": failures}
    write_output(REPO_ROOT / "results" / "tage" / "way-migration-known-fail.json",
        json.dumps(report, indent=2, sort_keys=True) + "\n")
    if failures:
        raise MisassociatedProviderUseful(
            f"{len(failures)} neighbor useful mismatches in complete eight-case matrix; first: {failures[0]!r}")
    coverage.assert_coverage(100.0)
