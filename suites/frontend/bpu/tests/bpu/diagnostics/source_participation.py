"""Explicit-only setup diagnostic; no unresolved-learning functional credit."""
import json
import pytest

from bpuverify.bpu.env.indirect_learning import indirect_program
from bpuverify.bpu.env.source_participation import PC,PROFILES,observe_source_participation


@pytest.mark.parametrize('profile',PROFILES)
async def test_genuine_original_participation_before_adopting_a_learning_policy(bpu_agent,request,profile):
    async with indirect_program(bpu_agent,PC) as env:
        evidence=await observe_source_participation(env,profile)
    request.node.user_properties.append(('source_participation_diagnostic',json.dumps(evidence,ensure_ascii=False)))
