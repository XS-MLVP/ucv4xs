"""A known tag-width failure must become XPASS when the DUT is corrected."""

from bpuverify.common.env.artifacts import output_path
from bpuverify.common.env.artifacts import write_output
from copy import deepcopy
from dataclasses import asdict
import json

from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.case.definitions import DEFECT_PC
from bpuverify.utage.case.definitions import POSITION
from bpuverify.utage.model.addressing import hash_indices
from bpuverify.utage.model.addressing import prediction_tag
from bpuverify.utage.case.errors import UtageTagWidthMismatch


async def check_guarded_pc_tag_width(agent, output):
    await agent.reset()
    scoreboard = Scoreboard('utage.tag_width_contract')
    def check(expected, actual, point):
        scoreboard.check(expected=expected, actual=actual, context=CheckContext(
            scoreboard=scoreboard.name, mode=ScoreboardMode.DIRECT,
            request=dict(pc=DEFECT_PC, position=POSITION, point=point)))
    cold = await agent.predict(DEFECT_PC, POSITION, 0)
    check(0, cold.hit, 'reset lookup is cold')
    check(hash_indices(DEFECT_PC, 0), tuple(cold.meta['readIndex']), 'independent cold address')
    check((1, POSITION), (cold.meta['abtbResult'][0]['valid'],
        cold.meta['abtbResult'][0]['cfiPosition']), 'genuine base slot')
    transaction = UtageTraining(DEFECT_PC, POSITION, 1, deepcopy(cold.meta))
    async with agent.observe_shadow(table=0) as shadow:
        await agent.train(transaction)
        # The declared defect is a prediction miss caused by tag truncation.
        # Declare that exact logical address so every other field of every
        # other prediction is still compared; the scenario below still has to
        # prove the allocated cell and the width obstruction.
        agent.allow_known_miss(DEFECT_PC, POSITION,
            'BPU-UTAGE-007 prediction tag wider than the training/SRAM tag')
        trained = await agent.predict(DEFECT_PC, POSITION, 0)
        cell, width = deepcopy(shadow.latest['cells'][0]), shadow.tag_width
    full_tag = prediction_tag(DEFECT_PC, 0, 0)
    check(dict(valid=1, index=hash_indices(DEFECT_PC, 0)[0], data_valid=1,
        tag=full_tag & ((1 << width) - 1), position=POSITION, counter=4), cell,
        'actual allocated shadow cell after genuine feedback')
    check(hash_indices(DEFECT_PC, 0), tuple(trained.meta['readIndex']), 'same trained address')
    entry = trained.meta['abtbResult'][0]
    check((1, POSITION), (entry['valid'], entry['cfiPosition']), 'trained slot validity and position')
    check(True, trained.hit in (0, 1), 'prediction hit is boolean')
    result = dict(status='PASS' if trained.hit else 'KNOWN_FAIL', dut='MicroTage',
        issue='prediction GuardedPc tag is wider than training/SRAM tag', pc_addr=hex(DEFECT_PC),
        observed_hit=trained.hit, observed_taken=trained.taken,
        public_feedback=asdict(transaction), full_prediction_tag=full_tag, stored_width=width,
        allocated_shadow_cell=cell, evidence=dict(abtbResult_0=entry, readIndex=trained.meta['readIndex']),
        declared_allowances=list(agent.allowed_reference_events))
    if trained.hit:
        check((1, 0, 4, 1), (entry['hit'], entry['tableId'], entry['takenCtr_value'], trained.taken),
            'architectural provider after training')
    else:
        check(True, full_tag >= (1 << width), 'miss has exact tag-width obstruction')
        check(0, entry['hit'], 'provider metadata also reports miss')
    write_output(output, json.dumps(result, indent=2, sort_keys=True) + '\n')
    if not trained.hit:
        raise UtageTagWidthMismatch(f'lookup must hit after genuine allocation; full_tag={full_tag:#x}, '
            f'stored_width={width}, allocated_cell={cell!r}, observed={asdict(trained)!r}')
    return result
