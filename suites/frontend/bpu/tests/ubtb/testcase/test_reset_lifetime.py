"""Old MicroBTB records and concurrent feedback cannot cross reset lifetimes."""
import json
import pytest
from suites.frontend.bpu.ubtb.model.reset_lifetime import Program, PROFILES
from suites.frontend.bpu.ubtb.coverage.reset_lifetime import Coverage
from suites.frontend.bpu.ubtb.case.reset_lifetime import check_reset_lifetime


@pytest.mark.feature('BPU-UBTB-001')
@pytest.mark.parametrize('profile', PROFILES)
async def test_reset_separates_original_learning_and_fresh_reliability_lifetimes(ubtb_agent, request, profile):
    program = Program(profile)
    evidence = dict(program=program.state(), status='INCOMPLETE')
    try:
        await check_reset_lifetime(ubtb_agent, program, Coverage(program), evidence)
    except BaseException as error:
        evidence.update(status='FAIL', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_ubtb_reset_lifetime', json.dumps(evidence, sort_keys=True)))
