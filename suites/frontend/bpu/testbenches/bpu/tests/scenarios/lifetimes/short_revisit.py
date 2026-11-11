"""The same declared read ancestor and new owned semantic path edges."""
import asyncio
from suites.frontend.bpu.testbenches.bpu.tests.scenarios.lifetimes.entry_protection import Program as ProtectionProgram
from suites.frontend.bpu.testbenches.bpu.env.driver.recovery import RecoveryDriver
from suites.frontend.bpu.testbenches.bpu.model.early_opposition import provider
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuRedirect
from suites.frontend.bpu.testbenches.utage.model.semantic import HISTORIES
from suites.frontend.bpu.testbenches.bpu.model.path_history import SHIFT


class Program(ProtectionProgram):
    path_position=None

    async def contradict(self,source):
        checks=self.checker.coverage
        self.actual_fallback=True
        checks.preparation_phase='bounded-NT-base'
        source=await self.prepare_wrong_base(source)
        checks.preparation_phase='Main-only-steering'
        source=await self.steer_main(source,3)
        checks.preparation_phase='Main-only-bridge'
        for _ in range((max(HISTORIES)+SHIFT-1)//SHIFT):
            # A normal streaming query can accept younger Main-taken work
            # before S3 delivery, replacing the very path being prepared.
            # Keep each declared semantic edge to one actual accepted source.
            source=await self._one_original(recover=source)
        await self.agent.configure_predictors(abtb=True,settle=True)
        await self.pause()
        checks.before_flowing_recovery(source)
        checks.preparation_phase='bounded-wrong-window'
        accepted=asyncio.get_running_loop().create_future()
        checks.open_wrong(accepted)
        try:
            await RecoveryDriver(self.agent,self.checker).send(source,
                position=checks.program.recovery_offset,branch_type=2,until=accepted)
        except BaseException as error:
            error.add_note('Declared read bridge: '+repr(checks.bridge)+'; window precondition: '
                +repr(checks.wrong_precondition)+'; first compared S1 candidates: '
                +repr(checks.first_wrong_candidates)+'; last compared S1 candidates: '
                +repr(list(checks.wrong_candidates))+'; actual-compared long allocation history: '
                +repr(list(checks.long_allocation_history)))
            raise
        result=await self.agent.next_transaction(start_pc=self.pc,after_tick=checks.selected_wrong_tick-1)
        token=self.checker.source_token(result)
        self.owners.append(result)
        await self.pause()
        await self.observation.wait('named_wrong_short_and_parallel_long_actually_compared',lambda _:
            checks.pending_loss is None and checks.pending_long is None
            and token.sequence in checks.long_allocations
            and any(row['owner']==token.sequence for row in checks.losses))
        checks.wrong_receipt(result)
        return result

    async def restart(self,source):
        if self.path_position is None: return await super().restart(source)
        await self.pause(); self.checker.source_token(source)
        request=BpuRedirect(self.pc,source.meta.redirect,cfi_pc=(self.pc//8)*8+self.path_position,
            taken=1,branch_type=1 if self.path_position==2 else 2)
        self.checker.plan_redirect(source,request)
        boundary=await self.agent.redirect(request)
        await self.agent.set_ready(prediction=True,meta=True)
        return boundary

    async def consume_long(self):
        checks=self.checker.coverage; allocation=checks.allocation_for_wrong()
        await self.pause()
        await RecoveryDriver(self.agent,self.checker).send(checks.bridge_source,
            position=checks.program.recovery_offset,branch_type=2)
        def match(token):
            value=provider(self.checker.model.sources,token)
            return value is not None and (value.table,value.index,value.tag)==(1,allocation['index'],allocation['tag'])
        source=await self.consume('actual_new_long_identity_consumes_wrong_short_allocation',match)
        checks.long_consumer(source); return source

    async def prepare_path(self,source):
        checks=self.checker.coverage
        await self.pause(); await self.agent.configure_predictors(abtb=False,settle=True)
        checks.begin_path()
        for position in checks.revisit.positions:
            self.path_position=position; before=source
            source=await self.query(before); checks.path_receipt(before,position,source)
        self.path_position=None; checks.path_ready()
        return source

    async def consume_short(self,source):
        checks=self.checker.coverage
        await self.agent.configure_predictors(abtb=True,settle=True)
        await self.pause()
        await RecoveryDriver(self.agent,self.checker).send(source,
            position=checks.program.recovery_offset,branch_type=2)
        def match(token):
            value=provider(self.checker.model.sources,token)
            return value is not None and value.key==checks.protected
        final=await self.consume('actual_short_error_update_survives_longer_learning',match)
        checks.short_consumer(final); return final
