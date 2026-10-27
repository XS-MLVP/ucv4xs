"""Real DUT semantic controls staged outside the frozen production source."""
import json

import pytest

from bpuverify.bpu.coverage.main_sibling import Coverage
from bpuverify.bpu.model.main_dynamic_target import Program, PHASES, ORIGINS
from bpuverify.bpu.case.main_dynamic_target import check_main_dynamic_target


@pytest.mark.feature('BPU-MBTB-028')
@pytest.mark.parametrize('phase', PHASES)
@pytest.mark.parametrize('origin', ORIGINS)
async def test_dynamic_indirect_target_preserves_unexecuted_conditional_sibling(bpu_agent, request, phase, origin):
    program = Program(phase, origin)
    evidence = dict(program=program.state(), status='INCOMPLETE')
    coverage = Coverage(program)
    try:
        await check_main_dynamic_target(bpu_agent, program, evidence, coverage)
    finally:
        request.node.user_properties.append(('semantic_dynamic_indirect_sibling', json.dumps(evidence, sort_keys=True)))
