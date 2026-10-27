"""One semantic action matrix, not one test per stack storage location."""
import json
import pytest
from bpuverify.ras.model.commit_action import Program
from bpuverify.ras.coverage.commit_action import Coverage
from bpuverify.ras.case.commit_action import run


@pytest.mark.feature('BPU-RAS-017')
@pytest.mark.parametrize('action',(1,2,3),ids=('return','call','return-and-call'))
async def test_real_original_commit_applies_its_resolved_stack_action(ras_agent,request,action):
    program=Program(action);evidence=dict(status='INCOMPLETE',program=program.state())
    try:await run(ras_agent,program,Coverage(program),evidence)
    finally:request.node.user_properties.append(('semantic_ras_original_commit_action',json.dumps(evidence,sort_keys=True)))
