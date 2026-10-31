"""Final correction must teach its original path, never a younger request."""
import json
import pytest
from suites.frontend.bpu.bpu.model.late_correction_learning import PROFILES
from suites.frontend.bpu.bpu.coverage.late_correction_learning import Coverage
from suites.frontend.bpu.bpu.case.late_correction_learning import run


@pytest.mark.feature('BPU-INT-044')
@pytest.mark.parametrize('profile',PROFILES)
async def test_final_correction_teaches_original_and_new_consumer(bpu_agent,bpu_sc_output,request,profile):
    coverage=Coverage(profile); evidence=dict(profile=profile,status='INCOMPLETE')
    try:
        await run(bpu_agent,profile,coverage,evidence); evidence['status']='PASS'
    except BaseException:
        evidence['status']='FAIL'; raise
    finally:
        coverage.write(bpu_sc_output)
        request.node.user_properties.append(('semantic_bpu_late_correction_learning',json.dumps(evidence,sort_keys=True)))
