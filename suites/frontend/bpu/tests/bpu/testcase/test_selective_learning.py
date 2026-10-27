"""An inactive companion cannot suppress another branch's late learning."""
import json
import pytest
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.bpu.model.tage.selective_learning import PROGRAMS, LATER_PROGRAMS
from bpuverify.bpu.coverage.selective_learning import Coverage
from bpuverify.bpu.case.selective_learning import check_selective_learning


@pytest.mark.feature('BPU-INT-086')
@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.name)
async def test_inactive_companion_preserves_qualified_late_learning(bpu_agent, request, program):
    evidence = dict(program=program.name, status='INCOMPLETE')
    coverage = Coverage(program)
    try:
        await check_selective_learning(bpu_agent, program, coverage, evidence)
        evidence['status'] = 'PASS'
    except BaseException:
        evidence['status'] = 'FAIL'
        raise
    finally:
        coverage.write(output_directory(REPO_ROOT, 'bpu'))
        request.node.user_properties.append(('semantic_selective_direction_learning', json.dumps(evidence, sort_keys=True)))


@pytest.mark.feature('BPU-INT-086')
@pytest.mark.parametrize('program', LATER_PROGRAMS, ids=lambda p: p.name)
async def test_NT_prefix_preserves_later_qualified_learning(bpu_agent, request, program):
    evidence = dict(program=program.name, status='INCOMPLETE')
    coverage = Coverage(program)
    try:
        await check_selective_learning(bpu_agent, program, coverage, evidence)
        evidence['status'] = 'PASS'
    except BaseException:
        evidence['status'] = 'FAIL'
        raise
    finally:
        coverage.write(output_directory(REPO_ROOT, 'bpu'))
        request.node.user_properties.append(('semantic_selective_direction_learning', json.dumps(evidence, sort_keys=True)))
