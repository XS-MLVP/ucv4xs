"""Associate checked PHR inputs through real S1/S2/S3 fire/flush events.

The integrated public projection has neither target nor perf echo. Never
synthesize them from model state or internal diagnostics. A UID is created at
the PHR input acceptance and travels with the two stage leases, independently
of equal PCs/metadata. This checks PHR lineage, not BPU prediction correctness.
"""
from collections import deque
from copy import deepcopy

from toffee import ClockCycles
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuMeta
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuPrediction
from suites.frontend.bpu.testbenches.bpu.transactions.types import BpuTransaction


class BpuPhrAssociation:
    def __init__(self):
        self.stage2 = self.stage3 = None
        self.completed = deque()
        self.emitted = 0
        self.flushed = 0
        self.accepted = 0
        self.offered = 0
        self.suppressed = 0
        self.next_uid = 0
        self.epoch = 0
        self.in_reset = False
        self.pending = set()
        self.cancellations = []
        self._completions = []

    @property
    def completions(self):
        """Immutable (uid, epoch, tick) terminal receipts, retained over reset."""
        return tuple(self._completions)

    def _cancel(self, token, tick, reason):
        if token is not None:
            self.pending.remove(token['uid'])
            self.flushed += 1
            self.cancellations.append(dict(uid=token['uid'], epoch=token['epoch'], tick=tick, reason=reason))

    def observe(self, row, tick, check):
        pipe, boundary, parent = row['pipeline'], row['boundary'], row['parent']
        if row['reset']:
            if not self.in_reset:
                self.epoch += 1
            self.in_reset = True
            self._cancel(self.stage2, tick, 'reset')
            self._cancel(self.stage3, tick, 'reset')
            self.stage2 = self.stage3 = None
            self.completed.clear()
            return
        self.in_reset = False
        check(int(self.stage2 is not None), pipe['s2_valid'])
        check(int(self.stage3 is not None), pipe['s3_valid'])
        redirect, override3, override2 = (boundary[name]['valid'] for name in ('redirect', 's3', 's2'))
        flush3, flush2, flush1 = bool(redirect), bool(redirect or override3), bool(redirect or override3 or override2)
        # s3_flush is an optimized alias of the observed public redirect.valid;
        # s3_fire is likewise s3_valid, not an independently stored signal.
        check(dict(s2_flush=int(flush2), s1_flush=int(flush1)),
            {name: pipe[name] for name in ('s2_flush', 's1_flush')})
        check(pipe['s3_valid'], row['public_meta']['valid'])
        check(pipe['s2_valid'], boundary['fire2'])
        check(int(bool(pipe['s1_valid']) and bool(row['public_prediction']['ready'])), boundary['fire1'])
        if self.stage3 is not None:
            token = self.stage3
            bits = row['public_meta']['bits']
            prediction = token['prediction']
            check({'resolve', 'redirect'}, set(bits))
            check(prediction.start_pc, parent['s3_pc'])
            check(token['phr'], bits['redirect']['phr'])
            meta = BpuMeta(resolve=deepcopy(bits['resolve']), redirect=deepcopy(bits['redirect']),
                perf=None)
            self.completed.append(BpuTransaction(token['tick'], tick, prediction, meta,
                                                 token['uid'], token['epoch']))
            self.pending.remove(token['uid'])
            self._completions.append((token['uid'], token['epoch'], tick))
            self.emitted += 1
        incoming = None
        if boundary['fire1']:
            self.offered += 1
        if boundary['fire1'] and not flush1:
            bits = row['public_prediction']['bits']
            check(1, row['public_prediction']['valid'])
            check(dict(start_pc=parent['s1_pc'], taken=parent['s1_taken'],
                position=parent['s1_position'], s2_override=0, s3_override=0), bits)
            uid = self.next_uid
            self.next_uid += 1
            self.accepted += 1
            self.pending.add(uid)
            incoming = dict(tick=tick, uid=uid, epoch=self.epoch,
                prediction=BpuPrediction(target=None, **bits),
                phr=dict(phrPtr=deepcopy(row['phr_meta']['pointer']), phrLowBits=row['phr_meta']['low']))
        elif boundary['fire1']:
            self.suppressed += 1
        if flush2:
            self._cancel(self.stage2, tick, 'backend redirect' if redirect else 'S3 override')
        self.stage3 = None if flush3 else (None if flush2 else self.stage2) if boundary['fire2'] else None
        self.stage2 = None if flush2 else incoming if boundary['fire1'] else None if boundary['fire2'] else self.stage2

    def finish(self, check):
        check(None, self.stage2)
        check(None, self.stage3)
        check(set(), self.pending)
        check(self.accepted, self.emitted + self.flushed)
        check(self.offered, self.accepted + self.suppressed)
        completed = {uid for uid, _, _ in self._completions}
        cancelled = {row['uid'] for row in self.cancellations}
        check(self.emitted, len(completed))
        check(self.flushed, len(cancelled))
        check(set(), completed & cancelled)
        check(set(range(self.next_uid)), completed | cancelled)

    async def next_transaction(
        self, agent, checker, *, start_pc=None, require_taken=False,
        after_tick=None, limit=512,
    ):
        if type(limit) is not int or limit <= 0:
            raise ValueError("transaction cycle limit must be a positive integer")
        observed = []
        for _ in range(limit):
            checker.raise_failure()
            while self.completed:
                item = self.completed.popleft()
                observed.append(item.prediction.start_pc)
                if (
                    (start_pc is None or item.prediction.start_pc == start_pc)
                    and (not require_taken or item.prediction.taken)
                    and (after_tick is None or item.prediction_tick > after_tick)
                ):
                    return item
            await ClockCycles(agent.dut.clock, 1)
        checker.raise_failure()
        raise AssertionError(
            f"PHR transaction not observed: start_pc={start_pc!r}, "
            f"require_taken={require_taken}, after_tick={after_tick!r}, "
            f"limit={limit}, observed={observed[:12]!r}"
        )
