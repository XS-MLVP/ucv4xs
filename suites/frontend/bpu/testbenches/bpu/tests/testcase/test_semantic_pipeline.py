from suites.frontend.bpu.testbenches.bpu.tests.scenarios.pipeline import check_stream
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.pipeline import check_micro_repair
from suites.frontend.bpu.testbenches.bpu.coverage.pipeline import PipelineCoverage
from suites.frontend.bpu.testbenches.shared.env.artifacts import output_directory
from suites.frontend.bpu.testbenches.shared.env.paths import REPO_ROOT
import pytest


@pytest.mark.feature('BPU-INT-076')
async def test_owned_pipeline_checks_backpressure_valid_only_metadata_and_genuine_recovery(bpu_agent):
    coverage = PipelineCoverage('stream')
    try:
        await check_stream(bpu_agent,coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT,'bpu'))


@pytest.mark.feature('BPU-INT-077')
async def test_owned_micro_predictions_corrected_by_middle_stage_preserve_token_history(bpu_agent):
    coverage = PipelineCoverage('repair')
    try:
        await check_micro_repair(bpu_agent,coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT,'bpu'))
