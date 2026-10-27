"""Two interior entries and two meaningful older paths, not a coordinate sweep."""
import json
import pytest
from bpuverify.bpu.model.short_revisit import PROFILES
from bpuverify.bpu.coverage.short_revisit import Coverage
from bpuverify.bpu.case.short_revisit import run


@pytest.mark.feature('BPU-INT-066')
@pytest.mark.parametrize('profile',PROFILES)
async def test_new_long_priority_then_original_short_learning_revisit(bpu_agent,bpu_sc_output,request,profile):
    coverage=Coverage(profile); evidence=dict(profile=profile,status='INCOMPLETE')
    try:
        await run(bpu_agent,profile,coverage,evidence); evidence['status']='PASS'
    except BaseException:
        evidence['status']='FAIL'; raise
    finally:
        coverage.write(bpu_sc_output)
        request.node.user_properties.append(('semantic_bpu_short_revisit',json.dumps(evidence,sort_keys=True)))
