"""Read-only TAGE reference scope and semantic learning-event admission."""
import asyncio
from contextlib import suppress

from toffee import AnyOf, SimTimeout, TaskComplete, XEventKind

from bpuverify.bpu.checker.assertions import mbtb_counter_for_position
from bpuverify.bpu.checker.tage.semantic import TageSemanticComponentChecker
from bpuverify.bpu.monitor.tage.semantic import TageSemanticComponentMonitor
from bpuverify.common.env.wait import wait_condition
from bpuverify.tage.model.semantic import Branch, Feedback, Hint


class TageSemanticEnvironment:
    def __init__(self, agent, reference=None):
        self.agent = agent
        self.reference = TageSemanticComponentChecker() if reference is None else reference
        self.monitor = TageSemanticComponentMonitor(agent)

    async def __aenter__(self):
        self.monitor.start(self.reference)
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.monitor.aclose()
        if exc_type is None:
            self.reference.raise_failure()

    async def allocate(self, source, transaction, *, owner, timeout_cycles=1823):
        """Admit one eligible allocation at a model-predicted opportunity.

        The existing SDK driver is still the sole writer. No observed random
        or allocation signals, explicit edge waits, internal writes, bank
        enumeration, or fixed settling delays are involved.
        """
        self.reference.raise_failure()
        branches = [branch for branch in transaction.branches if branch is not None]
        if len(branches) != 1 or transaction.pc != source.prediction.start_pc:
            raise ValueError('allocation requires one associated branch')
        branch, = branches
        meta = self.reference.source_expected(source,branch.position)
        if not branch.mispredict or branch.branch_type != 1:
            raise ValueError('allocation requires a genuinely mispredicted conditional')
        frame, = [frame for tick,frame,_,_,_ in self.reference.expected if tick == source.meta_tick-4]
        feedback = Feedback(transaction.pc,frame.read.context,(Branch(branch.position,bool(branch.taken),1,True,True,
            mbtb_counter_for_position(source,branch.position),
            Hint(bool(meta['hasProvider']),bool(meta['hasAlt']),bool(meta['useProvider']),
                meta.get('providerTableIdx',0),meta.get('providerWayIdx',0),
                meta.get('providerTakenCtr_value',0),meta.get('providerUsefulCtr_value',0),
                bool(meta['altOrBasePred']),bool(meta['altConf']))),))
        agent = self.agent
        old_prediction_ready,old_meta_ready = agent._prediction_ready,agent._meta_ready
        await agent.set_ready(prediction=False,meta=True)
        try:
            await agent.training_activity.wait_idle('reads','pipeline','writes')
            def sample():
                self.reference.raise_failure()
                candidate = self.reference.model.allocation_at_next_accept(feedback)
                if candidate is None:
                    raise ValueError('owned feedback has no eligible higher-history allocation')
                return candidate
            await wait_condition(agent.dut.clock,sample=sample,satisfied=lambda candidate:candidate==owner,
                name='bpu.tage.owned-allocation-opportunity',timeout_cycles=timeout_cycles)
            # No await between the forecast and submission: the normal driver
            # accepts in the following reference input boundary, once ready.
            before = self.reference.input_tick
            await agent.train_batch(transaction)
            self.reference.raise_failure()
            accepted = [(tick,request) for tick,request in self.reference.accepted_feedback if tick > before]
            if len(accepted) != 1 or accepted[0][0] != before+2 or accepted[0][1] != feedback:
                raise AssertionError(f'allocation admission changed semantic feedback: {accepted!r}, expected={feedback!r}')
        finally:
            await agent.set_ready(prediction=bool(old_prediction_ready),meta=bool(old_meta_ready))

    async def corrections(self,source,*,timeout_cycles=128):
        """Observe a complete causal window, with a failure budget, not delay."""
        if type(timeout_cycles) is not int or timeout_cycles <= 0:
            raise ValueError('correction observation timeout must be positive')
        operation = asyncio.create_task(self.agent.corrections_for(source))
        try:
            result = await AnyOf(TaskComplete(operation),SimTimeout(timeout_cycles,clock=self.agent.dut.clock))
            self.reference.raise_failure()
            if result.kind is XEventKind.TIMEOUT:
                raise TimeoutError(f'BPU correction window did not close: source_pc={source.prediction.start_pc:#x}, '
                                   f'metadata_tick={source.meta_tick}, budget={timeout_cycles}')
            return result.value
        finally:
            if not operation.done():
                operation.cancel()
                with suppress(asyncio.CancelledError):
                    await operation
