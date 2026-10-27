"""Two real blocks; driver admission can overlap prediction advancement."""
from bpuverify.bpu.env.early_direction import EarlyDirectionProgram
from bpuverify.bpu.model.early_opposition import provider
from bpuverify.bpu.model.early_aging import require_recovery_window
from bpuverify.bpu.model.path_history import WIDTH,LAYOUT,SHIFT
from bpuverify.bpu.transaction.types import BpuRedirect,BpuBatchTraining,BpuBranchFeedback


class Program(EarlyDirectionProgram):
    @property
    def checks(self): return self.checker.coverage

    async def pause(self):
        await super().pause()
        await self.observation.wait('cross_block_next_actual_state_compared',lambda _:self.checks.pending is None)

    async def initialize(self):
        # Controls are already observed as applied by the enclosing scope.
        # A standard cold reset gives A a real owned Main read immediately.
        await self.pause(); await self.agent.reset(self.checks.program.a)
        await self.agent.set_ready(prediction=True,meta=True)
        self.anchor=await self.agent.next_transaction(start_pc=self.checks.program.a)
        self.checker.source_token(self.anchor); await self.pause()
        return self.anchor

    async def from_predecessor(self,source):
        token=self.checker.source_token(source); p=self.checks.program
        if token.pc!=p.a: raise AssertionError('the real A-to-B edge owns this restart')
        await self.pause()
        require_recovery_window(self.checker.model.history.taken_edges,token.history.taken_edges,
            capacity=WIDTH,history_bits=max(length for length,_ in LAYOUT),shift=SHIFT)
        request=BpuRedirect(p.b,source.meta.redirect,cfi_pc=(p.a//8)*8+4,taken=1,branch_type=2)
        self.checker.plan_redirect(source,request)
        boundary=await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True,meta=True)
        return boundary

    async def query_successor(self,source):
        boundary=await self.from_predecessor(source)
        receipt=await self.agent.next_transaction(start_pc=self.checks.program.b,after_tick=boundary)
        self.checker.source_token(receipt); await self.pause(); return receipt

    async def resolve_owned(self,phase,source):
        checks=self.checks; checks.plan_resolution(phase,source)
        pc,position,target,kind,taken=checks.program.resolution(phase)
        active=phase in ('not-taken','fallback') and checks.program.flowing
        await self.agent.set_ready(prediction=active,meta=True)
        transaction=BpuBatchTraining(pc,source.meta.resolve,(BpuBranchFeedback(position,target,kind,
            taken=int(taken),mispredict=1),))
        self.checker.plan_feedback(source,transaction)
        if active:
            # Accept and mature the old feedback while predictions advance.
            # SRAM retirement may be blocked by those reads; pause below
            # establishes its service window without serializing admission.
            await self.agent.train_batches((transaction,))
        else:
            await self.agent.train_batch(transaction)
        await self.pause()

    async def consume_early_edge(self,source,pc):
        await self.from_predecessor(source)
        previous=self.pc; self.pc=pc
        try: receipt=await self.consume('actual_cross_block_early_edge',lambda token:token.early.source=='ahead')
        finally: self.pc=previous
        self.checks.early_consumer(receipt); return receipt

    async def consume_learned(self,source):
        await self.from_predecessor(source)
        previous=self.pc; self.pc=self.checks.program.b
        def qualified(token):
            value=provider(self.checker.model.sources,token)
            return value is not None and value.table==0 and value.position==2 and value.counter<4
        try: receipt=await self.consume('actual_new_cross_block_short_direction',qualified)
        finally: self.pc=previous
        self.checks.negative_consumer(receipt); return receipt

    async def fresh_predecessor(self):
        # Refresh through a real new A original, not a copied/reset checkpoint.
        await self.agent.set_ready(prediction=True,meta=True)
        previous=self.pc; self.pc=self.checks.program.a
        try: receipt=await self.consume('fresh_actual_predecessor_in_current_loop',lambda token:token.early.source=='ahead')
        finally: self.pc=previous
        self.checks.save(receipt); return receipt
