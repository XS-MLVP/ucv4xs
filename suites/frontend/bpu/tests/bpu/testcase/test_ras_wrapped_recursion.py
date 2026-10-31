"""Capacity-wrap recursion is one program lifetime, not a slot sweep."""
import json
import pytest

from suites.frontend.bpu.bpu.model.ras.wrapped_recursion import PROFILES
from suites.frontend.bpu.bpu.coverage.ras_wrapped_recursion import Coverage
from suites.frontend.bpu.bpu.case.ras.wrapped_recursion import check_wrapped_recursion


@pytest.mark.feature('BPU-INT-053')
@pytest.mark.feature('BPU-INT-054')
@pytest.mark.parametrize('calls', PROFILES, ids=('full-recursive-group', 'recursive-group-split'))
async def test_committed_storage_wrap_preserves_recursive_counts_and_retained_older_callers(bpu_agent, request, calls):
    evidence = dict(calls=calls, status='INCOMPLETE')
    try:
        await check_wrapped_recursion(bpu_agent, calls, Coverage(calls), evidence)
    except BaseException as error:
        evidence.update(status='FAIL', first_error_type=type(error).__name__, first_error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_wrapped_recursive_return', json.dumps(evidence, sort_keys=True)))
