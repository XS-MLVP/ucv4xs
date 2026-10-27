"""Real-DUT source qualification belongs to ENV, not Main hardware coverage."""
import json
import pytest
from bpuverify.bpu.model.source_eligibility import Program,MODES
from bpuverify.bpu.case.source_eligibility import run


@pytest.mark.feature('ENV-DRV-004')
@pytest.mark.toffee_functional_coverage(False)
@pytest.mark.parametrize('mode',MODES)
async def test_original_source_and_driver_task_lifetimes_remain_distinct(bpu_agent,request,mode):
    program=Program(mode);evidence=dict(status='INCOMPLETE',program=program.state())
    try:await run(bpu_agent,program,evidence)
    finally:request.node.user_properties.append(('semantic_environment_source_eligibility',json.dumps(evidence,sort_keys=True)))
