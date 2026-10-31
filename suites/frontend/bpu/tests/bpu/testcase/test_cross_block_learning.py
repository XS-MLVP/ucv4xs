"""Actual integrated cross-block sources, never freely chosen UT index inputs."""
import json
import pytest
from suites.frontend.bpu.bpu.model.cross_block_learning import PROFILES
from suites.frontend.bpu.bpu.coverage.cross_block_learning import Coverage
from suites.frontend.bpu.bpu.case.cross_block_learning import run


@pytest.mark.feature('BPU-INT-044')
@pytest.mark.parametrize('profile',PROFILES)
async def test_cross_block_learning_keeps_original_ownership_while_held_or_flowing(bpu_agent,bpu_sc_output,request,profile):
    coverage=Coverage(profile); evidence=dict(profile=profile,status='INCOMPLETE')
    try:
        await run(bpu_agent,profile,coverage,evidence); evidence['status']='PASS'
    except BaseException:
        evidence['status']='FAIL'; raise
    finally:
        coverage.write(bpu_sc_output)
        request.node.user_properties.append(('semantic_bpu_cross_block_learning',json.dumps(evidence,sort_keys=True)))
