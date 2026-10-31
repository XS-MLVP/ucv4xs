"""Cases select semantic ordering only, without any edge or signal operations."""
import json
import pytest

from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.sc.model.eligibility import EligibilityProgram
from suites.frontend.bpu.sc.coverage.original_enable import EnableCoverage
from suites.frontend.bpu.sc.case.original_enable import check_enable_lifetime


@pytest.mark.feature('BPU-SC-010')
@pytest.mark.parametrize('direction',(0,1))
@pytest.mark.parametrize('mode',('serial','pipelined'))
async def test_old_active_outcomes_are_ignored_while_disabled_and_fresh_same_results_learn_after_reopening(sc_agent,request,direction,mode):
    program=EligibilityProgram(direction,mode)
    coverage=EnableCoverage(program)
    try:await check_enable_lifetime(sc_agent,program,coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT,'sc'))
        if coverage.evidence is not None:
            request.node.user_properties.append(('original_enable_lifetime',json.dumps(coverage.evidence,ensure_ascii=False)))
