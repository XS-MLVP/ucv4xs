"""A cycle recovery must use the installed D CFI, not the self-loop formula."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from toffee import Scoreboard, ScoreboardMismatch

from suites.frontend.bpu.bpu.env.bypass.sparse import SparseProgramEnvironment
from suites.frontend.bpu.bpu.model.bypass.sparse import recipe
from suites.frontend.bpu.bpu.transaction.types import BpuPrediction, BpuMeta, BpuTransaction


@pytest.mark.parametrize('fault', (None, 'source_A', 'target', 'position', 'branch_type', 'valid'))
async def test_recovery_requires_the_actual_installed_D_to_A_checkpoint(fault):
    program = recipe()['old']
    pc = program['nodes'][3]
    checkpoint = BpuTransaction(10, 14, BpuPrediction(pc, program['pc'], 1, 7, 0, 0),
        BpuMeta({}, dict(phr=dict(phrLowBits=program['negative'][pc]['history'] & 8191)), None))
    final = dict(valid=1, pc=pc, target=program['pc'], taken=1, position=7, branch_type=3)
    if fault == 'source_A':
        checkpoint = replace(checkpoint, prediction=replace(checkpoint.prediction, start_pc=program['pc']))
    elif fault is not None:
        final[fault] ^= 1
    board = Scoreboard('sparse.recovery')
    checker = SimpleNamespace(records=[dict(tick=14, abtb=dict(final=final))],
        compare=lambda expected, actual, **details: board.check(expected=expected, actual=actual))
    submitted = []
    async def redirect(payload):
        submitted.append(payload)
        return 18
    async def wait(operation, label, cycles):
        return await operation
    env = SparseProgramEnvironment(SimpleNamespace(redirect=redirect), checker, None, {})
    env.wait = wait
    if fault is None:
        assert await env.restore_steady(program, checkpoint) == 18
        assert len(submitted) == 1
        payload = submitted[0].payload()
        assert payload == dict(meta=checkpoint.meta.redirect, target=program['pc'],
                               cfi_pc=(pc & ~7) + 7, taken=1, branch_type=3, ras_action=0)
        assert payload['cfi_pc'] != (program['pc'] & ~7) + program['position']
    else:
        with pytest.raises(ScoreboardMismatch):
            await env.restore_steady(program, checkpoint)
        assert not submitted
