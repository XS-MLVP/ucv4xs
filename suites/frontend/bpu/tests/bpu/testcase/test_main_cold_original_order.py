"""A still-valid cold original cannot initialize an unexecuted sibling."""
import json
import pytest
from bpuverify.bpu.model.main_cold_original_order import Program,ORDERS,PHASES,COUNTERS
from bpuverify.bpu.coverage.main_cold_original_order import Coverage
from bpuverify.bpu.case.main_cold_original_order import run


@pytest.mark.feature('BPU-INT-093')
@pytest.mark.feature('BPU-INT-095')
@pytest.mark.feature('BPU-MBTB-028')
@pytest.mark.parametrize('order',ORDERS)
@pytest.mark.parametrize('phase',PHASES)
@pytest.mark.parametrize('counter',COUNTERS,ids=('strong-NT','weak-NT'))
async def test_live_original_cold_resolve_preserves_retained_branch_and_unexecuted_sibling(bpu_agent,request,order,phase,counter):
    program=Program(order,phase,counter);evidence=dict(status='INCOMPLETE',program=program.state())
    try:await run(bpu_agent,program,Coverage(program),evidence)
    finally:request.node.user_properties.append(('semantic_live_cold_original',json.dumps(evidence,sort_keys=True)))
