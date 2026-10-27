"""Every retained branch owns both its boundary learning and final visibility."""
import json
import pytest
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.bpu.model.tage.shared_saturation import PROGRAMS
from bpuverify.bpu.coverage.shared_saturation import Coverage
from bpuverify.bpu.case.shared_saturation import check_shared_saturation


@pytest.mark.feature('BPU-INT-087')
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
async def test_each_retained_history_accumulates_and_holds_its_own_learning(bpu_agent,request,program):
    coverage=Coverage(program);evidence=dict(program=program.name,status='INCOMPLETE')
    try:
        await check_shared_saturation(bpu_agent,program,coverage,evidence);evidence['status']='PASS'
    except BaseException:
        evidence['status']='FAIL';raise
    finally:
        coverage.write(output_directory(REPO_ROOT,'bpu'))
        request.node.user_properties.append(('semantic_shared_saturation',json.dumps(evidence,sort_keys=True)))
