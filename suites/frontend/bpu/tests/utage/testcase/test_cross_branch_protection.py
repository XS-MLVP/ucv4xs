"""Different matching branches own their delayed correct/agreement/wrong results."""
import json
import pytest
from bpuverify.common.env.artifacts import output_directory
from bpuverify.common.env.paths import REPO_ROOT
from bpuverify.utage.model.cross_branch_protection import PROGRAMS
from bpuverify.utage.coverage.cross_branch_protection import Coverage
from bpuverify.utage.case.cross_branch_protection import check_cross_branch_protection


@pytest.mark.feature('BPU-UTAGE-021')
@pytest.mark.feature('BPU-UTAGE-023')
@pytest.mark.parametrize('program', PROGRAMS, ids=lambda p: p.label)
async def test_distinct_branches_keep_old_protection_qualification(utage_agent, program, request):
    coverage = Coverage(program)
    evidence = dict(program=program.label, status='INCOMPLETE')
    try: await check_cross_branch_protection(utage_agent, program, coverage, evidence)
    finally:
        coverage.write(output_directory(REPO_ROOT, 'utage'))
        request.node.user_properties.append(('semantic_cross_branch_protection', json.dumps(evidence, sort_keys=True)))
