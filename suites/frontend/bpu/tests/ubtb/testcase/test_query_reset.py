"""Old request disposition is source-owned, never guessed from equal PCs."""
import json
import pytest
from bpuverify.ubtb.model.query_reset import Program,MODES
from bpuverify.ubtb.coverage.query_reset import Coverage
from bpuverify.ubtb.case.query_reset import check_query_reset_lifetime


@pytest.mark.feature('BPU-UBTB-001')
@pytest.mark.parametrize('mode',MODES)
async def test_micro_query_response_keeps_its_original_reset_epoch(ubtb_agent,request,mode):
    program=Program(mode)
    evidence=dict(program=program.state(),status='INCOMPLETE')
    try:
        await check_query_reset_lifetime(ubtb_agent,program,Coverage(program),evidence)
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_query_reset_lifetime',json.dumps(evidence,sort_keys=True)))
