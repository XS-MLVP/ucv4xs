"""Four whole semantic lifetimes, no signal/edge/task choreography in tests."""
import json
import pytest

from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.sc.model.eligibility import EligibilityProgram
from suites.frontend.bpu.sc.coverage.eligibility import EligibilityCoverage
from suites.frontend.bpu.sc.case.eligibility import check_eligibility


@pytest.mark.feature('BPU-SC-001')
@pytest.mark.feature('BPU-SC-007')
@pytest.mark.feature('BPU-SC-008')
@pytest.mark.parametrize('direction',(0,1))
@pytest.mark.parametrize('mode',('serial',pytest.param('pipelined',marks=pytest.mark.feature('BPU-SC-009'))))
async def test_warm_correction_uses_its_original_qualification_and_survives_rejection(sc_agent,request,direction,mode):
    program=EligibilityProgram(direction,mode)
    coverage=EligibilityCoverage(program)
    try:
        await check_eligibility(sc_agent,program,coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT,'sc'))
        if coverage.evidence is not None:
            request.node.user_properties.append(('warm_eligibility',json.dumps(coverage.evidence,ensure_ascii=False)))
