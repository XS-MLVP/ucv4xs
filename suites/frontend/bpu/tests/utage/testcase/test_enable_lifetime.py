"""Short/long direction learning straddles the same semantic enable boundary."""
import json
import pytest

from bpuverify.utage.model.enable_lifetime import Program, TABLES, PHASES
from bpuverify.utage.coverage.enable_lifetime import Coverage
from bpuverify.utage.case.enable_lifetime import check_enable_lifetime


@pytest.mark.feature('BPU-UTAGE-012')
@pytest.mark.parametrize('table', TABLES, ids=('short', 'long'))
@pytest.mark.parametrize('phase', PHASES)
async def test_disable_distinguishes_unqualified_original_from_already_qualified_learning(utage_agent, request, table, phase):
    program = Program(table, phase)
    evidence = dict(program=program.state(), status='INCOMPLETE')
    try:
        await check_enable_lifetime(utage_agent, program, Coverage(program), evidence)
    except BaseException as error:
        evidence.update(status='FAIL', first_error_type=type(error).__name__, first_error=str(error))
        raise
    finally:
        request.node.user_properties.append(('semantic_enable_learning_lifetime', json.dumps(evidence, sort_keys=True)))
