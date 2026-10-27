"""Learning persistence is a logical lifetime, not a bank or set matrix."""
import json
import pytest

from bpuverify.utage.model.learning_persistence import Program, PROFILES, MODES
from bpuverify.utage.coverage.learning_persistence import Coverage
from bpuverify.utage.case.learning_persistence import run


@pytest.mark.feature('BPU-UTAGE-015')
@pytest.mark.feature('BPU-UTAGE-016')
@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('mode', MODES)
async def test_original_learning_survives_version_retirement_and_fresh_consumers(utage_agent, request, profile, mode):
    program = Program(profile, mode)
    evidence = dict(program=program.state(), status='INCOMPLETE')
    try:
        await run(utage_agent, program, Coverage(program), evidence)
    finally:
        request.node.user_properties.append(('semantic_utage_learning_persistence', json.dumps(evidence, sort_keys=True)))
