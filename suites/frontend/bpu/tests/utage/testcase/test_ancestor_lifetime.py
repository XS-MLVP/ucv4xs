"""Read and match ancestry remain distinct across a real learning effect."""
import json
import pytest
from bpuverify.utage.model.ancestor_lifetime import Program,PROFILES,RELATIONS
from bpuverify.utage.coverage.ancestor_lifetime import Coverage
from bpuverify.utage.case.ancestor_lifetime import check_ancestor_lifetime



@pytest.mark.feature('BPU-UTAGE-006')
@pytest.mark.feature('BPU-UTAGE-015')
@pytest.mark.feature('BPU-UTAGE-022')
@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('relation',RELATIONS)
async def test_later_window_matches_its_own_identity_without_rebinding_the_earlier_read(utage_agent,request,profile,relation):
    p=Program(profile,relation)
    evidence=dict(program=p.state(),status='INCOMPLETE')
    try:await check_ancestor_lifetime(utage_agent,p,Coverage(p),evidence)
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error));raise
    finally:request.node.user_properties.append(('semantic_utage_distinct_ancestor_lifetime',json.dumps(evidence,sort_keys=True)))
