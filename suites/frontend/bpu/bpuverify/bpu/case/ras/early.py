"""Natural early call/return overlap, not a synthetic stage-pin matrix."""
from dataclasses import asdict
import json
from bpuverify.bpu.bundle.ras_micro import micro_ras_binding
from bpuverify.bpu.bundle.values import _plain
from bpuverify.bpu.checker.ras.micro import MicroRasChecker
from bpuverify.bpu.env.ras.retirement import BpuRetirement
from bpuverify.bpu.monitor.ras.micro import MicroRasMonitor
from bpuverify.bpu.transaction.types import BpuRedirect, BpuTraining, BpuStage1Source
from bpuverify.bpu.case.ras.common import revisit_from_redirect
from bpuverify.bpu.coverage.ras_micro import MicroRasEvents


def early_program(gap):
    if type(gap) is not int or gap not in (0, 1):
        raise ValueError('gap selects adjacent return or one neutral operation')
    calls = (0x40010800, 0x40010840, 0x40010880)
    body, neutral = 0x40010a00, 0x40010900
    rows = [dict(pc=pc, target=calls[i+1] if i < 2 else neutral if gap else body,
        branch_type=2, action=2, position=15) for i, pc in enumerate(calls)]
    if gap:
        rows.append(dict(pc=neutral, target=body, branch_type=2, action=0, position=15))
    rows += [dict(pc=pc, target=target, branch_type=3, action=1, position=15)
        for pc, target in zip((body, calls[2]+16, calls[1]+16),
            (calls[2]+16, calls[1]+16, calls[0]+16), strict=True)]
    return rows


async def check_early_calls(agent, output, *, gap):
    plan, coverage = early_program(gap), MicroRasEvents()
    checker = MicroRasChecker(coverage=coverage)
    monitor = MicroRasMonitor(micro_ras_binding(agent), decoder=_plain)
    completed, witnesses = [], []
    async with BpuRetirement(agent) as retirement:
        monitor.start(agent._execution, observer=checker.capture)
        try:
            await agent.reset(plan[0]['pc'])
            initial = await agent.next_transaction(start_pc=plan[0]['pc'])
            await agent.configure_predictors(ubtb=True, abtb=False, tage=False, sc=False,
                ittage=False, ras=False, mbtb=True, settle=True)
            first = await revisit_from_redirect(agent, plan[0]['pc'], initial.meta.redirect)
            current = first
            for index, row in enumerate(plan):
                checker.check((row['pc'], 0), (current.prediction.start_pc, current.prediction.taken),
                    'genuine cold training context')
                await agent.train(BpuTraining(row['pc'], row['position'], row['target'], current.meta.resolve,
                    branch_type=row['branch_type'], ras_action=row['action']), prediction_pause=True)
                if index+1 < len(plan):
                    current = await revisit_from_redirect(agent, plan[index+1]['pc'], current.meta.redirect)
            await agent.configure_predictors(ras=True, settle=True)
            boundary = await agent.redirect(BpuRedirect(plan[0]['pc'], first.meta.redirect))
            for row in plan:
                transaction = await agent.next_transaction(start_pc=row['pc'], after_tick=boundary)
                checker.raise_failure()
                checker.check(dict(start_pc=row['pc'], target=row['target'], taken=1,
                    position=row['position'], s2_override=0, s3_override=0),
                    asdict(transaction.prediction), 'natural S1 program prediction', input=row)
                checker.check(BpuStage1Source.UBTB, transaction.meta.perf.s1_source, 'real early source')
                frames = [frame for frame in checker.records if frame['tick'] == transaction.prediction_tick]
                checker.check(1, len(frames), 'exact accepted S1 source')
                frame = frames[0]
                checker.check((1, row['pc'], row['position'], row['action']),
                    (frame['inputs']['fire1'], frame['inputs']['s1']['pc'], frame['inputs']['s1']['position'],
                     frame['inputs']['s1']['action']), 'actual MicroRAS operation and acceptance')
                completed.append((transaction, row['action']))
                witnesses.append(frame)
            checker.check([2]*(len(plan)-1), [b[0].prediction_tick-a[0].prediction_tick
                for a, b in zip(completed, completed[1:])], 'one early operation per cycle')
            required = 's1-pop/s3-push' if gap else 's1-pop/s2-push/s3-push'
            checker.check(True, any(frame['route'] == required for frame in witnesses),
                'required independently predicted overlap', required=required)
            interaction = next(frame for frame in witnesses if frame['route']==required)
            coverage.require('return-pairs-S3-uses-main' if gap else 'return-pairs-S2-forwards-S3',
                interaction['tick'],check=checker.check)
            await agent.set_ready(prediction=False, meta=True)
            await retirement.coherent.drain()
            await retirement.retire_many([(tx, action) for tx, action in completed if action])
            checker.raise_failure()
            checker.check(0, retirement.checker.reference.head, 'all three call frames returned')
            result = dict(passed=True, gap=gap, operations=[dict(input=row, prediction_tick=tx.prediction_tick,
                meta_tick=tx.meta_tick) for row,(tx,_) in zip(plan, completed, strict=True)],
                witnesses=witnesses, micro=checker.finish(), retirement=retirement.checker.summary(),
                phr=retirement.phr.summary(), full_FTQ_legality_proven=False)
            (output/f'early-ras-{gap}-summary.json').write_text(json.dumps(result, indent=2)+'\n')
            return result
        except BaseException as error:
            coverage.fail(error)
            (output/f'early-ras-{gap}-failure.json').write_text(json.dumps(dict(failure=repr(error),
                completed=len(completed), recent=list(checker.records)[-12:], summary=checker.summary()
                if checker.failure is None else dict(failure=repr(checker.failure))), indent=2)+'\n')
            raise
        finally:
            await monitor.aclose()
            coverage.write(output,f'early-{gap}')
