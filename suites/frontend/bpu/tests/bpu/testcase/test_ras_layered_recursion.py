"""Multiple recursive owners survive inner split, target correction and unwind."""
import json
import pytest
from suites.frontend.bpu.bpu.model.ras.layered_recursion import Program, PROFILES
from suites.frontend.bpu.bpu.coverage.ras_layered_recursion import Coverage
from suites.frontend.bpu.bpu.case.ras.layered_recursion import check_layered_recursion


@pytest.mark.feature('BPU-INT-033')
@pytest.mark.feature('BPU-INT-054')
@pytest.mark.parametrize('calls', PROFILES, ids=('inner-full-group', 'inner-nonzero-split-group'))
async def test_independent_recursive_layers_preserve_each_others_counts_and_return_identities(bpu_agent, request, calls):
    program = Program(calls)
    evidence = dict(program=program.state(), status='INCOMPLETE')
    try:
        await check_layered_recursion(bpu_agent, program, Coverage(program), evidence)
    except BaseException as error:
        evidence.update(status='FAIL', first_error_type=type(error).__name__, first_error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_layered_recursive_return', json.dumps(evidence, sort_keys=True)))
