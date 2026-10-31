"""Long provider correction preserves two full identities and short experience."""
import json
import pytest
from suites.frontend.bpu.utage.model.long_protection import Program,MODES,LIFETIMES
from suites.frontend.bpu.utage.coverage.long_protection import Coverage
from suites.frontend.bpu.utage.case.long_protection import run


@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.feature('BPU-UTAGE-023')
@pytest.mark.feature('BPU-UTAGE-024')
@pytest.mark.parametrize('first',(0,1),ids=('not-taken-first','taken-first'))
@pytest.mark.parametrize('mode',MODES)
@pytest.mark.parametrize('lifetime',LIFETIMES)
async def test_long_provider_feedback_keeps_original_identity_and_short_experience(utage_agent,request,first,mode,lifetime):
    p=Program(first,mode,lifetime);evidence=dict(program=p.state(),status='INCOMPLETE')
    try:await run(utage_agent,p,Coverage(p),evidence)
    finally:request.node.user_properties.append(('semantic_utage_long_protection',json.dumps(evidence,sort_keys=True)))
