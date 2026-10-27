"""Fresh evidence for phase-changing protection ownership, not row enumeration."""
import json
import pytest
from bpuverify.utage.model.selective_protection import Program,MODES
from bpuverify.utage.coverage.selective_protection import Coverage
from bpuverify.utage.case.selective_protection import run


@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.feature('BPU-UTAGE-023')
@pytest.mark.feature('BPU-UTAGE-024')
@pytest.mark.parametrize('first',(0,1),ids=('taken-first','not-taken-first'))
@pytest.mark.parametrize('mode',MODES)
async def test_fresh_originals_keep_selective_protection_and_direction_correction_owned(utage_agent,request,first,mode):
    program=Program(first,mode);evidence=dict(program=program.state(),status='INCOMPLETE')
    try:await run(utage_agent,program,Coverage(program),evidence)
    finally:request.node.user_properties.append(('semantic_utage_selective_protection_alias',json.dumps(evidence,sort_keys=True)))
