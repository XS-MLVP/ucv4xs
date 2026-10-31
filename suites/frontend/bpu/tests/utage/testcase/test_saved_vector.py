"""Two independently learned directions recover as one age-owned vector."""
import json
import pytest
from suites.frontend.bpu.utage.model.saved_vector import PROGRAMS
from suites.frontend.bpu.utage.coverage.saved_vector import Coverage
from suites.frontend.bpu.utage.case.saved_vector import check_saved_vector


@pytest.mark.parametrize('program',tuple(pytest.param(p,id=p.label,marks=pytest.mark.feature(
    'BPU-UTAGE-008' if p.stage=='s2' else 'BPU-UTAGE-009')) for p in PROGRAMS))
async def test_recovery_keeps_both_branch_experiences_in_one_original_age(utage_agent,request,program):
    evidence=dict(program=program.state(),status='INCOMPLETE')
    try: await check_saved_vector(utage_agent,program,Coverage(program),evidence)
    finally: request.node.user_properties.append(('semantic_utage_saved_vector',json.dumps(evidence,sort_keys=True)))
