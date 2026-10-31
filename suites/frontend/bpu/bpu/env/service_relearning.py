"""Public asynchronous input and monitor-terminated old-service collision."""
import asyncio
from contextlib import suppress
from toffee import DriveStable, on
from suites.frontend.bpu.bpu.bundle.values import _plain
from suites.frontend.bpu.bpu.env.direction_service import DirectionService
from suites.frontend.bpu.bpu.transaction.types import BpuBatchTraining


class Service(DirectionService):
    async def overlap_learning(self, source, branches):
        self.checks.begin_late()
        request = BpuBatchTraining(source.prediction.start_pc, source.meta.resolve, tuple(branches))
        self.env.checker.plan_feedback(source, request)
        before = self.env.checker.last_tick
        handle = self.agent.training_driver.send(request)
        receipt = asyncio.get_running_loop().create_future()
        prepared = asyncio.get_running_loop().create_future()
        sampler = self.monitor.binding.bits.compile_sampler()
        def capture(event):
            try: self.checks.prepare_collision(event, _plain(sampler()))
            except Exception as error:
                if self.monitor.failure is None: self.monitor.failure = error
        async def delivered(_): pass
        subscription = self.agent._execution.subscribe(on(DriveStable(self.monitor.binding.clock),
            capture=capture, delivery='lossless', capacity=8)(delivered).bind())
        def healthy():
            self.monitor.raise_failure()
            return True
        def failure(): return self.monitor.failure or self.checks.failure or self.env.checker.failure
        try:
            await self.env.observation.wait('late_original_accepted', lambda _: healthy() and handle.done())
            accepted = await handle
            events = tuple((tick, resolution) for tick, resolution in self.env.checker.resolutions_for_source(source) if tick > before)
            self.checks.check((accepted.tick,), tuple(t for t, _ in events), 'late async send has one exact compared original acceptance')
            self.checks.late_accepted(events[0])
            # Independent learning-stage ownership, not a fixed cycle delay or
            # actual valid signal used to predict its own expected timing.
            await self.env.observation.wait('late_independent_learning_ready_for_service',
                lambda checker: healthy() and checker.model.sources.tage.info is not None)
            self.checks.begin_collision(receipt, prepared)
            actual = await self.agent.allow_services_until(receipt, prepared=prepared,
                name='bpu.service-relearning.old-completion-meets-new-learning', failure=failure)
            self.monitor.raise_failure()
            self.checks.collision_complete(actual)
        except Exception as error:
            error.add_note(f'service-relearning snapshot: {self.checks.snapshot()!r}')
            raise
        finally:
            self.agent._execution.reactor.cancel_subscription(subscription)
            if subscription.task is not None:
                with suppress(asyncio.CancelledError): await subscription.task
            for future in (receipt, prepared):
                if not future.done(): future.cancel()
            if not handle.done() and handle.accepted_event is None: handle.cancel()

    async def release_remaining(self):
        self.checks.release()
        await self.env.pause()
        def complete(_):
            self.monitor.raise_failure()
            return tuple(map(len, self.checks.written.values())) == tuple(1+n for n in self.checks.profile.remaining)
        await self.env.observation.wait('all_remaining_real_versions_serviced', complete)
        self.checks.services_complete()
