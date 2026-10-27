"""Isolated semantic controls; no production imports are overridden."""
import json

import pytest

from bpuverify.bpu.case.main_sibling import check_main_sibling
from bpuverify.bpu.model.main_sibling import Program, PHASES, ORIGINS
from bpuverify.bpu.coverage.main_sibling import Coverage


@pytest.mark.feature('BPU-MBTB-028')
@pytest.mark.parametrize('phase',PHASES)
@pytest.mark.parametrize('origin',ORIGINS)
async def test_correcting_earlier_branch_preserves_unexecuted_conditional_sibling(bpu_agent,request,phase,origin):
    program = Program(phase,origin)
    evidence = dict(program=program.state(),status='INCOMPLETE')
    coverage = Coverage(program)
    try:
        await check_main_sibling(bpu_agent,program,evidence,coverage)
    finally:
        request.node.user_properties.append(('semantic_unexecuted_sibling',json.dumps(evidence,sort_keys=True)))
