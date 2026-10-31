"""Two genuine original versions cannot relearn an unexecuted sibling."""
import json
import pytest
from suites.frontend.bpu.bpu.model.main_original_order import Program,ORDERS,PHASES,COUNTERS
from suites.frontend.bpu.bpu.coverage.main_original_order import Coverage
from suites.frontend.bpu.bpu.case.main_original_order import run


@pytest.mark.feature('BPU-INT-093')
@pytest.mark.feature('BPU-INT-095')
@pytest.mark.feature('BPU-MBTB-028')
@pytest.mark.parametrize('order',ORDERS)
@pytest.mark.parametrize('phase',PHASES)
@pytest.mark.parametrize('counter',COUNTERS,ids=('strong-NT','weak-NT'))
async def test_original_resolve_arrival_controls_latest_target_without_relearning_unexecuted_sibling(bpu_agent,request,order,phase,counter):
    program=Program(order,phase,counter);evidence=dict(status='INCOMPLETE',program=program.state())
    try:await run(bpu_agent,program,Coverage(program),evidence)
    finally:request.node.user_properties.append(('semantic_main_original_order',json.dumps(evidence,sort_keys=True)))
