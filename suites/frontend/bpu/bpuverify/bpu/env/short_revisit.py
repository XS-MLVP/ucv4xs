"""The same declared read ancestor and new owned semantic path edges."""
from bpuverify.bpu.env.entry_protection import Program as ProtectionProgram
from bpuverify.bpu.driver.recovery import RecoveryDriver
from bpuverify.bpu.model.early_opposition import provider
from bpuverify.bpu.transaction.types import BpuRedirect


class Program(ProtectionProgram):
    path_position=None

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
