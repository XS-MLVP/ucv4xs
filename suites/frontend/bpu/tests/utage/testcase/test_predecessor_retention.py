"""Human behavior crosses: retention boundary and real feedback cadence."""
import json
import pytest

from bpuverify.utage.case.predecessor_retention import run
from bpuverify.utage.coverage.predecessor_retention import Coverage
from bpuverify.utage.model.predecessor_retention import Program,PROFILES,MODES
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT


@pytest.mark.feature('BPU-UTAGE-016')
@pytest.mark.feature('BPU-UTAGE-020')
@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.feature('BPU-UTAGE-022')
@pytest.mark.feature('BPU-UTAGE-023')
@pytest.mark.parametrize('profile',PROFILES)
@pytest.mark.parametrize('mode',MODES)
@pytest.mark.parametrize('taken',(
    pytest.param(True,id='taken',marks=pytest.mark.feature('BPU-UTAGE-003')),
    pytest.param(False,id='not-taken',marks=pytest.mark.feature('BPU-UTAGE-004'))))
async def test_multiple_incoming_edges_keep_short_learning_after_retirement(utage_agent,profile,mode,taken,request):
    program = Program(profile,mode,taken)
    coverage,evidence = Coverage(program),{}
    try:
        await run(utage_agent,program,coverage,evidence)
    finally:
        request.node.user_properties.append(('semantic_utage_predecessor_retention',json.dumps(evidence,sort_keys=True,default=str)))
        coverage.write(output_directory(REPO_ROOT,'utage'))
