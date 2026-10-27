"""Duplicate clear and independent learning require destination ownership."""
import json
import pytest
from bpuverify.bpu.model.main_duplicate_cleanup import Program,IDENTITIES,OVERLAPS,PREPARATIONS
from bpuverify.bpu.coverage.main_duplicate_cleanup import Coverage
from bpuverify.bpu.case.main_duplicate_cleanup import check_duplicate_cleanup


@pytest.mark.feature('BPU-MBTB-029')
@pytest.mark.feature('BPU-INT-093')
@pytest.mark.parametrize('identity',IDENTITIES)
@pytest.mark.parametrize('overlap',OVERLAPS)
@pytest.mark.parametrize('preparation',PREPARATIONS)
async def test_main_duplicate_cleanup_preserves_survivor_and_independent_learning(bpu_agent,request,identity,overlap,preparation):
    p=Program(identity,overlap,preparation);evidence=dict(program=p.state(),status='INCOMPLETE')
    try:await check_duplicate_cleanup(bpu_agent,p,Coverage(p),evidence)
    finally:request.node.user_properties.append(('semantic_main_duplicate_cleanup',json.dumps(evidence,sort_keys=True)))
