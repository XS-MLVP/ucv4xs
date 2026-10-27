"""bpuverify.bpu.env.phr.observation components."""

from copy import deepcopy
from toffee import ClockCycles
from bpuverify.bpu.monitor.phr.observation import BpuPhrMonitor


class BpuPhrObservation:
    """Exclusive coherent observation, not a second agent or pin interface.

    Existing training helpers still use the original BpuAgent. Only its
    observation source changes for this scope. No private monitor queue or
    cross-phase timestamp approximation is involved.
    """

    def __init__(self, agent, checker):
        self.agent = agent
        self.checker = checker
        self.monitor = None
        self.accepted = []
        self._active = False

    async def __aenter__(self):
        agent = self.agent
        agent._require_started()
        if agent._phr_observation is not None:
            raise RuntimeError("PHR observation already owns this agent")
        if self._active or self.monitor is not None:
            raise RuntimeError("PHR observation scopes are single-use")
        # Resolve every memory-direct leaf before changing ownership. A binding failure
        # must not strand the ordinary prediction/meta monitors in closed state.
        self.monitor = BpuPhrMonitor(agent)
        agent._phr_observation = self
        self._active = True
        try:
            await agent.prediction_monitor.aclose()
            await agent.meta_monitor.aclose()
            self.monitor.start(agent._execution, observer=self.checker.capture)
        except BaseException:
            await self.aclose()
            raise
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        await self.aclose()
        # A failed body already carries the foreground error. Do not raise the
        # same latched mismatch again during teardown.
        if exc_type is None:
            self.checker.raise_failure()

    async def aclose(self, *, resume_streams=True):
        if not self._active:
            return
        agent = self.agent
        try:
            await self.monitor.aclose()
        finally:
            self._active = False
            agent._phr_observation = None
            if resume_streams and agent._started and agent._execution is not None:
                agent._make_stream_monitors()
                agent.prediction_monitor.start(agent._execution)
                agent.meta_monitor.start(agent._execution)
                agent._transaction_aligned = False

    def _require_active(self):
        if not self._active or self.agent._phr_observation is not self:
            raise RuntimeError("PHR observation scope is not active")
        self.checker.raise_failure()

    async def next_transaction(self, **selection):
        self._require_active()
        return await self.checker.association.next_transaction(
            self.agent, self.checker, **selection
        )

    async def redirect(self, payload):
        self._require_active()
        first_tick = self.checker.last_tick
        self.checker.plan(payload)
        result = await self.agent.redirect_driver.send(payload)
        self.checker.raise_failure()
        accepted = [row for row in self.checker.records
                    if (first_tick is None or row['tick'] > first_tick) and row['public_redirect']['valid']]
        self.checker.check(1, len(accepted), phase='coherent-redirect-acceptance')
        self.checker.check(payload, accepted[0]['public_redirect']['bits'],
                           phase='coherent-redirect-payload')
        # DriveStable completion follows the actual coherent boundary by one
        # cycle. The public result in this scope is the observed acceptance,
        # never a fuzzy later same-PC match.
        self.checker.check(accepted[0]['tick'] + 2, result.tick,
                           phase='driver-completion-phase-contract')
        self.accepted.append(dict(tick=result.tick, payload=deepcopy(payload),
                                  observed_tick=accepted[0]['tick']))
        return accepted[0]['tick']

    async def redirect_many(self, payloads):
        """Associate a pulse burst with every actual, adjacent input beat."""
        self._require_active()
        payloads = tuple(payloads)
        if not payloads:
            raise ValueError('a coherent recovery burst must not be empty')
        first_tick = self.checker.last_tick
        for payload in payloads:
            self.checker.plan(payload)
        result = await self.agent.redirect_driver.send_many(payloads)
        self.checker.raise_failure()
        rows = [row for row in self.checker.records
                if (first_tick is None or row['tick'] > first_tick) and row['public_redirect']['valid']]
        self.checker.check(len(payloads), len(rows), phase='coherent-redirect-burst-acceptance')
        for index, (payload, row) in enumerate(zip(payloads, rows, strict=True)):
            self.checker.check(payload, row['public_redirect']['bits'],
                               phase='coherent-redirect-burst-payload', index=index)
            if index:
                self.checker.check(rows[index-1]['tick'] + 2, row['tick'],
                                   phase='coherent-redirect-burst-adjacency')
            self.accepted.append(dict(payload=deepcopy(payload), observed_tick=row['tick'], burst_index=index))
        self.checker.check(rows[-1]['tick'] + 2, result.tick, phase='driver-burst-completion-contract')
        return tuple(row['tick'] for row in rows)

    async def settle(self, cycles):
        """Observe an explicit stimulus window; not a completion guarantee."""
        self._require_active()
        if type(cycles) is not int or cycles <= 0:
            raise ValueError("settle cycles must be a positive integer")
        await ClockCycles(self.agent.dut.clock, cycles)
        self.checker.raise_failure()

    async def drain(self):
        """Check actual retirement after the caller has stopped younger reads."""
        self._require_active()
        result = await self.agent.drain_prediction_work()
        self.checker.raise_failure()
        return result

    async def pause_after_s1(self, *, start_pc, after_tick, cycles=4, limit=32):
        """Stall younger S1 traffic after this exact accepted pipeline token.

        Older S2/S3 tokens keep advancing. Selection uses observed fire, not
        fixed sleeps or a later request with a coincidentally equal PC.
        """

        self._require_active()
        if type(limit) is not int or limit <= 0:
            raise ValueError("acceptance cycle limit must be a positive integer")
        for _ in range(limit):
            row = self.checker.records[-1]
            if (row['tick'] > after_tick and row['boundary']['fire1']
                    and row['parent']['s1_pc'] == start_pc):
                break
            await self.settle(1)
        else:
            raise AssertionError(
                f"post-redirect S1 token did not accept: start_pc={start_pc:#x}, "
                f"after_tick={after_tick}, limit={limit}"
            )
        await self.agent.set_ready(prediction=False, meta=True)
        try:
            await self.settle(cycles)
        finally:
            await self.agent.set_ready(prediction=True, meta=True)
