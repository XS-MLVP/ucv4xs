"""Real neutral S2 correction cancels a genuinely decoded younger CALL or RET."""
import json
from bpuverify.bpu.bundle.ras_micro import micro_ras_binding
from bpuverify.bpu.bundle.values import _plain
from bpuverify.bpu.checker.ras.micro import MicroRasChecker
from bpuverify.bpu.checker.ras.correction import check_program_output, check_correction, check_wrong_path_absent
from bpuverify.bpu.case.ras.early import early_program
from bpuverify.bpu.case.ras.common import revisit_from_redirect
from bpuverify.bpu.env.ras.retirement import BpuRetirement
from bpuverify.bpu.monitor.ras.micro import MicroRasMonitor
from bpuverify.bpu.transaction.types import BpuRedirect, BpuTraining
from bpuverify.bpu.coverage.ras_micro import MicroRasEvents


def correction_program(younger_action=2):
    if type(younger_action) is not int or younger_action not in (1,2):
        raise ValueError('younger operation must be CALL or RETURN')
    plan = early_program(1)
    neutral = plan[3]
    wrong_path = dict(pc=neutral['pc'] + 16, target=0x40010c00,
        position=15, action=younger_action, branch_type=2 if younger_action==2 else 3)
    return plan, wrong_path


async def check_neutral_correction(agent, output, *, younger_action=2):
    plan, wrong_path = correction_program(younger_action)
    neutral, older = plan[3], plan[2]
    coverage=MicroRasEvents()
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
            # Leave the neutral jump until LAST. With UBtb disabled for its
            # complete preparation, no resolve or fastTrain can warm its key.
            training = [row for row in plan if row['action']] + [wrong_path]
            for index, row in enumerate(training):
                if index:
                    current = await revisit_from_redirect(agent, row['pc'], current.meta.redirect)
                checker.check((row['pc'], 0), (current.prediction.start_pc, current.prediction.taken),
                    'genuine cold context for early call or return')
                await agent.train(BpuTraining(row['pc'], row['position'], row['target'], current.meta.resolve,
                    branch_type=row['branch_type'], ras_action=row['action']), prediction_pause=True)
            await agent.configure_predictors(ubtb=False, settle=True)
            current = await revisit_from_redirect(agent, neutral['pc'], current.meta.redirect)
            checker.check((neutral['pc'], 0), (current.prediction.start_pc, current.prediction.taken),
                'genuine cold neutral MainBTB source')
            await agent.train(BpuTraining(neutral['pc'], neutral['position'], neutral['target'], current.meta.resolve,
                branch_type=neutral['branch_type'], ras_action=0), prediction_pause=True)
            await agent.set_ready(prediction=False, meta=True)
            await retirement.coherent.drain()
            await agent.configure_predictors(ubtb=True, ras=True, settle=True)
            boundary = await agent.redirect(BpuRedirect(plan[0]['pc'], first.meta.redirect))
            await agent.set_ready(prediction=True, meta=True)
            correction = None
            for row in plan:
                transaction = await agent.next_transaction(start_pc=row['pc'], after_tick=boundary)
                checker.raise_failure()
                witness = check_program_output(checker, retirement.phr, transaction, row,
                    cold_neutral=(row['action'] == 0))
                completed.append((transaction, row['action']))
                witnesses.append(witness)
                if row['action'] == 0:
                    correction = check_correction(checker, retirement.phr, transaction, older, neutral, wrong_path)
                    coverage.require('neutral-S2-cancel-S1-CALL' if younger_action==2 else 'neutral-S2-cancel-S1-RETURN',
                        correction['tick'],check=checker.check)
            checker.check([2, 2, 2, 4, 2, 2], [b[0].prediction_tick - a[0].prediction_tick
                for a, b in zip(completed, completed[1:])], 'three adjacent calls then one real correction bubble')
            await agent.set_ready(prediction=False, meta=True)
            await retirement.coherent.drain()
            check_wrong_path_absent(checker, retirement.phr, retirement.checker, wrong_path, boundary)
            await retirement.retire_many([(tx, action) for tx, action in completed if action])
            checker.raise_failure()
            checker.check(0, retirement.checker.reference.head, 'all real call frames returned, no wrong-path operation')
            summary = retirement.checker.summary()
            checker.check((6, 6), (summary['accepted'], summary['applied']), 'six genuine ordered retirements')
            result = dict(passed=True, operations=[dict(input=row, prediction_tick=tx.prediction_tick,
                meta_tick=tx.meta_tick) for row, (tx, _) in zip(plan, completed, strict=True)],
                wrong_path=wrong_path, witnesses=witnesses, correction=correction,
                micro=checker.finish(), retirement=summary, phr=retirement.phr.summary(),
                full_FTQ_legality_proven=False)
            (output/'neutral-ras-correction-summary.json').write_text(json.dumps(result, indent=2)+'\n')
            return result
        except BaseException as error:
            coverage.fail(error)
            (output/'neutral-ras-correction-failure.json').write_text(json.dumps(dict(failure=repr(error),
                completed=len(completed), recent=list(checker.records)[-12:],
                latched_failure=repr(checker.failure),events=coverage.summary()), indent=2)+'\n')
            raise
        finally:
            await monitor.aclose()
            coverage.write(output,f'neutral-{younger_action}')
