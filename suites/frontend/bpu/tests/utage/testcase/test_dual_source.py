"""Warm short/long branch experiences share one genuine executed prefix."""
import json
import pytest
from suites.frontend.bpu.utage.model.dual_source import PROGRAMS
from suites.frontend.bpu.utage.coverage.dual_source import Coverage
from suites.frontend.bpu.utage.case.dual_source import check_dual_source


def parameters():
    for program in PROGRAMS:
        marks = []
        if program.result in ('later-direct','later-indirect'):
            marks = [pytest.mark.feature('BPU-UTAGE-013'),pytest.mark.feature('BPU-UTAGE-025')]
        yield pytest.param(program,id=program.label,marks=marks)


@pytest.mark.feature('BPU-UTAGE-014')
@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.parametrize('program',tuple(parameters()))
async def test_two_warm_providers_learn_only_their_executed_instruction_prefix(utage_agent,request,program):
    evidence = dict(program=program.state(),status='INCOMPLETE')
    try:
        await check_dual_source(utage_agent,program,Coverage(program),evidence)
    finally:
        request.node.user_properties.append(('semantic_utage_dual_source',json.dumps(evidence,sort_keys=True)))
