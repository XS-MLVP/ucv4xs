"""Real semantic programs; driver, monitor and phase details stay in their layers."""
import json
import pytest
from suites.frontend.bpu.bpu.model.conditional_prefix import PROFILES
from suites.frontend.bpu.bpu.coverage.conditional_prefix import Coverage
from suites.frontend.bpu.bpu.case.conditional_prefix import run


@pytest.mark.feature('BPU-INT-032')
@pytest.mark.feature('BPU-INT-034')
@pytest.mark.feature('BPU-INT-044')
@pytest.mark.feature('BPU-INT-048')
@pytest.mark.feature('BPU-INT-111')
@pytest.mark.parametrize('profile', PROFILES)
async def test_atomic_conditional_prefix_ownership(bpu_agent, bpu_sc_output, request, profile):
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
        if 'duplicate_visibility' in evidence:
            with open(bpu_sc_output / 'duplicate-visibility.json', 'w') as stream:
                json.dump(evidence['duplicate_visibility'], stream, indent=1, sort_keys=True)
        request.node.user_properties.append(('semantic_bpu_conditional_prefix', json.dumps(evidence, sort_keys=True)))
