"""Each old pair owns two successors, even beside both prior retirements."""
from copy import deepcopy
from suites.frontend.bpu.bpu.checker.dual_migration import DualMigrationChecks
from suites.frontend.bpu.bpu.coverage.dual_retirement import RULES
from suites.frontend.bpu.bpu.model.tage.dual_migration import provider
from suites.frontend.bpu.bpu.model.tage.dual_retirement import PATHS, OUTCOMES, SOURCE_COUNT, counters_after_service
from suites.frontend.bpu.bpu.model.tage.service import learning_inflight, pending_plan


class DualRetirementChecks(DualMigrationChecks):
    source_count = SOURCE_COUNT

    @staticmethod
    def acceptance_after_snapshot(tick):
        # ServiceMonitor snapshots child combinational ports at RisingStable.
        # Those values are candidates for the NEXT clock edge. The SDK instead
        # captures at DriveStable and stamps Transfer at that accepting edge.
        # One logical clock is two half ticks; never rebase from an actual tick.
        return tick + 2

    def __init__(self, pipeline, coverage):
        super().__init__(pipeline, coverage)
        self.closed = False

    def begin_burst(self):
        self.check('armed', self.phase, 'one qualified two-provider burst')
        tage = self.pipeline.model.sources.tage
        self.check(False, learning_inflight(tage), 'all normal preparation effects matured')
        self.check(((), ()), pending_plan(tage, self.table, self.bank), 'no earlier service can impersonate this burst')
        self.phase = 'burst'

    def payload(self, owner, ordinal):
        counters = counters_after_service(ordinal)
        return dict(self.proposal[1 - owner], counter=counters[1 - owner])

    def capture_state(self, event, row):
        if self.failure is not None:
            return
        try:
            self.last = event.tick, row
            self.check(False, bool(row['reset']), 'no reset replaces an old pair or its successor')
            self.check(0, row['reads'][1]['valid'], 'all four original pairs qualify without a training reread')
            if row['training']['valid'] and row['training']['ready']:
                self.check('burst', self.phase, 'public feedback belongs to the declared burst')
                self.check(True, len(self.input_ticks) < self.source_count, 'no extra original input')
                self.input_ticks.append(event.tick)
            ports = row['incoming']
            flags = tuple(port['valid'] for port in ports)
            self.check(True, flags in ((0, 0), (1, 1)), 'both original branch proposals arrive together')
            if not any(flags):
                return
            self.check('burst', self.phase, 'learning cannot escape its declared burst')
            ordinal = len(self.offered)
            self.check(True, ordinal < self.source_count and ordinal < len(self.input_ticks), 'one proposal per actual original pair')
            self.check(self.proposal, tuple(p['bits'] for p in ports), 'old ports, logical tags and counters stay immutable')
            self.check(True, event.tick > self.input_ticks[ordinal], 'learning follows its own accepted old source')
            if ordinal:
                self.check(self.offered[-1]['tick'] + 2, event.tick, 'all paired proposals actually adjacent')
            busy = any(p['valid'] and p['mask'] & (1 << self.bank) for p in row['reads'])
            self.check(False, bool(busy), 'unblocked service is a real precondition, not only a driver setting')
            self.check(True, len(row['dirty']) == 2 and all(len(way) == 4 for way in row['dirty']), 'complete actual retention vectors')
            dirty = tuple(sum(way) for way in row['dirty'])
            self.check((int(ordinal > 0),) * 2, dirty, 'both previous versions pending until their actual retirement')
            self.check(((int(ordinal > 0), 1),) * 2,
                       tuple((p['valid'], p['ready']) for p in row['writes']), 'both previous versions retire beside every successor')
            retired = None
            if ordinal:
                retired = tuple(p['bits'] for p in row['writes'])
                self.check(tuple(self.payload(owner, ordinal) for owner in range(2)), retired,
                           'simultaneous full services use each current owner and its preceding counter')
            self.offered.append(dict(tick=event.tick, accepts_at=self.acceptance_after_snapshot(event.tick),
                bits=tuple(p['bits'] for p in ports), dirty=dirty, retiring=retired))
        except Exception as error:
            self.failure = error

    def accepted_burst(self, events):
        self.check('burst', self.phase, 'all accepts belong to one dual burst')
        self.check((), tuple(self.accepted), 'the four-source burst is accepted once')
        self.check(self.source_count, len(events), 'all four genuine original pairs accepted')
        for index, (source, event) in enumerate(zip(self.sources, events, strict=True)):
            self.outcome(event, source, OUTCOMES)
            self.check(False, self.pipeline.model.sources.feedback_for(event[1]).reread, 'each source independently qualifies nonreread learning')
            if index:
                self.check(events[index - 1][0] + 2, event[0], 'actual inputs adjacent, not hidden serial replay')
        self.check(tuple(t for t, _ in events), tuple(self.input_ticks), 'all actual inputs keep their exact source receipts')
        controls = self.pipeline.last_resolution_controls
        self.check((events[-1][0], True), (controls[0], bool(controls[1][2] and controls[1][3])), 'both learning predictors enabled')
        self.check(self.source_count, len(self.offered), 'all old proposals compared before acceptance qualification')
        self.accepted.extend(events)
        self.reach(RULES[1], accepted_ticks=list(self.input_ticks), reread=False)
        self.reach(RULES[2], actual_proposals=deepcopy(self.offered))

    def write_accepted(self, owner, transfer):
        self.check('burst', self.phase, 'SDK service belongs to the in-flight paired burst')
        self.check(True, owner in (0, 1), 'only the two declared current owners')
        index = len(self.written[owner])
        self.check(True, index < self.source_count and index < len(self.offered), 'no missing proposal or extra actual service')
        self.check(self.acceptance_after_snapshot(self.offered[index]['accepts_at']), transfer.accepted_tick,
                   'actual service follows accepted entry-buffer learning on the next cycle')
        self.check(self.payload(owner, index + 1), transfer.value, 'each actual full version uses current owner and cumulative counter')
        self.written[owner].append((transfer.accepted_tick, deepcopy(transfer.value)))

    def services_complete(self):
        self.check('burst', self.phase, 'qualify actual services once')
        self.check((4, 4, 4), (len(self.sources), len(self.accepted), len(self.offered)), 'all distinct source, accept and proposal identities mandatory')
        self.check((4, 4), tuple(map(len, self.written.values())), 'eight SDK-confirmed full services mandatory')
        ticks = tuple(tuple(t for t, _ in self.written[owner]) for owner in range(2))
        self.check(ticks[0], ticks[1], 'both owner services pair at every version')
        overlaps = []
        for index in range(1, self.source_count):
            tick = self.offered[index]['accepts_at']
            self.check(tick, ticks[0][index - 1], 'every successor coincides with both prior SDK retirements')
            self.check(tuple(self.written[owner][index - 1][1] for owner in range(2)),
                       self.offered[index]['retiring'], 'same-cycle sampled service equals SDK transfer, not a later receipt')
            overlaps.append(dict(successor=index + 1, snapshot_tick=self.offered[index]['tick'], accepted_tick=tick))
        self.reach(RULES[3], actual_writes=deepcopy(self.written))
        self.reach(RULES[4], actual_overlap=overlaps)
        self.reach(RULES[5], final_two_services={owner: deepcopy(self.written[owner][-2:]) for owner in range(2)})
        self.phase = 'consumers'

    def consumed(self, name, source):
        self.check('consumers', self.phase, 'fresh consumers follow complete actual service')
        self.check(True, name in PATHS and name not in self.consumers, 'each history has exactly one final consumer')
        self.check(True, source.prediction_tick > max(v[-1][0] for v in self.written.values()), 'consumer is fresh after the fourth paired service')
        self.check(self.read(self.before[name]).context, self.read(source).context, 'exact genuine original or displaced history')
        providers = (provider(1, 0), provider(0, 7)) if name == 'original' else (None, None)
        self.check(((0, 3), providers), self.profile(source), 'complete Main identities, final providers and displaced misses')
        self.consumers[name] = source
        if set(self.consumers) == set(PATHS):
            self.reach(RULES[6], consumers={n: dict(prediction_tick=s.prediction_tick, meta_tick=s.meta_tick,
                compared=self.profile(s)) for n, s in self.consumers.items()})

    def finish(self):
        self.check(False, self.closed, 'final comparison credit is single-use')
        self.check('consumers', self.phase, 'all actual paired services qualified')
        self.check(set(PATHS), set(self.consumers), 'both full history consumers mandatory')
        self.check(tuple(self.frozen), tuple(s.meta.resolve for s in self.sources), 'all four actual old metadata snapshots immutable')
        self.check(tuple(self.defined), tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s))
                   for s in self.sources), 'all four independently owned old definitions immutable')
        self.reach(RULES[7], original_meta_ticks=[s.meta_tick for s in self.sources], compared_consumers=2)
        self.check(set(RULES), self.completed, 'every semantic obligation mandatory before checked')
        self.closed = True
        for rule in RULES:
            self.coverage.record('checked', rule, **self.witnesses[rule])
        for s in (*self.sources, *self.before.values(), *self.consumers.values()):
            self.pipeline.retire_source(s.meta_tick)
