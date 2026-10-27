"""An old writeback never acknowledges a newer learning version."""
import json
import pytest
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.bpu.model.tage.service_relearning import PROGRAMS
from bpuverify.bpu.coverage.service_relearning import Coverage
from bpuverify.bpu.case.service_relearning import run


@pytest.mark.feature('BPU-INT-087')
@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
async def test_old_service_cannot_discharge_new_learning(bpu_agent, request, program):
    coverage = Coverage(program)
    evidence = dict(program=program.name, status='INCOMPLETE')
    try:
        await run(bpu_agent, program, coverage, evidence)
        evidence['status'] = 'PASS'
    except BaseException:
        evidence['status'] = 'FAIL'
        raise
    finally:
        coverage.write(output_directory(REPO_ROOT, 'bpu'))
        request.node.user_properties.append(('semantic_service_relearning', json.dumps(evidence, sort_keys=True)))
