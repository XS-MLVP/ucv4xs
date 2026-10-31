"""Interior entry learning is not only aligned-block loop learning."""
import json
import pytest
from suites.frontend.bpu.bpu.model.block_entry_learning import PROFILES
from suites.frontend.bpu.bpu.coverage.block_entry_learning import Coverage
from suites.frontend.bpu.bpu.case.block_entry_learning import run


@pytest.mark.feature('BPU-INT-044')
@pytest.mark.parametrize('profile',PROFILES)
async def test_interior_instruction_entry_learns_its_own_negative_provider(bpu_agent,bpu_sc_output,request,profile):
    coverage=Coverage(profile); evidence=dict(profile=profile,status='INCOMPLETE')
    try:
        await run(bpu_agent,profile,coverage,evidence); evidence['status']='PASS'
    except BaseException:
        evidence['status']='FAIL'; raise
    finally:
        coverage.write(bpu_sc_output)
        request.node.user_properties.append(('semantic_bpu_block_entry_learning',json.dumps(evidence,sort_keys=True)))
