"""An original agreement preserves protection, not obsolete direction confidence."""
import json
import pytest
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.utage.model.delayed_agreement import PROGRAMS
from suites.frontend.bpu.utage.coverage.delayed_agreement import Coverage
from suites.frontend.bpu.utage.case.delayed_agreement import run


@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p:p.label)
async def test_delayed_original_agreement_keeps_protection_and_learns_current_direction(utage_agent, request, program):
    coverage = Coverage(program); evidence = dict(program=program.label, status='INCOMPLETE')
    try: await run(utage_agent, program, coverage, evidence)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))
        request.node.user_properties.append(('semantic_utage_delayed_agreement', json.dumps(evidence, sort_keys=True)))
