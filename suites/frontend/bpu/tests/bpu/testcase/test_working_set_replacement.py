"""Natural multi-branch identity turnover, retaining the original failed suite."""
import json

import pytest

from bpuverify.bpu.case.working_set_replacement import check_ahead_identity_replacement
from bpuverify.bpu.coverage.working_set_replacement import Coverage
from bpuverify.bpu.model.working_set_replacement import KINDS, Program, geometry


@pytest.mark.feature('BPU-INT-100')
@pytest.mark.parametrize('kinds', KINDS)
async def test_new_branch_identity_clears_strong_old_confidence_and_preserves_survivors(bpu_agent, request, kinds):
    program = Program(kinds)
    coverage = Coverage(program)
    try:
        await check_ahead_identity_replacement(bpu_agent, program, coverage)
    finally:
        evidence = dict(coverage.evidence or dict(status='INCOMPLETE'), declared_geometry=geometry(program))
        request.node.user_properties.append(('semantic_bpu_ahead_identity_replacement',
                                            json.dumps(evidence, sort_keys=True)))
