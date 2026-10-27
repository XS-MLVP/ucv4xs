"""Real semantic programs; driver, monitor and phase details stay in their layers."""
import json
import pytest
from bpuverify.bpu.model.indirect_path_ownership import PROFILES
from bpuverify.bpu.coverage.indirect_path_ownership import Coverage
from bpuverify.bpu.case.indirect_path_ownership import run


@pytest.mark.feature('BPU-INT-032')
@pytest.mark.feature('BPU-INT-034')
@pytest.mark.feature('BPU-INT-044')
@pytest.mark.feature('BPU-INT-048')
@pytest.mark.parametrize('profile', PROFILES)
async def test_complete_original_direction_and_indirect_target_lifetime(bpu_agent, bpu_sc_output, request, profile):
    coverage = Coverage(profile)
    evidence = dict(profile=profile, status='INCOMPLETE', production_promotion=False)
    try:
        await run(bpu_agent, profile, coverage, evidence)
        evidence['status'] = 'PASS'
    except BaseException:
        evidence['status'] = 'FAIL'
        raise
    finally:
        coverage.write(bpu_sc_output)
        request.node.user_properties.append(('semantic_bpu_indirect_path_ownership', json.dumps(evidence, sort_keys=True)))
