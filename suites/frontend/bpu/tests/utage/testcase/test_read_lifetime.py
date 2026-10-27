"""Four semantic version/age combinations, not physical-coordinate sweeps."""
import json
import pytest

from bpuverify.utage.model.read_lifetime import Program,PROFILES,RELATIONS
from bpuverify.utage.coverage.read_lifetime import Coverage
from bpuverify.utage.case.read_lifetime import check_read_version



@pytest.mark.feature('BPU-UTAGE-006')
@pytest.mark.feature('BPU-UTAGE-015')
@pytest.mark.feature('BPU-UTAGE-022')
@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('relation',RELATIONS)
async def test_old_query_keeps_original_branch_version_when_learning_changes_future_consumers(utage_agent,request,profile,relation):
    program=Program(profile,relation)
    evidence=dict(program=program.state(),status='INCOMPLETE')
    try:
        await check_read_version(utage_agent,program,Coverage(program),evidence)
    except BaseException as error:
        evidence.update(status='FAIL',error_type=type(error).__name__,error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_utage_read_version_lifetime',json.dumps(evidence,sort_keys=True)))


from bpuverify.utage.model.read_lifetime import LateReplacementProgram,REBUILD_PROFILES,MODES
from bpuverify.utage.coverage.read_lifetime import LateReplacementCoverage
from bpuverify.utage.case.read_lifetime import check_late_replacement


@pytest.mark.feature('BPU-UTAGE-019')
@pytest.mark.parametrize('profile',REBUILD_PROFILES)
@pytest.mark.parametrize('mode',MODES)
async def test_late_short_originals_rebuild_their_own_confidence_after_another_branch_takes_the_row(utage_agent,request,profile,mode):
    program=LateReplacementProgram(profile,mode)
    evidence=dict(program=program.state(),status='INCOMPLETE')
    try:
        await check_late_replacement(utage_agent,program,LateReplacementCoverage(program),evidence)
    finally:
        request.node.user_properties.append(('semantic_utage_late_owner_rebuild',json.dumps(evidence,sort_keys=True)))
