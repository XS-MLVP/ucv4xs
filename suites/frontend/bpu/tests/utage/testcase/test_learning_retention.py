"""Both drive modes obey the same learning-persistence requirement."""
import json

import pytest

from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.utage.case.learning_retention import check_learning_retention
from suites.frontend.bpu.utage.coverage.learning_retention import LearningRetentionCoverage
from suites.frontend.bpu.utage.model.working_set import WorkingSetProgram


@pytest.mark.feature('BPU-UTAGE-016')
@pytest.mark.parametrize('mode', ('serial', 'adjacent'))
async def test_learning_survives_other_identities_without_own_relearning(utage_agent, request, mode):
    program = WorkingSetProgram('turnover', mode)
    coverage = LearningRetentionCoverage(program)
    try:
        await check_learning_retention(utage_agent, program, coverage)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))
        if coverage.evidence is not None:
            request.node.user_properties.append(('semantic_delayed_retention', json.dumps(coverage.evidence, sort_keys=True)))
