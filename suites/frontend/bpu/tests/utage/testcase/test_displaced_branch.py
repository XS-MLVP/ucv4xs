"""Late instruction qualification must not freeze an independent companion."""
import json
import pytest
from suites.frontend.bpu.utage.model.displaced_branch import PROGRAMS
from suites.frontend.bpu.utage.coverage.displaced_branch import Coverage
from suites.frontend.bpu.utage.case.displaced_branch import check_displaced_branch


@pytest.mark.feature('BPU-UTAGE-014')
@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
async def test_late_original_respects_the_current_instruction_but_its_companion_still_learns(utage_agent,request,program):
    evidence = dict(program=program.state(),status='INCOMPLETE')
    try:
        await check_displaced_branch(utage_agent,program,Coverage(program),evidence)
    finally:
        request.node.user_properties.append(('semantic_utage_displaced_branch',json.dumps(evidence,sort_keys=True)))
