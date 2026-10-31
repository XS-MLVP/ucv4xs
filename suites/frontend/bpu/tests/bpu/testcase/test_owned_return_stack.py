"""Real call/return originals, not bank or pointer enumeration."""
import json
import pytest

from suites.frontend.bpu.bpu.case.owned_return_stack import check_owned_return_stack
from suites.frontend.bpu.bpu.coverage.owned_return_stack import OwnedReturnCoverage
from suites.frontend.bpu.bpu.model.owned_return_stack import PROGRAMS


def parameters():
    for p in PROGRAMS:
        marks=[pytest.mark.feature('BPU-INT-008'),pytest.mark.feature('BPU-INT-052')]
        if p.mode!='natural-return':
            marks.append(pytest.mark.feature('BPU-INT-080' if p.mode=='call-replay' else 'BPU-INT-081'))
        yield pytest.param(p,id=p.label,marks=marks)


@pytest.mark.parametrize('program',tuple(parameters()))
async def test_call_return_recovery_and_commit_use_the_exact_owned_original(bpu_agent,request,program):
    coverage=OwnedReturnCoverage(program)
    evidence=dict(profile=program.label,status='INCOMPLETE')
    try:
        await check_owned_return_stack(bpu_agent,program,coverage,evidence)
    except BaseException as error:
        evidence.update(status='FAIL',first_error_type=type(error).__name__,first_error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_owned_return_stack',json.dumps(evidence,ensure_ascii=False)))
