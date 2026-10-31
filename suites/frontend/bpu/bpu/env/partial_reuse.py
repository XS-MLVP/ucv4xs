"""Two feedback bursts separated by monitor-terminated partial service."""
import asyncio
from contextlib import suppress
from toffee import DriveStable, on
from suites.frontend.bpu.bpu.bundle.values import _plain
from suites.frontend.bpu.bpu.env.neighbor_migration import NeighborMigrationService


class PartialReuseService(NeighborMigrationService):
    async def release_one_pair(self):
        receipt = asyncio.get_running_loop().create_future()
        prepared = asyncio.get_running_loop().create_future()
        self.checks.begin_partial(receipt, prepared)
        sampler = self.monitor.binding.bits.compile_sampler()
        def capture(event):
            try: self.checks.prepare_partial(event, _plain(sampler()))
            except Exception as error:
                if self.monitor.failure is None: self.monitor.failure = error
        async def delivered(_): pass
        subscription = self.agent._execution.subscribe(on(DriveStable(self.monitor.binding.clock),
            capture=capture, delivery='lossless', capacity=8)(delivered).bind())
        def failure():
            return self.monitor.failure or self.checks.failure or self.env.checker.failure
        try:
            event = await self.agent.allow_services_until(receipt, prepared=prepared,
                name='bpu.partial-reuse.first-neighbor-pair', failure=failure)
            self.monitor.raise_failure()
            self.checks.partial_complete(event)
        except Exception as error:
            error.add_note(f'partial-service boundary: last_actual={self.checks.last!r}; '
                           f'pipeline_tick={self.env.checker.last_tick}; '
                           f'public_events={self.env.checker.last_events!r}')
            raise
        finally:
            self.agent._execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError): await subscription.task
            for future in (receipt, prepared):
                if not future.done(): future.cancel()
