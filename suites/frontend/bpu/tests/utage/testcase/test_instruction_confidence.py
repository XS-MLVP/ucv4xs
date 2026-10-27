"""An overlapping other-instruction version cannot enter the old counter chain."""
import json
import pytest
from bpuverify.utage.model.instruction_confidence import PROGRAMS
from bpuverify.utage.coverage.instruction_confidence import Coverage
from bpuverify.utage.case.instruction_confidence import check_instruction_confidence


@pytest.mark.feature('BPU-UTAGE-014')
@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.label)
async def test_instruction_confidence_never_inherits_another_concurrent_branch(utage_agent,request,program):
    evidence=dict(program=program.state(),status='INCOMPLETE')
    try:await check_instruction_confidence(utage_agent,program,Coverage(program),evidence)
    finally:request.node.user_properties.append(('semantic_utage_instruction_confidence',json.dumps(evidence,sort_keys=True)))
