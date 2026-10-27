"""bpuverify.bpu.env.ras.retirement components."""

from copy import deepcopy
from bpuverify.common.env.wait import wait_condition
from bpuverify.bpu.bundle.values import _plain
from bpuverify.bpu.checker.phr.checking import BpuPhrChecker
from bpuverify.common.driver.signal import PulseDriver
from bpuverify.bpu.checker.ras.retirement import CommitChecker
from bpuverify.bpu.monitor.ras.retirement import CommitMonitor
from bpuverify.bpu.case.ras.retirement import CommitPorts


class BpuRetirement:
    """Drive real FTQ retirement with independently associated S3 metadata."""
    def __init__(self, agent, *, semantic=None):
        self.agent = agent
        self.ports = CommitPorts.bind(agent)
        self.driver = PulseDriver(self.ports.commit)
        self.checker = CommitChecker()
        self.phr = BpuPhrChecker(scope='integrated-retirement')
        self.coherent = agent.observe_phr(self.phr)
        self.monitor = CommitMonitor(self.ports.observation, decoder=_plain)
        self.semantic = semantic

    async def __aenter__(self):
        await self.driver.__aenter__()
        self.monitor.start(self.agent._execution, observer=self.checker.capture)
        try:
            await self.coherent.__aenter__()
        except BaseException:
            await self.monitor.aclose()
            self.driver.close()
            raise
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        try:
            await self.coherent.__aexit__(exc_type, exc, traceback)
        finally:
            await self.monitor.aclose()
            self.driver.close()
        if exc_type is None:
            self.checker.summary()

    async def retire_many(self, operations):
        requests = []
        for transaction,action in operations:
            expected = None if self.semantic is None else self.semantic.source_expected(transaction)
            request = self.checker.request_for(transaction,action,self.phr)
            if expected is not None:
                self.checker.check(expected,request['meta'],tick=transaction.meta_tick,phase='independently-owned-commit-source')
            requests.append(request)
        requests = tuple(requests)
        if not requests:
            raise ValueError('retirement burst must not be empty')
        target = len(self.checker.accepted)+len(requests)
        self.checker.planned.extend(deepcopy(requests))
        await self.driver.send_many(tuple(dict(action=row['action'], branch_type=row['branch_type'],
            meta=row['meta']) for row in requests))
        def sample():
            self.checker.raise_failure()
            self.phr.raise_failure()
            return dict(planned=len(self.checker.planned),pending=self.checker.pending_expected is not None,
                        accepted=len(self.checker.accepted),applied=len(self.checker.applied),
                        checked=self.checker.checked_applied)
        await wait_condition(self.agent.dut.clock,sample=sample,
            satisfied=lambda state:not state['planned'] and not state['pending'] and state['checked']>=target,
            name='bpu.ras.retirement-effects-compared',timeout_cycles=128)
        self.checker.raise_failure()
        self.phr.raise_failure()
        return requests

    def report(self):
        return dict(scope='genuine neutral notifications and ordered calls/returns; no stale-SSP call/return recovery',
            summary=self.checker.summary(), phr_summary=self.phr.summary(),
            cycles=self.checker.records, accepted=self.checker.accepted,
            applied=self.checker.applied, phr_cycles=self.phr.records,
            native_state_never_seeds_reference=True, fabricated_commitMeta=False,
            test_level_edge_or_get_set=False, formal_credit=False)
