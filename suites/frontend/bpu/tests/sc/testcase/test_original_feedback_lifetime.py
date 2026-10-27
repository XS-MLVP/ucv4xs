"""Each case expresses a semantic rejection cause, not waveform details."""
import json
import pytest

from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.sc.model.original_feedback import FeedbackProgram
from bpuverify.sc.coverage.original_feedback import FeedbackCoverage
from bpuverify.sc.case.original_feedback import check_ignored_original_feedback


@pytest.mark.feature('BPU-SC-011')
@pytest.mark.parametrize('gate',('provider-missing','main-miss','nonconditional'))
@pytest.mark.parametrize('direction',(0,1))
@pytest.mark.parametrize('mode',('serial','pipelined'))
async def test_single_ineligible_original_feedback_preserves_learning_and_valid_reverse_feedback_still_changes_it(sc_agent,request,gate,direction,mode):
    program=FeedbackProgram(direction,mode,gate)
    coverage=FeedbackCoverage(program)
    try:
        await check_ignored_original_feedback(sc_agent,program,coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT,'sc'))
        if coverage.evidence is not None:
            request.node.user_properties.append(('ignored_original_feedback',json.dumps(coverage.evidence,ensure_ascii=False)))
