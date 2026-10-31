"""Literal miss payload cannot grant learning authority to the old identity."""
import json
import pytest
from suites.frontend.bpu.bpu.model.miss_authority import Program
from suites.frontend.bpu.bpu.coverage.miss_authority import Coverage
from suites.frontend.bpu.bpu.case.miss_authority import run


@pytest.mark.feature('BPU-MBTB-027')
@pytest.mark.parametrize('allocate',(False,True),ids=('no-allocation','allocate'))
@pytest.mark.parametrize('same_position',(False,True),ids=('other-position','same-position'))
async def test_original_miss_payload_has_no_resident_direction_authority(bpu_agent,request,allocate,same_position):
    p=Program(allocate,same_position);evidence=dict(program=p.state(),status='INCOMPLETE')
    try:await run(bpu_agent,p,Coverage(p),evidence)
    finally:request.node.user_properties.append(('semantic_bpu_miss_authority',json.dumps(evidence,sort_keys=True)))
