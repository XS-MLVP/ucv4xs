"""Neutral use at protection limits does not freeze later branch learning."""
import json
import pytest
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.bpu.model.neutral_recovery import PROFILES
from bpuverify.bpu.coverage.neutral_recovery import Coverage
from bpuverify.bpu.case.neutral_recovery import run


@pytest.mark.feature('BPU-INT-066')
@pytest.mark.parametrize('profile', PROFILES)
async def test_neutral_guidance_at_protection_limits_keeps_real_learning_reversible(bpu_agent, request, profile):
    coverage = Coverage(); evidence = dict(profile=profile, status='INCOMPLETE')
    try:
        await run(bpu_agent, profile, coverage, evidence); evidence['status'] = 'PASS'
    except BaseException:
        evidence['status'] = 'FAIL'; raise
    finally:
        coverage.write(output_directory(REPO_ROOT, 'bpu'))
        request.node.user_properties.append(('semantic_bpu_neutral_recovery', json.dumps(evidence, sort_keys=True)))
