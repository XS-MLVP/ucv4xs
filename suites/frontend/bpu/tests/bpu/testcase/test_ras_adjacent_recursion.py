"""Adjacent recursive owners must not borrow each other's remaining returns."""
import json
import pytest
from bpuverify.bpu.model.ras.adjacent_recursion import Program,DEPTHS,RELATIONS
from bpuverify.bpu.coverage.ras_adjacent_recursion import Coverage
from bpuverify.bpu.case.ras.adjacent_recursion import check_adjacent_recursion


@pytest.mark.feature('BPU-INT-033')
@pytest.mark.feature('BPU-INT-054')
@pytest.mark.feature('BPU-INT-096')
@pytest.mark.parametrize('depth',DEPTHS)
@pytest.mark.parametrize('relation',RELATIONS)
async def test_near_capacity_adjacent_recursive_frames_preserve_counts_and_complete_returns(bpu_agent,request,depth,relation):
    program=Program(depth,relation);evidence=dict(program=program.state(),status='INCOMPLETE')
    try:await check_adjacent_recursion(bpu_agent,program,Coverage(program),evidence)
    except BaseException as error:
        evidence.update(status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
    finally:request.node.user_properties.append(('semantic_adjacent_recursive_return',json.dumps(evidence,sort_keys=True)))
