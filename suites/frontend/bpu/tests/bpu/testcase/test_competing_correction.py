"""Two independently owned corrections, one restored path and a new consumer."""
import json
import pytest
from bpuverify.bpu.model.competing_correction import PROFILES
from bpuverify.bpu.coverage.competing_correction import Coverage
from bpuverify.bpu.case.competing_correction import run


@pytest.mark.feature('BPU-INT-034')
@pytest.mark.parametrize('profile',PROFILES)
async def test_older_late_correction_wins_younger_middle_path(bpu_agent,bpu_sc_output,request,profile):
    coverage=Coverage(profile); evidence=dict(profile=profile,status='INCOMPLETE')
    try:
        await run(bpu_agent,profile,coverage,evidence); evidence['status']='PASS'
    except BaseException:
        evidence['status']='FAIL';raise
    finally:
        coverage.write(bpu_sc_output)
        request.node.user_properties.append(('semantic_bpu_competing_correction',json.dumps(evidence,sort_keys=True)))
