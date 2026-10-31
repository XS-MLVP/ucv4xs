"""SC correction selects the executed prefix; all timing stays in the agent/env."""
import json

import pytest

from suites.frontend.bpu.bpu.case.statistical_prefix import run
from suites.frontend.bpu.bpu.coverage.statistical_prefix import Coverage
from suites.frontend.bpu.bpu.model.statistical_prefix import PROFILES


@pytest.mark.feature('BPU-INT-032')
@pytest.mark.feature('BPU-INT-043')
@pytest.mark.feature('BPU-INT-060')
@pytest.mark.parametrize('profile', PROFILES)
async def test_SC_correction_owns_executed_prefix_and_original_feedback(bpu_agent, bpu_sc_output, request, profile):
    coverage, evidence = Coverage(profile), {}
    try:
        await run(bpu_agent, profile, coverage, evidence)
    finally:
        request.node.user_properties.append(('semantic_bpu_statistical_prefix', json.dumps(evidence, sort_keys=True)))
        coverage.write(bpu_sc_output)


from suites.frontend.bpu.bpu.case.statistical_prefix import run_context
from suites.frontend.bpu.bpu.coverage.statistical_prefix import ContextCoverage
from suites.frontend.bpu.bpu.model.statistical_prefix import CONTEXT_PROFILES


@pytest.mark.feature('BPU-INT-042')
@pytest.mark.feature('BPU-INT-043')
@pytest.mark.feature('BPU-INT-060')
@pytest.mark.feature('BPU-INT-061')
@pytest.mark.parametrize('profile',CONTEXT_PROFILES)
async def test_SC_learns_original_nonzero_context_and_new_prediction_consumes_it(bpu_agent,bpu_sc_output,request,profile):
    coverage,evidence=ContextCoverage(profile),{}
    try:
        await run_context(bpu_agent,profile,coverage,evidence)
    finally:
        request.node.user_properties.append(('semantic_bpu_sc_context_learning',json.dumps(evidence,sort_keys=True)))
        coverage.write(bpu_sc_output)


from suites.frontend.bpu.bpu.case.statistical_prefix import run_concurrent_context
from suites.frontend.bpu.bpu.coverage.statistical_prefix import ConcurrentContextCoverage
from suites.frontend.bpu.bpu.model.statistical_prefix import CONCURRENT_CONTEXT_PROFILES

# Measured on the 2026-10-21 full BPU program run; scheduling hint only.
pytestmark = pytest.mark.estimated_runtime(29)


@pytest.mark.feature('BPU-INT-042')
@pytest.mark.feature('BPU-INT-043')
@pytest.mark.feature('BPU-INT-061')
@pytest.mark.parametrize('profile',CONCURRENT_CONTEXT_PROFILES)
async def test_old_nonzero_context_learns_once_while_unrelated_predictions_continue(bpu_agent,bpu_sc_output,request,profile):
    coverage,evidence=ConcurrentContextCoverage(profile),{}
    try:
        await run_concurrent_context(bpu_agent,profile,coverage,evidence)
    finally:
        request.node.user_properties.append(('semantic_bpu_sc_concurrent_context',json.dumps(evidence,sort_keys=True)))
        coverage.write(bpu_sc_output)
