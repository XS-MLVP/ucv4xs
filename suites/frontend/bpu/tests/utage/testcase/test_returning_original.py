"""An old contribution belongs to the original branch, not its replacement."""
import json
import pytest
from suites.frontend.bpu.utage.model.returning_original import PROGRAMS
from suites.frontend.bpu.utage.coverage.returning_original import Coverage
from suites.frontend.bpu.utage.case.read_lifetime import check_late_replacement


@pytest.mark.feature('BPU-UTAGE-019')
@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.feature('BPU-UTAGE-023')
@pytest.mark.parametrize('program', PROGRAMS, ids=lambda program: program.label)
async def test_original_contribution_rebuilds_its_own_experience_after_another_branch_takes_it(utage_agent, request, program):
    evidence = dict(program=program.state(), status='INCOMPLETE')
    try:
        await check_late_replacement(utage_agent, program, Coverage(program), evidence)
    finally:
        request.node.user_properties.append(('semantic_utage_returning_original', json.dumps(evidence, sort_keys=True)))
