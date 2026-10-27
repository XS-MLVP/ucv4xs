"""Domain stage control extends the normal agent, never the SDK or test case."""
from bpuverify.mbtb.agent.main import MbtbAgent
from bpuverify.common.env.wait import wait_condition


class CleanupResetAgent(MbtbAgent):
    async def expose_registered_invalidation(self,monitor):
        self._require_started()
        if not self._multi_hit_cleanup_scope_active or not self._defer_multi_hit_cleanup:
            raise RuntimeError('an owned deferred duplicate scope is required')
        self._defer_multi_hit_cleanup=False
        self.lookup_driver.quiesce()
        try:
            result=await wait_condition(self.dut.clock,sample=monitor.status,
                satisfied=lambda value:value is not None and bool(value['clears']),
                name='mbtb.original-duplicate-registered-invalidation',timeout_cycles=16)
            return result.state
        finally:
            # Stop replaying the cached observation before reset. Neither the
            # invalidation nor its SRAM write is drained by this operation.
            self._defer_multi_hit_cleanup=True
            self.lookup_driver.quiesce()
