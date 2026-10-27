"""An original agreement preserves protection, not obsolete direction confidence."""
import json
import pytest
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.model.delayed_agreement import PROGRAMS
from bpuverify.utage.coverage.delayed_agreement import Coverage
from bpuverify.utage.case.delayed_agreement import run


@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p:p.label)
async def test_delayed_original_agreement_keeps_protection_and_learns_current_direction(utage_agent, request, program):
    coverage = Coverage(program); evidence = dict(program=program.label, status='INCOMPLETE')
    try: await run(utage_agent, program, coverage, evidence)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))
        request.node.user_properties.append(('semantic_utage_delayed_agreement', json.dumps(evidence, sort_keys=True)))
