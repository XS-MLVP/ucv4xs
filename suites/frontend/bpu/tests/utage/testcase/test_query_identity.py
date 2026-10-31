"""Original full-index ownership under serial and adjacent real learning."""
import json
import pytest
from suites.frontend.bpu.utage.model.query_identity import Program,MODES
from suites.frontend.bpu.utage.coverage.query_identity import Coverage
from suites.frontend.bpu.utage.case.query_identity import run


@pytest.mark.feature('BPU-UTAGE-023')
@pytest.mark.feature('BPU-UTAGE-024')
@pytest.mark.parametrize('teacher',(0,1),ids=('taken-first','not-taken-first'))
@pytest.mark.parametrize('mode',MODES)
async def test_same_match_sources_keep_distinct_complete_index_ownership(utage_agent,request,teacher,mode):
    program=Program(teacher,mode);evidence=dict(program=program.state(),status='INCOMPLETE')
    try:await run(utage_agent,program,Coverage(program),evidence)
    finally:request.node.user_properties.append(('semantic_utage_index_alias',json.dumps(evidence,sort_keys=True)))
