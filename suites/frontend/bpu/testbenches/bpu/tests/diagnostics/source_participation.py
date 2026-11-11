"""Explicit-only setup diagnostic; no unresolved-learning functional credit."""
import json
import pytest

from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.indirect_learning import indirect_program
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.source_participation import PC
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.source_participation import PROFILES
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.source_participation import observe_source_participation


@pytest.mark.parametrize('profile',PROFILES)
async def test_genuine_original_participation_before_adopting_a_learning_policy(bpu_agent,request,profile):
    async with indirect_program(bpu_agent,PC) as env:
        evidence=await observe_source_participation(env,profile)
    request.node.user_properties.append(('source_participation_diagnostic',json.dumps(evidence,ensure_ascii=False)))
