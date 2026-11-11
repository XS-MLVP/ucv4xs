"""Duplicate clear and independent learning require destination ownership."""
import json
import pytest
from suites.frontend.bpu.testbenches.bpu.model.main_duplicate_cleanup import Program
from suites.frontend.bpu.testbenches.bpu.model.main_duplicate_cleanup import IDENTITIES
from suites.frontend.bpu.testbenches.bpu.model.main_duplicate_cleanup import OVERLAPS
from suites.frontend.bpu.testbenches.bpu.model.main_duplicate_cleanup import PREPARATIONS
from suites.frontend.bpu.testbenches.bpu.coverage.main_duplicate_cleanup import Coverage
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.main_duplicate_cleanup import check_duplicate_cleanup


@pytest.mark.feature('BPU-MBTB-029')
@pytest.mark.feature('BPU-INT-093')
@pytest.mark.parametrize('identity',IDENTITIES)
@pytest.mark.parametrize('overlap',OVERLAPS)
@pytest.mark.parametrize('preparation',PREPARATIONS)
async def test_main_duplicate_cleanup_preserves_survivor_and_independent_learning(bpu_agent,request,identity,overlap,preparation):
    p=Program(identity,overlap,preparation);evidence=dict(program=p.state(),status='INCOMPLETE')
    try:await check_duplicate_cleanup(bpu_agent,p,Coverage(p),evidence)
    finally:request.node.user_properties.append(('semantic_main_duplicate_cleanup',json.dumps(evidence,sort_keys=True)))
