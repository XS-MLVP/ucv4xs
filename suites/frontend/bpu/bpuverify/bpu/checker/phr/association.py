"""Associate one coherent cycle snapshot through the actual S1/S2/S3 pipeline.

No PC search or latency tolerance: a token advances only on stage fire and
is invalidated by the specified flush priority. All S3 perf echo fields must
match its original S1 token. Raw state is never fed into the PHR reference.
"""
from collections import deque
from copy import deepcopy

from toffee import ClockCycles
from bpuverify.bpu.transaction.types import BpuMeta
from bpuverify.bpu.transaction.types import BpuPerf
from bpuverify.bpu.transaction.types import BpuPrediction
from bpuverify.bpu.transaction.types import BpuStage1Source
from bpuverify.bpu.transaction.types import BpuTransaction


class BpuPhrAssociation:
    def __init__(self):
        self.stage2 = self.stage3 = None
        self.completed = deque()
        self.emitted = 0
        self.flushed = 0

    def observe(self, row, tick, check):
        pipe, boundary, parent = row['pipeline'], row['boundary'], row['parent']
        if row['reset']:
            self.stage2 = self.stage3 = None
            self.completed.clear()
            return
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
            # PrunedAddr signGuard is 50 bits on prediction; perfMeta uses
            # unGuard, exactly [48:0] (BpuDut.v output declarations/assignment).
            check(dict(start_pc=prediction.start_pc & ((1 << 49) - 1),
                    s1_target=prediction.target, s1_taken=prediction.taken, s1_position=prediction.position),
                {name: bits['perf'][name] for name in ('start_pc', 's1_target', 's1_taken', 's1_position')})
            check(token['phr'], bits['redirect']['phr'])
            meta = BpuMeta(resolve=deepcopy(bits['resolve']), redirect=deepcopy(bits['redirect']),
                perf=BpuPerf(**dict(bits['perf'], s1_source=BpuStage1Source(bits['perf']['s1_source']))))
            self.completed.append(BpuTransaction(token['tick'], tick, prediction, meta))
            self.emitted += 1
        incoming = None
        if boundary['fire1'] and not flush1:
            bits = row['public_prediction']['bits']
            check(1, row['public_prediction']['valid'])
            check(dict(start_pc=parent['s1_pc'], target=parent['s1_target'], taken=parent['s1_taken'],
                position=parent['s1_position'], s2_override=0, s3_override=0), bits)
            incoming = dict(tick=tick, prediction=BpuPrediction(**bits),
                phr=dict(phrPtr=deepcopy(row['phr_meta']['pointer']), phrLowBits=row['phr_meta']['low']))
        self.flushed += int(flush2 and self.stage2 is not None)
        self.stage3 = None if flush3 else (None if flush2 else self.stage2) if boundary['fire2'] else None
        self.stage2 = None if flush2 else incoming if boundary['fire1'] else None if boundary['fire2'] else self.stage2

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
