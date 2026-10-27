"""An accepted original effect survives a coincident prediction recovery."""
import json
import pytest
from bpuverify.bpu.model.main_coincident_recovery import PROGRAMS
from bpuverify.bpu.coverage.main_coincident_recovery import Coverage
from bpuverify.bpu.case.main_coincident_recovery import check_coincident_recovery


@pytest.mark.feature('BPU-INT-005')
@pytest.mark.feature('BPU-INT-093')
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
async def test_same_boundary_learning_and_recovery_preserve_the_accepted_original(bpu_agent,request,program):
    evidence=dict(program=program.state(),status='INCOMPLETE')
    try:await check_coincident_recovery(bpu_agent,program,Coverage(program),evidence)
    finally:request.node.user_properties.append(('semantic_main_coincident_recovery',json.dumps(evidence,sort_keys=True)))
