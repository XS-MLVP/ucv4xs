"""Test intent; timing, matching, comparison and native access live in the library."""

from bpuverify.common.env.trace import dump_trace
from contextlib import AsyncExitStack
from copy import deepcopy
from dataclasses import asdict

from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.checker.checking import UtageUsefulChecker
from bpuverify.utage.model.addressing import FOLD_LAYOUT
from bpuverify.utage.model.addressing import fold_history
from bpuverify.utage.model.addressing import hash_indices
from bpuverify.utage.model.addressing import prediction_tag

PC, POSITION = 0x40000000, 5


class UsefulContext:
    def __init__(self, agent, *, mode, name, index, output, allocation_coverage=None,
                 update_coverage=None, shadow=False):
        self.agent, self.mode, self.name, self.index, self.output = agent, mode, name, index, output
        self.checker = UtageUsefulChecker(mode=mode, allocation_coverage=allocation_coverage,
            update_coverage=update_coverage, scope=dict(scenario=name, index=index))
        self.predictions, self.operations = [], []
        self.shadow_needed = shadow
        self.shadow = None
        self.stack = AsyncExitStack()

    async def __aenter__(self):
        await self.agent.reset()
        await self.stack.__aenter__()
        try:
            await self.stack.enter_async_context(self.agent.observe_useful(self.checker))
            if self.shadow_needed:
                self.shadow = await self.stack.enter_async_context(self.agent.observe_shadow(table=0))
        except BaseException:
            await self.stack.aclose()
            raise
        return self

    async def __aexit__(self, kind, error, traceback):
        failure = error
        summary = None
        try:
            await self.stack.__aexit__(kind, error, traceback)
            if error is None:
                summary = self.checker.summary()
        except BaseException as caught:
            failure = caught
            raise
        finally:
            result = dict(scenario=self.name, index=self.index, mode=self.mode,
                predictions=self.predictions, public_operations=self.operations,
                passive_trace=self.checker.records, formal_credit=False,
                summary=summary,
                failure=None if failure is None else repr(failure),
                shadow_trace=None if self.shadow is None else self.shadow.trace)
            path = self.output / f'{self.name}-{self.index:03d}-{self.mode}.json'
            dump_trace(path, result)

    def check(self, expected, actual, *, point):
        from toffee import CheckContext
        from toffee import ScoreboardMode
        context = CheckContext(scoreboard=self.checker.scoreboard.name, mode=ScoreboardMode.DIRECT,
            request=dict(scenario=self.name, index=self.index, cadence=self.mode, point=point),
            observed_event=self.checker._last_event)
        self.checker.scoreboard.check(expected=expected, actual=actual, context=context)

    async def predict(self, pc, history, base, *, expected=None, position=POSITION,
                      index_pc=None, index_history=None):
        observed = await self.agent.predict(pc, position, base, folded_history=history,
                                           index_pc=index_pc, index_history=index_history)
        return self.check_prediction(observed, pc, history, base, expected=expected, position=position,
                                     index_pc=index_pc, index_history=index_history)

    def check_prediction(self, observed, pc, history, base, *, expected=None, position=POSITION,
                         index_pc=None, index_history=None):
        """The same complete comparison for serial and bound pipeline responses."""
        meta, entry = observed.meta, observed.meta['abtbResult'][0]
        read_pc, read_history = (pc if index_pc is None else index_pc,
                                 history if index_history is None else index_history)
        self.check(hash_indices(read_pc, read_history), tuple(meta['readIndex']), point='hash index routing')
        self.check([dict(foldedHist=fold_history(history, length, width)) for length, width in FOLD_LAYOUT],
            list(meta['foldedPathHistForTrain_hist']), point='complete folded history')
        self.check((1, base, position), (entry['valid'], entry['baseTaken'], entry['cfiPosition']), point='valid base position')
        self.check(0, entry['baseIsStrongBias'], point='complete non-strong-bias base metadata')
        self.check(observed.hit, entry['hit'], point='public hit agrees with training provider metadata')
        if observed.hit:
            self.check(observed.taken, entry['predTaken'], point='public direction agrees with training provider metadata')
        self.check((1, 0, 0, 0), tuple(slot['valid'] for slot in meta['abtbResult']), point='single valid slot')
        self.check(tuple(range(position, position + 4)), tuple(slot['cfiPosition'] for slot in meta['abtbResult']), point='padding position alignment')
        actual = (observed.hit, entry['tableId'], entry['takenCtr_value'], observed.taken)
        if expected is not None:
            for field, wanted, value in zip(('hit', 'provider', 'taken counter', 'direction'), expected, actual, strict=True):
                if wanted is not None:
                    self.check(wanted, value, point='public ' + field)
        self.predictions.append(dict(pc=pc, history=history, index_pc=read_pc, index_history=read_history,
                                     base=base, position=position, observed=asdict(observed)))
        return observed

    async def feedback(self, pc, prediction, actual, *, count=1, phase):
        position = prediction.meta['abtbResult'][0]['cfiPosition']
        transactions = tuple(UtageTraining(pc, position, actual, deepcopy(prediction.meta),
            mispredict=int(actual != prediction.taken)) for _ in range(count))
        self.checker.plan(transactions, phase=phase)
        self.operations.extend(dict(phase=phase, transaction=asdict(transaction)) for transaction in transactions)
        if self.mode == 'adjacent':
            await self.agent.train_many(transactions)
        else:
            for transaction in transactions:
                await self.agent.train(transaction)
        self.checker.finish_phase()


async def check_allocation_routes(agent, coverage, output, *, indices=range(512)):
    indices = tuple(indices)
    for mode in ('serial', 'adjacent'):
        async with UsefulContext(agent, mode=mode, name='lower-allocation', index=-1,
                output=output, allocation_coverage=coverage, shadow=True) as run:
            for index in indices:
                pc = PC + index
                cold = await run.predict(pc, 0, 0, expected=(0, None, None, None))
                await run.feedback(pc, cold, 1, phase=f'allocate-lower-{index}')
                tag = prediction_tag(pc, 0, 0)
                if tag < 256:
                    await run.predict(pc, 0, 0, expected=(1, 0, 4, 1))
                else:
                    # The useful allocation itself was already compared by the
                    # dense useful observer on the feedback boundary. This
                    # later prediction can only miss because of the declared
                    # tag-width defect; declare that exact address, then prove
                    # the genuine allocated cell instead of pretending a hit.
                    agent.allow_known_miss(pc, POSITION,
                        'BPU-UTAGE-007 lower-table tag truncation')
                    await run.predict(pc, 0, 0, expected=(0, None, None, None))
                    slot = (run.shadow.latest['enq'] - 1) % len(run.shadow.latest['cells'])
                    cell = run.shadow.latest['cells'][slot]
                    run.check(dict(valid=1, index=index, data_valid=1,
                        tag=tag & ((1 << run.shadow.tag_width) - 1), position=POSITION,
                        counter=4), cell, point='genuine allocated truncated shadow tag')
                    run.predictions[-1]['known_defect_observation_not_correctness_pass'] = 'BPU-UTAGE-007'
        async with UsefulContext(agent, mode=mode, name='upper-allocation', index=-1,
                output=output, allocation_coverage=coverage) as run:
            # Keep64lower useful registers nonzero. A position6 miss then
            # allocates upper directly, without requiring any forged hit.
            for index in sorted({index & 63 for index in indices}):
                cold = await run.predict(PC, index, 0, expected=(0, None, None, None))
                await run.feedback(PC, cold, 1, phase=f'prepare-lower-{index}')
            for index in indices:
                cold = await run.predict(PC, index, 0, position=POSITION + 1, expected=(0, None, None, None))
                await run.feedback(PC, cold, 1, phase=f'allocate-upper-{index}')
                await run.predict(PC, index, 0, position=POSITION + 1, expected=(1, 1, 4, 1))


async def check_update_routes(agent, coverage, output, *, indices=range(512)):
    blocked = []
    for mode in ('serial', 'adjacent'):
        for index in indices:
            pc, history = PC + (index & ~63), index & 63
            expected_tag = prediction_tag(pc, history, 0)
            async with UsefulContext(agent, mode=mode, name='lower-update', index=index,
                    output=output, update_coverage=coverage, shadow=expected_tag >= 256) as run:
                cold = await run.predict(pc, history, 0, expected=(0, None, None, None))
                await run.feedback(pc, cold, 1, phase='allocate')
                if expected_tag >= 256:
                    # The training/SRAM tag is eight bits in this build. The
                    # truncated tag makes the required prediction miss; declare
                    # that exact logical address, then verify the real cell.
                    agent.allow_known_miss(pc, POSITION,
                        'BPU-UTAGE-007 lower-table tag truncation')
                lower = await run.predict(pc, history, 0)
                if lower.hit == 0 and run.shadow is not None and expected_tag >= (1 << run.shadow.tag_width):
                    # A miss does not qualify raw takenVec or tableId as a
                    # prediction. Verify the actual allocated physical cell.
                    run.check((0, 0), (lower.hit, lower.meta['abtbResult'][0]['hit']),
                        point='specific tag-width provider miss')
                    cell = run.shadow.latest['cells'][0]
                    run.check(dict(valid=1, index=index, data_valid=1, tag=expected_tag & ((1 << run.shadow.tag_width) - 1),
                        position=POSITION, counter=4), cell, point='genuine allocated truncated shadow tag')
                    blocked.append(dict(mode=mode, table=0, index=index, full_tag=expected_tag,
                        stored_width=run.shadow.tag_width, observed_cell=deepcopy(cell), prediction=asdict(lower)))
                    continue
                run.check((1, 0, 4, 1), (lower.hit, lower.meta['abtbResult'][0]['tableId'],
                    lower.meta['abtbResult'][0]['takenCtr_value'], lower.taken), point='allocated lower provider')
                await run.feedback(pc, lower, 1, count=3, phase='increase-and-saturate')
                agreeing = await run.predict(pc, history, 1, expected=(1, 0, 7, 1))
                await run.feedback(pc, agreeing, 1, phase='base-agrees-useful-holds')
                await run.feedback(pc, lower, 0, count=4, phase='decrease-and-saturate')
        for index in indices:
            async with UsefulContext(agent, mode=mode, name='upper-update', index=index,
                    output=output, update_coverage=coverage) as run:
                cold = await run.predict(PC, index, 0, expected=(0, None, None, None))
                await run.feedback(PC, cold, 1, phase='lower-allocate')
                lower = await run.predict(PC, index, 0, expected=(1, 0, 4, 1))
                await run.feedback(PC, lower, 0, phase='upper-allocate')
                upper = await run.predict(PC, index, 1, expected=(1, 1, 3, 0))
                await run.feedback(PC, upper, 0, count=2, phase='increase-and-saturate')
                agreeing = await run.predict(PC, index, 0, expected=(1, 1, 1, 0))
                await run.feedback(PC, agreeing, 0, phase='base-agrees-useful-holds')
                await run.feedback(PC, upper, 1, count=4, phase='decrease-and-saturate')
    return blocked
