"""Joint native-source qualification before assigning functional credit."""
import json
import pytest
from bpuverify.bpu.case.joint_lifetime import check_joint_cold
from bpuverify.bpu.model.joint_lifetime import Program, MODES
from bpuverify.bpu.coverage.joint_lifetime import Coverage
from bpuverify.bpu.case.joint_lifetime import run

@pytest.mark.feature('BPU-INT-004')
async def test_joint_cold_sources_compare_both_read_stages_and_full_metadata(bpu_agent, request):
    evidence = dict(status='INCOMPLETE')
    try:
        await check_joint_cold(bpu_agent, evidence)
    except BaseException as error:
        evidence.update(status='FAIL', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_joint_cold_qualification', json.dumps(evidence, sort_keys=True)))

@pytest.mark.feature('BPU-INT-004')
@pytest.mark.feature('BPU-INT-007')
@pytest.mark.feature('BPU-INT-032')
@pytest.mark.parametrize('mode', MODES)
async def test_original_direction_selects_the_only_eligible_indirect_target(bpu_agent, request, mode):
    program = Program(mode)
    evidence = dict(program=program.state(), status='INCOMPLETE')
    try:
        await run(bpu_agent, program, Coverage(program), evidence)
    except BaseException as error:
        evidence.update(status='FAIL', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_joint_late_lifetime', json.dumps(evidence, sort_keys=True)))
