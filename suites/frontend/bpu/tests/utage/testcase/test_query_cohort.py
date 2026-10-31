"""Read ages and branch-version semantics, not a physical coordinate matrix."""
import json
import pytest
from suites.frontend.bpu.utage.model.query_cohort import Program,PROFILES,ANCESTRIES
from suites.frontend.bpu.utage.coverage.query_cohort import Coverage
from suites.frontend.bpu.utage.case.query_cohort import run


@pytest.mark.feature('BPU-UTAGE-006')
@pytest.mark.feature('BPU-UTAGE-015')
@pytest.mark.feature('BPU-UTAGE-022')
@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('ancestry',ANCESTRIES)
async def test_each_original_query_keeps_its_own_version_across_learning_and_later_turnover(utage_agent,request,profile,ancestry):
    program=Program(profile,ancestry);evidence=dict(program=program.state(),status='INCOMPLETE')
    try:await run(utage_agent,program,Coverage(program),evidence)
    finally:request.node.user_properties.append(('semantic_utage_query_cohort',json.dumps(evidence,sort_keys=True)))
