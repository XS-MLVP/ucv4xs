"""The correctness of an original prediction cannot be retroactively changed."""
import json
import pytest
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.model.delayed_protection import PROGRAMS
from bpuverify.utage.coverage.delayed_protection import Coverage
from bpuverify.utage.case.delayed_protection import run


@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p:p.label)
async def test_delayed_feedback_keeps_original_correctness_and_current_learning(utage_agent, request, program):
    coverage = Coverage(program); evidence = dict(program=program.label, status='INCOMPLETE')
    try: await run(utage_agent, program, coverage, evidence)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))
        request.node.user_properties.append(('semantic_utage_delayed_protection', json.dumps(evidence, sort_keys=True)))
