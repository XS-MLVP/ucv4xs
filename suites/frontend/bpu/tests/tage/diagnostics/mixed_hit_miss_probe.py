"""Real two-branch hit/allocation diagnostic, excluded from formal coverage."""

from __future__ import annotations
import ucv.runtime as ucv_paths

import argparse
import asyncio
from dataclasses import asdict
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

from toffee import Execution
from toffee import Scoreboard
from toffee import XCommClockBackend

from bpuverify.tage.agent.main import TageAgent
from bpuverify.tage.transaction.types import TageBaseBranch
from bpuverify.tage.transaction.types import TageBatchTraining
from bpuverify.tage.transaction.types import TageBranchFeedback
from bpuverify.common.env.dut import initialize_dut_inputs
from bpuverify.tage.case.definitions import HIGHEST_TABLE
from bpuverify.tage.case.way_migration_scenario import cell
from bpuverify.tage.case.way_migration_scenario import prepare_unprotected_highest_ways
from bpuverify.tage.case.way_migration_scenario import read_grid
from bpuverify.tage.case.way_migration_scenario import snapshot

ROOT = Path(__file__).resolve().parents[3]


async def scenario(agent, pc):
    # Only the highest-table way1 may be replaced. The lower six residents
    # remain protected; the existing way0 is made strongly not-taken/useful.
    await prepare_unprotected_highest_ways(agent, pc, origin_way=1)
    residents = await read_grid(agent, pc, positions=tuple(range(9)))
    target = next(position for position, pred in residents.items() if cell(pred) == (HIGHEST_TABLE, 0))
    victim = next(position for position, pred in residents.items() if cell(pred) == (HIGHEST_TABLE, 1))
    async with agent.observe_training() as observed:
        for expected_counter in range(6, -1, -1):
            prediction = await agent.predict(pc, target, 1, base_conf=1)
            assert cell(prediction) == (HIGHEST_TABLE, 0)
            await agent.train_checked(TageBatchTraining(pc, (TageBranchFeedback(
                target, 0, 1, prediction.meta,
                mispredict=int((prediction.taken if prediction.valid else 1) != 0)),)), observed)
            after = await agent.predict(pc, target, 1, base_conf=1)
            assert after.meta['providerTakenCtr_value'] == expected_counter, after
        for _ in range(3):
            prediction = await agent.predict(pc, target, 1, base_conf=1)
            await agent.train_checked(TageBatchTraining(pc, (TageBranchFeedback(
                target, 0, 1, prediction.meta, mispredict=0),)), observed)
        # Counter=0 with actual NT is deliberately optimized into no write.
        # Rearm it to 1 so the mixed beat must perform a real 1->0 update,
        # while remaining an earlier not-taken branch in a legal FTQ beat.
        prediction = await agent.predict(pc, target, 0)
        assert prediction.meta['providerTakenCtr_value'] == 0
        await agent.train_checked(TageBatchTraining(pc, (TageBranchFeedback(
            target, 1, 0, prediction.meta, mispredict=1),)), observed)
        before = await read_grid(agent, pc, positions=tuple(range(9)))
        assert before[target].meta['providerTakenCtr_value'] == 1
        assert before[target].meta['providerUsefulCtr_value'] == 3
        assert before[victim].meta['providerUsefulCtr_value'] == 0
        newcomer = 9
        assert target < newcomer and newcomer not in before
        prediction = await agent.predict_branches(
            pc, (TageBaseBranch(target, 0), TageBaseBranch(newcomer, 0)))
        assert prediction.metas[0]['providerTakenCtr_value'] == 1
        assert prediction.metas[0]['providerWayIdx'] == 0
        assert prediction.metas[1]['hasProvider'] == 0
        transaction = TageBatchTraining(pc, (
            TageBranchFeedback(target, 0, 0, prediction.metas[0], mispredict=0),
            TageBranchFeedback(newcomer, 1, 0, prediction.metas[1], mispredict=1),
        ))
        start = len(observed)
        await agent.train_checked(transaction, observed)
        assert len(observed) == start + 1
        accepted = observed[-1]
        checks = Scoreboard('tage.mixed_hit_allocation_probe')
        transfers = [agent.submit_predict(pc, position, 0) for position in (*before, newcomer)]
        await agent.drain_predictions()
        final = {position: await transfer for position, transfer in zip((*before, newcomer), transfers, strict=True)}
        for position in before:
            if position == victim:
                checks.check(expected=0, actual=final[position].meta['hasProvider'])
            else:
                expected = snapshot(before[position])
                if position == target:
                    expected['meta'] = dict(expected['meta'], providerTakenCtr_value=0)
                checks.check(expected=expected, actual=snapshot(final[position]))
        new = final[newcomer]
        checks.check(expected={'cell': (HIGHEST_TABLE, 1), 'counter': 4, 'useful': 0,
                               'has_alt': 0, 'valid': 1, 'taken': 1},
                     actual={'cell': cell(new), 'counter': new.meta['providerTakenCtr_value'],
                             'useful': new.meta['providerUsefulCtr_value'], 'has_alt': new.meta['hasAlt'],
                             'valid': new.valid, 'taken': new.taken})
        return {'pc': pc, 'target': target, 'victim': victim, 'newcomer': newcomer,
                'accepted_feedback': {'tick': accepted.event.tick, 'value': accepted.value},
                'before': {position: snapshot(pred) for position, pred in before.items()},
                'after': {position: snapshot(pred) for position, pred in final.items()},
                'checks': asdict(checks.status)}


async def probe(arguments):
    report_path = arguments.report.resolve()
    protected = tuple(ROOT/'results'/name for name in (
        'feature-points.json', 'rtl-coverage-manifest.json',
        'rtl-line-coverage.json', 'verification-report.html'))
    if report_path in protected:
        raise ValueError('diagnostic output cannot overwrite formal evidence')
    before = {str(path): sha256(path.read_bytes()).hexdigest() for path in protected}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    raw = report_path.with_name('probe-'+report_path.stem+'-coverage.dat')
    package = ROOT/'dut/tage'
    spec = importlib.util.spec_from_file_location(
        'tage_mixed_hit_miss_diagnostic', package/'__init__.py',
        submodule_search_locations=[str(package)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    cls = next(value for name, value in vars(module).items() if name.startswith('DUT'))
    dut = cls(module.xsp.StringVector(['tage', ucv_paths.native_seed()]), coverage_filename=str(raw))
    try:
        dut.InitClock('clock')
        initialize_dut_inputs(dut)
        async with Execution(XCommClockBackend(dut.GetXClock()), max_batch_ticks=256) as execution:
            agent = await TageAgent(dut).start(execution)
            try:
                observations = await scenario(agent, arguments.pc)
            finally:
                await agent.aclose()
    finally:
        dut.Finish()
        assert before == {str(path): sha256(path.read_bytes()).hexdigest() for path in protected}
    result = {'format': 'bpu-tage-mixed-hit-miss-probe', 'version': 1,
              'scope': 'normal genuine-metadata transactions, not formal pytest/functional coverage',
              'probe_script': str(Path(__file__).resolve()), 'raw_file': str(raw), 'seed': 1,
              'observations': observations, 'formal_reports_preserved_byte_for_byte': True,
              'protected_sha256': before}
    report_path.write_text(json.dumps(result, indent=2)+'\n')
    print('mixed hit/allocation payload and all six protected neighbors checked; formal reports preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--pc', type=lambda value: int(value, 0), default=0x40000000)
    asyncio.run(probe(parser.parse_args()))
