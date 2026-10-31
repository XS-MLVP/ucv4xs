"""An available service slot cannot be allocated to two independent obligations."""
import json
import pytest
from suites.frontend.bpu.mbtb.model.shared_service import PROGRAMS
from suites.frontend.bpu.mbtb.coverage.shared_service import Coverage
from suites.frontend.bpu.mbtb.case.shared_service import check_shared_service


@pytest.mark.feature('BPU-MBTB-026')
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
async def test_relocated_correction_and_first_cleanup_both_survive_shared_service(mbtb_agent,program,request):
    evidence=dict(program=program.state(),status='INCOMPLETE');coverage=Coverage(program)
    try:
        await check_shared_service(mbtb_agent,program,coverage,evidence);evidence['status']='PASS'
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,first_error=str(error));raise
    finally:request.node.user_properties.append(('semantic_mbtb_shared_service',json.dumps(evidence,sort_keys=True)))
