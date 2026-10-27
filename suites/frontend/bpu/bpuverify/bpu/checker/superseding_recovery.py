"""Two original lifetimes and both intermediate/final observable histories."""
from copy import deepcopy

from bpuverify.bpu.checker.common_query import CommonQueryChecks
from bpuverify.bpu.model.common_history import Value
from bpuverify.bpu.model.superseding_recovery import RULES


class SupersedingRecoveryChecks(CommonQueryChecks):
    def __init__(self, pipeline, *, program, coverage, **options):
        super().__init__(pipeline, **options)
        self.program, self.semantic_coverage = program, coverage
        self.selected = None
        self.recoveries = []
        self.reached = set()
        self.intermediate_state = self.final_state = self.final_consumer = None
        self.closed = False

    def mark(self, rule, **witness):
        self.check_query(True, rule in RULES, 'only declared semantic obligations receive credit')
        self.reached.add(rule)
        self.semantic_coverage.record('reached', self.program.profile, rule, **witness)

    def arm(self, older, younger):
        old, young = self.source(older), self.source(younger)
        self.check_query(True, old.owner is not young.owner and old.token_sequence < young.token_sequence,
                         'second correcting branch is older and survives the first cancellation')
        self.check_query(True, 0 < old.count < young.count < 255, 'original age is distinguishable, not saturated')
        selected = []
        for receipt, iteration in ((older, old), (younger, young)):
            token = self.pipeline.source_token(receipt)
            query = self.query.snapshot(token)
            self.check_query(True, query.published, 'each recovery has an already published real original')
            self.check_query(Value(True, 255, 15), query.metadata, 'normal loop independently establishes common history')
            self.check_query((1,), query.block.conditionals, 'one genuine conditional, no invented suffix')
            selected.append(dict(receipt=receipt, meta=deepcopy(receipt.meta), iteration=iteration,
                                 query=query, token=token))
        self.selected = tuple(selected)
        self.mark(RULES[0], older=old.token_sequence, younger=young.token_sequence)
        self.mark(RULES[1], older_count=old.count, younger_count=young.count)

    def capture_state(self, event, row):
        recording = self.selected is not None and bool(row['iteration']['redirect']['valid'])
        planned = self.plans[0] if recording and self.plans else None
        super().capture_state(event, row)
        if self.failure is not None:
            return
        try:
            if recording:
                self.check_query(True, planned is not None, 'every superseding recovery has an owned planned source')
                source, branch, request = planned
                index = len(self.recoveries)
                self.check_query(True, index < 2, 'only the two declared corrections may be accepted')
                chosen = self.selected[1-index]
                self.check_query(True, source is chosen['iteration'], 'actual recovery order is younger then older')
                # Keep references so the inherited independent observer also
                # confirms each next registered iteration, including first.
                self.recoveries.append(dict(tick=event.tick, original=source.count,
                    token=source.token_sequence, complete_input=deepcopy(row['iteration']['redirect']),
                    iteration_receipt=self.last_recovery))
            if len(self.recoveries) == 2 and event.tick == self.recoveries[1]['tick'] + 2:
                self.check_query(self.program.intermediate.mapping(), row['state'],
                                 'the younger prefix registers before the older one replaces it')
                self.intermediate_state = dict(tick=event.tick, actual=deepcopy(row['state']))
            if self.final_state is None and len(self.recoveries) == 2 and event.tick > self.recoveries[1]['tick'] + 2:
                self.check_query(self.program.restored, self.query.value, 'final committed prefix belongs only to the older original')
                self.check_query(self.program.iteration(self.selected[0]['iteration'].count), self.model.cursor,
                                 'final iteration comes from the older original, not younger/current state')
                self.final_state = dict(tick=event.tick, actual=deepcopy(row['state']), iteration=row['iteration']['state'])
        except Exception as error:
            self.failure = error

    def accepted_pair(self, ticks):
        self.raise_failure()
        self.check_query(tuple(ticks), tuple(v['tick'] for v in self.recoveries), 'driver receipts equal actual compared input acceptances')
        self.check_query(2, len(self.recoveries), 'both input events are required, even if only the last wins')
        self.check_query(ticks[0]+2, ticks[1], 'the two actual recoveries are adjacent')
        self.mark(RULES[2], ticks=ticks)
        self.mark(RULES[3], source_tokens=tuple(v['token'] for v in self.recoveries))

    def consumed_winner(self, receipt):
        self.raise_failure()
        token = self.pipeline.source_token(receipt)
        source = self.query.snapshot(token)
        iteration = self.source(receipt)
        expected = Value(True, self.program.restored.ghr, self.program.restored.bw)
        self.check_query(True, self.final_state is not None and receipt.prediction_tick > self.recoveries[-1]['tick'],
                         'a genuinely fresh consumer follows the final registered recovery')
        self.check_query(self.program.consumer_pc, token.pc, 'consumer is on the surviving direct-only drain path')
        self.check_query((), source.block.conditionals, 'consumer cannot add a hidden conditional outcome')
        self.check_query(expected, source.metadata, 'fresh public history consumes the winning executed prefix')
        self.check_query(0, iteration.count, 'direct-only consumer clears the recovered loop iteration')
        self.check_query(True, source.published, 'winning source really completed and published')
        self.final_consumer = dict(prediction_tick=receipt.prediction_tick, meta_tick=receipt.meta_tick,
            token=token.sequence, pc=token.pc, history=source.metadata.mapping(), iteration=iteration.count)
        self.mark(RULES[6], **self.final_consumer)

    def finish_pair(self):
        self.raise_failure()
        self.check_query(False, self.closed, 'complete result cannot be credited twice')
        self.check_query(True, self.intermediate_state is not None and self.final_state is not None and self.final_consumer is not None,
                         'registered state and fresh complete consumer both required')
        self.check_query(False, bool(self.plans) or bool(self.pipeline.redirect_plans), 'all recovery plans actually accepted')
        self.check_query(True, all(v['iteration_receipt'].get('registered') for v in self.recoveries),
                         'each intermediate iteration has an independently compared register witness')
        self.mark(RULES[4], compared_queries=self.query_checked)
        self.mark(RULES[5], final_state=self.final_state)
        for original in self.selected:
            self.check_query(original['meta'], original['receipt'].meta, 'later corrections do not mutate original metadata')
            self.check_query(original['query'], self.query.snapshot(original['token']), 'original read and published history immutable')
        self.mark(RULES[7], originals=len(self.selected))
        self.check_query(set(RULES), self.reached, 'all declared obligations before complete checked credit')
        self.closed = True

    def summary(self):
        return dict(program=self.program.state(), closed=self.closed, reached=sorted(self.reached),
            recoveries=[dict(tick=v['tick'], original=v['original'], token=v['token'], complete_input=v['complete_input'],
                registered={k:x for k,x in v['iteration_receipt'].items() if k != 'source'}) for v in self.recoveries],
            original_counts=None if self.selected is None else [v['iteration'].count for v in self.selected],
            intermediate_state=self.intermediate_state, final_state=self.final_state, final_consumer=self.final_consumer,
            comparisons=dict(queries=self.query_checked, public_metadata=self.query_metadata))
