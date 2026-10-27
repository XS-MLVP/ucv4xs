"""Old request disposition is source-owned, never guessed from equal PCs."""
import json
import pytest
from bpuverify.mbtb.model.query_reset import Program,MODES
from bpuverify.mbtb.coverage.query_reset import Coverage
from bpuverify.mbtb.case.query_reset import check_query_reset_lifetime


@pytest.mark.feature('BPU-MBTB-001')
@pytest.mark.parametrize('mode',MODES)
async def test_main_query_response_keeps_its_original_reset_epoch(mbtb_agent,request,mode):
    program=Program(mode)
    evidence=dict(program=program.state(),status='INCOMPLETE')
    try:
        await check_query_reset_lifetime(mbtb_agent,program,Coverage(program),evidence)
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_query_reset_lifetime',json.dumps(evidence,sort_keys=True)))
