"""Actual SC guidance must belong to a real early conditional and fresh consumer."""
import json

import pytest

from bpuverify.bpu.case.sc_early_learning import run
from bpuverify.bpu.coverage.sc_early_learning import Coverage
from bpuverify.bpu.model.sc_early_learning import PROFILES


@pytest.mark.feature('BPU-INT-032')
@pytest.mark.feature('BPU-INT-044')
@pytest.mark.feature('BPU-INT-048')
@pytest.mark.parametrize('profile',PROFILES)
async def test_SC_original_guidance_builds_a_natural_early_consumer(bpu_agent,bpu_sc_output,request,profile):
    coverage,evidence = Coverage(profile),{}
    try:
        await run(bpu_agent,profile,coverage,evidence)
    finally:
        request.node.user_properties.append(('semantic_bpu_SC_early_learning',json.dumps(evidence,sort_keys=True,default=str)))
        coverage.write(bpu_sc_output)
