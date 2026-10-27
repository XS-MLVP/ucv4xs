"""Semantic mode only: no edge, fixed delay, signal or task choreography."""
import json
import pytest

from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.common.coverage.exports import write_functional_coverage
from bpuverify.bpu.model.recovery_arbitration import RecoveryProgram
from bpuverify.bpu.env.recovery_arbitration import exercise_recovery


@pytest.mark.feature('BPU-INT-034')
@pytest.mark.feature('BPU-INT-077')
@pytest.mark.parametrize('taken',(0,1))
@pytest.mark.parametrize('mode',('collision','after-repair'))
async def test_original_execution_recovery_wins_over_younger_prediction_repair(bpu_agent,request,taken,mode):
    checks=await exercise_recovery(bpu_agent,RecoveryProgram(taken,mode))
    request.node.user_properties.append(('original_recovery_arbitration',json.dumps(checks.summary(),ensure_ascii=False)))
    write_functional_coverage(checks.database(),output_directory(REPO_ROOT,'bpu')/'functional-recovery-arbitration.json')
