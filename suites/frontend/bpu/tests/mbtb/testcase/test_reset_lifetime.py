"""Warm and registered-feedback reset lifetimes through normal MainBTB agent."""
import json
import pytest
from bpuverify.mbtb.model.reset_lifetime import Program, PROFILES
from bpuverify.mbtb.coverage.reset_lifetime import Coverage
from bpuverify.mbtb.case.reset_lifetime import check_reset_lifetime


@pytest.mark.feature('BPU-MBTB-001')
@pytest.mark.parametrize('profile', PROFILES)
async def test_reset_terminates_old_branch_and_learning_lifetimes(mbtb_agent, request, profile):
    program = Program(profile)
    evidence = dict(program=program.state(), status='INCOMPLETE')
    try:
        await check_reset_lifetime(mbtb_agent, program, Coverage(program), evidence)
    except BaseException as error:
        evidence.update(status='FAIL', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_mbtb_reset_lifetime', json.dumps(evidence, sort_keys=True)))
