"""Interior original contribution and original-consistent-but-wrong penalties."""
import json
import pytest
from suites.frontend.bpu.bpu.model.entry_protection import PROFILES
from suites.frontend.bpu.bpu.coverage.entry_protection import Coverage
from suites.frontend.bpu.bpu.case.entry_protection import run


@pytest.mark.feature('BPU-INT-066')
@pytest.mark.parametrize('profile',PROFILES)
async def test_interior_original_contribution_and_error_own_their_protection(bpu_agent,bpu_sc_output,request,profile):
    coverage=Coverage(profile); evidence=dict(profile=profile,status='INCOMPLETE')
    try:
        await run(bpu_agent,profile,coverage,evidence); evidence['status']='PASS'
    except BaseException:
        evidence['status']='FAIL'; raise
    finally:
        coverage.write(bpu_sc_output)
        request.node.user_properties.append(('semantic_bpu_entry_protection',json.dumps(evidence,sort_keys=True)))
