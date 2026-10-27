"""Two semantic cleanup/reset phases; no case-level edges or signal writes."""
import json
import pytest
from bpuverify.mbtb.model.cleanup_reset import Program,PROFILES
from bpuverify.mbtb.coverage.cleanup_reset import Coverage
from bpuverify.mbtb.case.cleanup_reset import check_cleanup_reset



@pytest.mark.feature('BPU-MBTB-001')
@pytest.mark.feature('BPU-MBTB-019')
@pytest.mark.parametrize('profile',PROFILES)
async def test_old_duplicate_cleanup_cannot_erase_new_branch_after_reset(mbtb_cleanup_agent,request,profile):
    program=Program(profile)
    evidence=dict(program=program.state(),status='INCOMPLETE')
    try:
        await check_cleanup_reset(mbtb_cleanup_agent,program,Coverage(program),evidence)
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_mbtb_cleanup_reset_lifetime',json.dumps(evidence,sort_keys=True)))
