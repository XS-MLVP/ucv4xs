"""Compare iteration versions before committing independently predicted events."""
from collections import deque
from copy import deepcopy

from toffee import CheckContext, ScoreboardMode

from bpuverify.bpu.model.loop_iteration import LoopIterationReference, MAX_ITERATIONS, loop_successor
from bpuverify.bpu.model.selection import Branch, Kind
from bpuverify.bpu.coverage.loop_iteration import RULES, FINAL_RULES


class LoopIterationChecks:
    def __init__(self, pipeline, *, observe_state=True, coverage=None):
        if not observe_state:
            raise ValueError('iteration reference needs a read-only registered-state comparison')
        self.pipeline, self.coverage = pipeline, coverage
        self.observe_state = observe_state
        self.model = LoopIterationReference()
        self.failure = None
        self.initialized = False
        self.last_tick = self.last_step = self.last_row = None
        self.plans = deque()
        self.original = self.last_recovery = self.consumer = None
        self.proof = {}
        self.proposal = None
        self.completed = False

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure
        self.pipeline.raise_failure()

    def check(self, expected, actual, point):
        self.raise_failure()
        try:
            self.pipeline.board.check(expected=expected, actual=actual,
                context=CheckContext(self.pipeline.board.name, ScoreboardMode.DIRECT,
                    sequence_id=self.last_tick, request=dict(point=point, cursor=self.model.cursor,
                        step=self.last_step, proposal=self.proposal,
                        original=None if self.original is None else dict(source=self.original[1], program=self.original[3]),
                        pending=tuple(self.plans))))
        except Exception as error:
            self.failure = error
            raise

    def metadata(self, receipt, source):
        token = self.pipeline.source_token(receipt)
        self.check(True, self.model.snapshot(token) is source,
                   'iteration metadata belongs to this exact immutable prediction version')
        self.check((source.count, source.count),
            (receipt.meta.redirect['commonHRMeta']['imli'], receipt.meta.resolve['commonHR']['imli']),
            'both public iteration snapshots were predicted independently of metadata')

    def source(self, receipt):
        source = self.model.snapshot(self.pipeline.source_token(receipt))
        self.metadata(receipt, source)
        return source

    def register_anchor(self, receipt):
        source = self.source(receipt)
        self.check(0, source.count, 'reset source starts outside a loop')
        return source

    def plan(self, receipt, request):
        source = self.source(receipt)
        position = request.cfi_pc - (source.pc // 8) * 8
        correction = Branch(position, request.pc, Kind(request.branch_type), bool(request.taken))
        self.plans.append((source, correction, request))

    def record(self, rule, **witness):
        if self.coverage is not None:
            witness.setdefault('tick', self.last_tick)
            self.coverage.record('reached', rule, **witness)

    def original_source(self, receipt, program):
        source = self.source(receipt)
        self.check(True, source.count == MAX_ITERATIONS if program.saturated_original
                   else 0 < source.count < MAX_ITERATIONS, 'original is a nonzero independent loop source')
        self.original = receipt, source, deepcopy(receipt.meta), program
        self.proof['original'] = dict(prediction_tick=receipt.prediction_tick, meta_tick=receipt.meta_tick,
            token=source.token_sequence, count=source.count, pc=source.pc)
        self.record(RULES[0], **self.proof['original'])

    def saturated_and_held(self):
        self.check(MAX_ITERATIONS, self.model.cursor, 'normal younger loop predictions reach the semantic bound')
        self.check(MAX_ITERATIONS, self.last_row['state'], 'actual registered younger cursor is saturated')
        self.check('hold', self.last_step.reason, 'quiescent prediction does not extend or clear the loop')
        self.metadata(self.original[0], self.original[1])
        self.proof['younger'] = dict(tick=self.last_tick, count=self.model.cursor,
            original_count=self.original[1].count, reasons=dict(self.model.reasons))
        self.record(RULES[1], **self.proof['younger'])
        self.record(RULES[2], reason=self.last_step.reason, count=self.model.cursor)

    def recovered(self, tick):
        self.check(True, self.last_recovery is not None, 'actual accepted backend recovery is required')
        recovery = self.last_recovery
        self.check((tick, self.original[1]), (recovery['tick'], recovery['source']),
                   'recovery uses the original token rather than the current saturated cursor')
        self.check(True, recovery.get('registered', False), 'next registered state must independently agree')
        self.check(loop_successor(self.original[1].count, self.original[1].pc, self.original[3].correction),
                   recovery['after'], 'only a taken backward conditional extends its own original loop')
        self.proof['recovery'] = {k: v for k, v in recovery.items() if k != 'source'}
        self.record(RULES[3], **self.proof['recovery'])
        self.record(RULES[4], **self.proof['recovery'])

    def consumed(self, receipt):
        source = self.source(receipt)
        self.check(True, self.last_recovery is not None and receipt.prediction_tick > self.last_recovery['tick'],
                   'fresh consumer must be younger than the actual accepted recovery')
        self.consumer = receipt
        self.proof['consumer'] = dict(prediction_tick=receipt.prediction_tick, meta_tick=receipt.meta_tick,
            token=source.token_sequence, count=source.count, pc=source.pc,
            actual_redirect=receipt.meta.redirect['commonHRMeta']['imli'],
            actual_resolve=receipt.meta.resolve['commonHR']['imli'])
        self.record(RULES[5], **self.proof['consumer'])

    def finish(self):
        self.check(False, self.completed, 'iteration result is single-use')
        self.check(True, self.original is not None and self.consumer is not None
                   and self.last_recovery is not None and self.last_recovery.get('registered', False),
                   'source, real recovery, registered endpoint and fresh consumer all required')
        self.check(False, bool(self.plans), 'no unaccepted iteration recovery remains')
        receipt, source, saved, _ = self.original
        self.metadata(receipt, source)
        self.check(saved, receipt.meta, 'younger speculation and recovery cannot mutate old public snapshots')
        self.record(RULES[6], token=source.token_sequence, count=source.count)
        self.check(True, self.model.reasons['middle-repair'] > 0,
                   'normally learned loop has an actual independently compared pipeline repair')
        self.record(RULES[7], repairs=self.model.reasons['middle-repair'])
        if self.coverage is not None:
            for rule in RULES:
                self.coverage.record('checked', rule, tick=self.last_tick)
            self.coverage.finish()
        self.completed = True

    def finish_final_repair(self, original, consumer):
        self.check(False, self.completed, 'iteration result is single-use')
        receipt, saved, source = original
        self.metadata(receipt, source)
        self.check(saved, receipt.meta, 'original weak-provider public source remains immutable')
        token = self.pipeline.source_token(receipt)
        wanted = self.pipeline.model.sources.defined_metadata(token)
        slot, = [i for i in range(4) if wanted.get(f'{i}.hasProvider')]
        self.check((3, 3, 0, 1), tuple(wanted[f'{slot}.{key}'] for key in
            ('providerTableIdx', 'providerTakenCtr_value', 'useProvider', 'altOrBasePred')),
            'normally learned weak-negative provider is rejected for the opposite taken base')
        repair = self.proof.get('first_final-repair')
        self.check(True, repair is not None and repair.get('registered_tick') is not None,
                   'real final repair needs its same-cycle lookup and next registered state')
        self.check(source.token_sequence, repair['token'], 'actual final repair belongs to this original source')
        fresh = self.source(consumer)
        self.check((repair['issued_token'], repair['after']), (fresh.token_sequence, fresh.count),
                   'exact new lookup issued by the final repair reaches a public consumer')
        self.check(True, consumer.prediction_tick > repair['tick'], 'final repair consumer is genuinely younger')
        self.check(False, bool(self.plans), 'no planned recovery remains')
        self.proof['original'] = dict(token=source.token_sequence, count=source.count, meta_tick=receipt.meta_tick)
        self.proof['consumer'] = dict(token=fresh.token_sequence, count=fresh.count, meta_tick=consumer.meta_tick)
        if self.coverage is not None:
            for rule in FINAL_RULES:
                self.coverage.record('reached', rule, finish_tick=self.last_tick,
                    consumer=self.proof['consumer'], **repair)
            for rule in FINAL_RULES:
                self.coverage.record('checked', rule, tick=self.last_tick)
            self.coverage.finish()
        self.completed = True

    def capture_state(self, event, row):
        if self.failure is not None:
            return
        try:
            self.last_tick = event.tick
            if not self.initialized:
                if not row['reset']:
                    return
                self.initialized = True
            if row['reset']:
                self.model.reset(); self.plans.clear()
                self.original = self.last_recovery = self.consumer = None
                self.last_step = self.last_row = None
                self.proposal = None; self.completed = False
                self.proof.clear()
                return
            self.check(self.pipeline.last_tick, event.tick, 'lossless pipeline and iteration observations share one boundary')
            self.check(self.model.cursor, row['state'], 'registered iteration state from the preceding semantic event')
            for reason in ('middle-repair', 'final-repair'):
                first = self.proof.get('first_'+reason)
                if first is not None and 'registered_tick' not in first:
                    self.check(first['after'], row['state'], 'pipeline repair becomes the next registered iteration state')
                    first.update(registered_tick=event.tick, actual_registered=row['state'])
            cycle = self.pipeline.last_cycle
            self.check((int(cycle.middle_repair), int(cycle.final_repair)), tuple(row['repairs']),
                       'actual repair provenance is predicted by the independent selection model')
            for index, token in enumerate(cycle.tokens):
                if token is not None:
                    self.check(self.model.snapshot(token).count, row['stages'][index],
                               f'stage {index+1} carries its immutable original iteration')
            if self.last_recovery is not None and event.tick > self.last_recovery['tick']\
                    and not self.last_recovery.get('registered', False):
                self.check(self.last_recovery['after'], row['state'], 'accepted recovery becomes registered iteration state')
                self.last_recovery['registered'] = True
                self.last_recovery.update(registered_tick=event.tick, actual_registered=row['state'])
            recovery = None
            if row['redirect']['valid']:
                self.check(True, bool(self.plans), 'accepted iteration recovery has an independently owned plan')
                source, correction, request = self.plans[0]
                self.model.require(source)
                r = row['redirect']
                self.check((request.cfi_pc, request.pc, request.taken, request.branch_type, source.count),
                    (r['pc'], r['target'], r['taken'], r['kind'], r['count']),
                    'complete actual recovery input preserves the original counter and semantic outcome')
                self.check(True, self.pipeline.last_events.redirect.source is source.owner,
                           'pipeline and iteration recovery share the exact owned source, not just equal encoding')
                recovery = source, correction
            step = self.model.preview(cycle, recovery=recovery)
            self.proposal = step
            self.check(step.after, row['lookup'], 'new lookup uses the winning semantic event before registration')
            if recovery is not None:
                self.last_recovery = dict(tick=event.tick, source=recovery[0], before=step.before,
                    original=recovery[0].count, after=step.after, reason=step.reason,
                    actual_lookup=row['lookup'], actual_restore=row['redirect']['count'], registered=False)
            issued = self.model.apply(step, issued=self.pipeline.model.stages[0] if step.issue else None)
            if recovery is not None:
                self.plans.popleft()
            if step.reason in ('middle-repair', 'final-repair'):
                self.proof.setdefault('first_'+step.reason, dict(tick=event.tick,
                    original=step.source.count, token=step.source.token_sequence,
                    before=step.before, after=step.after, actual_lookup=row['lookup'],
                    issued_token=None if issued is None else issued.token_sequence))
            self.last_step, self.last_row = step, row
            self.proposal = None
        except Exception as error:
            self.failure = error
