"""Human intent only; shared environment owns signals, timing and association."""
import json
import pytest

from bpuverify.bpu.model.ras.nested_recursion import PROFILES
from bpuverify.bpu.coverage.ras_nested_recursion import Coverage
from bpuverify.bpu.case.ras.nested_recursion import check_nested_recursion


@pytest.mark.feature('BPU-INT-033')
@pytest.mark.feature('BPU-INT-054')
@pytest.mark.parametrize('calls', PROFILES, ids=('one-recursive-group', 'split-recursive-group'))
async def test_all_recursive_returns_reach_the_distinct_outer_caller(bpu_agent, request, calls):
    coverage, evidence = Coverage(calls), dict(calls=calls, status='INCOMPLETE')
    try:
        await check_nested_recursion(bpu_agent, calls, coverage, evidence)
    except BaseException as error:
        evidence.update(status='FAIL', first_error_type=type(error).__name__, first_error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_nested_recursive_return', json.dumps(evidence, sort_keys=True)))
