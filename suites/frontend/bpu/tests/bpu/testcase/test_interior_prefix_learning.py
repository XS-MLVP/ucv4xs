"""Real original prefix feedback updates current versions without old bound hints."""
import json
import pytest
from suites.frontend.bpu.runtime.artifacts import output_directory
from suites.frontend.bpu.runtime.paths import REPO_ROOT
from suites.frontend.bpu.bpu.model.tage.interior_prefix_learning import PROGRAMS
from suites.frontend.bpu.bpu.coverage.interior_prefix_learning import Coverage
from suites.frontend.bpu.bpu.case.interior_prefix_learning import check_interior_prefix


@pytest.mark.feature('BPU-INT-086')
@pytest.mark.parametrize('program',PROGRAMS,ids=lambda p:p.name)
async def test_interior_original_prefix_preserves_both_current_learnings(bpu_agent,request,program):
    evidence=dict(program=program.name,status='INCOMPLETE');coverage=Coverage(program)
    try:
        await check_interior_prefix(bpu_agent,program,coverage,evidence);evidence['status']='PASS'
    except BaseException:
        evidence['status']='FAIL';raise
    finally:
        coverage.write(output_directory(REPO_ROOT,'bpu'))
        request.node.user_properties.append(('semantic_interior_prefix_learning',json.dumps(evidence,sort_keys=True)))
