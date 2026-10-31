"""Only protocol intent; drivers and monitors own launch, association and drain."""
import pytest
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.utage.case.source_ownership import check_request_ownership, check_saved_source
from suites.frontend.bpu.utage.coverage.source_ownership import SourceOwnershipCoverage
from suites.frontend.bpu.utage.model.source_ownership import ASSOCIATION_MODES, AssociationProgram, RecoveryProgram


@pytest.mark.feature('BPU-UTAGE-006')
@pytest.mark.parametrize('mode', ASSOCIATION_MODES)
async def test_distinct_overlapping_requests_keep_complete_owned_responses(utage_agent, mode):
    program = AssociationProgram(mode); coverage = SourceOwnershipCoverage(program)
    try: await check_request_ownership(utage_agent, program, coverage)
    finally: coverage.write(output_directory(REPO_ROOT, 'utage'))


@pytest.mark.parametrize('stage', (
    pytest.param('s2', marks=pytest.mark.feature('BPU-UTAGE-008')),
    pytest.param('s3', marks=pytest.mark.feature('BPU-UTAGE-009'))))
@pytest.mark.parametrize('retag', (False, True), ids=('match', 'retag'))
@pytest.mark.parametrize('learning', (False, True), ids=('stable', 'learning'))
async def test_recovery_owns_saved_age_and_does_not_reread_latest_content(utage_agent, stage, retag, learning):
    program = RecoveryProgram(stage, retag=retag, learning=learning)
    coverage = SourceOwnershipCoverage(program)
    try: await check_saved_source(utage_agent, program, coverage)
    finally: coverage.write(output_directory(REPO_ROOT, 'utage'))
