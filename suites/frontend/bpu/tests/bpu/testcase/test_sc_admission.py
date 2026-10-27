"""Instruction outcomes and resource relations, not raw pins or asyncio tasks."""
import json
import pytest

from bpuverify.bpu.case.sc_admission import run,run_burst
from bpuverify.bpu.coverage.sc_admission import Coverage,BurstCoverage,ReadOnlyCoverage
from bpuverify.bpu.model.sc_admission import PROFILES,BURST_PROFILES,READ_ONLY_PROFILES
from bpuverify.bpu.model.sc_admission import CONTEXT_BURST_PROFILES
from bpuverify.bpu.coverage.sc_admission import ContextBurstCoverage
from bpuverify.bpu.case.sc_admission import run_context_burst

# Measured on the 2026-10-21 full BPU program run; scheduling hint only.
pytestmark = pytest.mark.estimated_runtime(78)


@pytest.mark.feature('BPU-INT-061')
@pytest.mark.parametrize('profile',CONTEXT_BURST_PROFILES)
async def test_distinct_old_context_feedbacks_keep_original_qualification_and_fresh_consumers(
        bpu_agent,bpu_sc_output,request,profile):
    coverage,evidence=ContextBurstCoverage(profile),{}
    try:
        await run_context_burst(bpu_agent,profile,coverage,evidence)
    finally:
        request.node.user_properties.append(('semantic_bpu_SC_context_burst',json.dumps(evidence,sort_keys=True,default=str)))
        coverage.write(bpu_sc_output)


@pytest.mark.feature('BPU-INT-060')
@pytest.mark.parametrize('profile',PROFILES)
async def test_original_SC_eligibility_controls_concurrent_feedback_admission(bpu_agent,bpu_sc_output,request,profile):
    coverage,evidence = Coverage(profile),{}
    try:
        await run(bpu_agent,profile,coverage,evidence)
    finally:
        request.node.user_properties.append(('semantic_bpu_SC_admission',json.dumps(evidence,sort_keys=True,default=str)))
        coverage.write(bpu_sc_output)


@pytest.mark.feature('BPU-INT-060')
@pytest.mark.parametrize('profile',READ_ONLY_PROFILES)
async def test_correct_SC_disagreement_reads_without_relearning(bpu_agent,bpu_sc_output,request,profile):
    coverage,evidence = ReadOnlyCoverage(profile),{}
    try:
        await run(bpu_agent,profile,coverage,evidence)
    finally:
        request.node.user_properties.append(('semantic_bpu_SC_read_no_write',json.dumps(evidence,sort_keys=True,default=str)))
        coverage.write(bpu_sc_output)


@pytest.mark.feature('BPU-INT-060')
@pytest.mark.parametrize('profile',BURST_PROFILES)
async def test_queued_original_SC_feedbacks_keep_order_and_learning(bpu_agent,bpu_sc_output,request,profile):
    coverage,evidence = BurstCoverage(profile),{}
    try:
        await run_burst(bpu_agent,profile,coverage,evidence)
    finally:
        request.node.user_properties.append(('semantic_bpu_SC_feedback_burst',json.dumps(evidence,sort_keys=True,default=str)))
        coverage.write(bpu_sc_output)
