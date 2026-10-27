"""Neither opposite learning effect may disappear behind the other version."""
import json
import pytest
from bpuverify.bpu.model.tage.opposed_learning_pair import PROGRAMS
from bpuverify.bpu.coverage.opposed_learning_pair import Coverage
from bpuverify.bpu.case.opposed_learning_pair import check_opposed_learning_pair


@pytest.mark.feature('BPU-INT-086')
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
async def test_opposed_original_feedbacks_preserve_both_current_learning_effects(bpu_agent,bpu_sc_output,request,program):
    coverage=Coverage(program);evidence=dict(program=program.name,status='INCOMPLETE')
    try:
        await check_opposed_learning_pair(bpu_agent,program,coverage,evidence)
        evidence['status']='PASS'
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_opposed_learning_pair',json.dumps(evidence,sort_keys=True)))
        coverage.write(bpu_sc_output)
