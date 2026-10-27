"""Associate by owned history/instruction; compare complete services independently."""
from copy import deepcopy

from bpuverify.bpu.checker.neighbor_migration import NeighborMigrationChecks
from bpuverify.bpu.coverage.asymmetric_retirement import RULES
from bpuverify.bpu.model.pipeline import Resolution, Outcome
from bpuverify.bpu.model.selection import Kind
from bpuverify.bpu.model.tage.asymmetric_retirement import (
    SOURCE_COUNT, INPUT_NAMES, OUTCOMES, PROPOSALS, PRELUDE_PLAN, FINAL_PLAN,
    PRE_DIRTY_COUNTS, SERVICE_IDENTITIES, expected_profile)
from bpuverify.bpu.model.tage.dual_migration import PC, POSITIONS, TARGETS, TABLE
from bpuverify.bpu.model.tage.neighbor_migration import expected_profile as neighbor_profile
from bpuverify.bpu.model.tage.service import learning_inflight, pending_plan
from bpuverify.tage.model.semantic import coordinate


class AsymmetricRetirementChecks(NeighborMigrationChecks):
    source_count = SOURCE_COUNT
    input_names = INPUT_NAMES
    history_profile = staticmethod(expected_profile)
    rules = RULES

    def __init__(self, pipeline, coverage):
        super().__init__(pipeline, coverage)
        self.pending_round = 0

    def arm_neighbor(self, current):
        self.check('armed', self.phase, 'normal neighbor setup follows migration')
        self.check(tuple(s.name for s in self.neighbor_intents), tuple(self.neighbor_labels),
                   'all normal neighbor effects completed')
        self.check(None, self.neighbor_active, 'no unfinished neighbor feedback')
        self.check(set(self.history_paths), set(current), 'all genuine histories present')
        for name, source in current.items():
            self.check(((1, 3), neighbor_profile(name, serviced=False)[1]), self.profile(source),
                       'normal neighbor setup has not changed target counters')
        self.migration_before, self.neighbor_before = self.before, current
        self.phase = 'neighbor-prepared'

    def arm_asymmetric(self, warm_source, warm_event, current):
        self.check('neighbor-prepared', self.phase, 'one fresh target feedback after normal neighbor setup')
        self.outcome(warm_event, warm_source, OUTCOMES[1])
        self.check(set(self.history_paths), set(current), 'all warm history consumers present')
        for name, source in current.items():
            self.check(True, source.prediction_tick > warm_event[0], 'warm consumers follow actual feedback')
            self.check(self.read(self.neighbor_before[name]).context, self.read(source).context,
                       'warm feedback preserves each logical history')
            self.check(self.history_profile(name, serviced=False), self.profile(source),
                       'full Main and TAGE warm state derived from normal feedback')
        self.identities = {}
        for prefix, name in (('target', 'original'), ('neighbor', 'neighbor')):
            read = self.read(current[name])
            row, raw = coordinate(PC, read.context, TABLE)[1:]
            self.check(row, read.rows[TABLE], 'identity row comes from owned history geometry')
            self.check(tuple(sorted(raw ^ p for p in POSITIONS)), tuple(sorted(e.tag for e in read.entries[TABLE])),
                       'complete tags identify the original instructions')
            for label, position in zip(('a', 'b'), POSITIONS, strict=True):
                self.identities[prefix + '-' + label] = dict(row=row, valid=1, tag=raw ^ position)
        self.check(True, self.identities['target-a']['row'] != self.identities['neighbor-a']['row'],
                   'neighbor is a distinct logical history, not another receipt of the target')
        self.requests = (self.sources[0], current['neighbor'], current['original'], *self.sources[1:])
        tokens = tuple(self.pipeline.source_token(s) for s in self.requests)
        self.check(self.input_count, len({id(t.history) for t in tokens}), 'all five original checkpoints distinct')
        for token, outcomes in zip(tokens, OUTCOMES, strict=True):
            request = Resolution(token.history, PC, tuple(Outcome(POSITIONS[i], TARGETS[i], Kind.CONDITIONAL,
                taken, mispredict=wrong) for i, taken, wrong in outcomes), origin=token)
            self.check(False, self.pipeline.model.sources.feedback_for(request).reread,
                       'each source independently qualifies without training reread')
        tage = self.pipeline.model.sources.tage
        self.check(False, learning_inflight(tage), 'warm feedback matured before the experiment')
        self.check(((), ()), pending_plan(tage, TABLE, self.bank), 'warm feedback already serviced')
        self.initial_overflows = tage.cache[TABLE, self.bank].overflows
        self.expected_offers = tuple(tuple(None if item is None else self.payload(item) for item in pair)
                                     for pair in PROPOSALS)
        self.expected_plan = self.concrete(FINAL_PLAN)
        self.input_frozen = tuple(deepcopy(s.meta) for s in self.requests)
        self.input_defined = tuple(deepcopy(self.pipeline.model.sources.defined_metadata(t)) for t in tokens)
        self.before, self.phase = current, 'neighbor-armed'
        self.reach(self.rules[1], warm_tick=warm_event[0], histories={n: self.profile(s) for n, s in current.items()},
                   sources={n: s.meta_tick for n, s in zip(INPUT_NAMES, self.requests, strict=True)})

    def payload(self, item):
        name, counter = item
        return dict(self.identities[name], counter=counter)

    def concrete(self, plan):
        return tuple(tuple(self.payload(item) for item in owner) for owner in plan)

    def capture_state(self, event, packet):
        if self.failure is not None:
            return
        try:
            row = packet['state']
            self.last = event.tick, row
            self.check(0, row['reset'], 'reset cannot replace pending learning')
            self.check(0, row['reads'][1]['valid'], 'all five feedbacks avoid training SRAM rereads')
            busy = any(p['valid'] and p['mask'] & (1 << self.bank) for p in row['reads'])
            if busy:
                self.check((0, 0), tuple(p['ready'] for p in row['writes']), 'actual reads block both services')
            if self.phase == 'holding':
                self.check(True, bool(busy), 'same-bank read competition remains uninterrupted')
            if row['training']['valid'] and row['training']['ready']:
                self.check('holding', self.phase, 'only declared held feedback')
                self.check(True, len(self.input_ticks) < self.input_count, 'no sixth feedback')
                p = row['prediction']
                self.check(True, bool(p['valid'] and p['ready'] and p['pc'] % 4 == self.bank),
                           'real prediction accepts beside each feedback')
                self.input_ticks.append(event.tick)
            if any(p['valid'] for p in row['incoming']):
                self.check('holding', self.phase, 'all proposals belong to held read competition')
                index = len(self.offered)
                self.check(True, index < self.input_count and index < len(self.input_ticks),
                           'one complete proposal per actual accepted source')
                actual = tuple(p['bits'] if p['valid'] else None for p in row['incoming'])
                self.check(self.expected_offers[index], actual, 'complete original proposal ports and payloads')
                self.check((4, 4), tuple(map(len, row['dirty'])), 'complete actual retention prestate')
                self.check(PRE_DIRTY_COUNTS[index], tuple(sum(v) for v in row['dirty']),
                           'single-owner pressure creates distinct pending lifetimes')
                # Only active proposals have a meaningful retained hit/rank.
                hits, ranks = [], []
                for port, proposal in enumerate(actual):
                    if proposal is None:
                        hits.append(None); ranks.append(None)
                        continue
                    observed = packet['owner_hits'][port]
                    hit = (int(any(observed['owner0'])), observed['owner1'])
                    wanted = (0, 1) if index == 0 or index >= 3 and port == 0 else (
                        (1, 0) if index >= 3 else (0, 0))
                    self.check(wanted, hit, 'actual full-key hit follows logical current owner, not old port')
                    rank = None if not any(hit) else packet['hit_ranks'][port][hit.index(1)]
                    if rank is not None:
                        self.check(1 if index >= 3 and port == 1 else 0, rank,
                                   'late updates reach distinct retained lifetimes without same-destination ambiguity')
                    hits.append(hit); ranks.append(rank)
                self.check(True, event.tick > self.input_ticks[index], 'proposal follows its own actual input')
                if index in (1, 2, 4):
                    self.check(self.offered[-1]['tick'] + 2, event.tick, 'proposals adjacent within each burst')
                self.offered.append(dict(tick=event.tick, bits=deepcopy(actual), dirty=deepcopy(row['dirty']),
                                         hits=tuple(hits), ranks=tuple(ranks)))
            if self.phase == 'holding' and self.pending_ready:
                self.check(((1, 0), (1, 0)), tuple((p['valid'], p['ready']) for p in row['writes']),
                           'both logical result fronts stay blocked')
        except Exception as error:
            self.failure = error

    def accepted_burst(self, events):
        self.check('holding', self.phase, 'acceptance under real read competition')
        first = len(self.accepted)
        self.check(True, first in (0, 3), 'exactly the prelude and late feedback bursts')
        self.check(0 if first == 0 else 1, self.pending_round, 'prelude is qualified before late feedback')
        self.check(3 if first == 0 else 2, len(events), 'complete declared burst')
        last = first + len(events)
        for index, (source, event, outcomes) in enumerate(zip(self.requests[first:last], events, OUTCOMES[first:last], strict=True)):
            self.outcome(event, source, outcomes)
            self.check(False, self.pipeline.model.sources.feedback_for(event[1]).reread, 'original nonreread qualification')
            if index:
                self.check(events[index - 1][0] + 2, event[0], 'actual accepts adjacent within the burst')
        self.check(tuple(t for t, _ in events), tuple(self.input_ticks[first:]), 'driver receipts equal actual public acceptances')
        controls = self.pipeline.last_resolution_controls
        self.check((events[-1][0], True), (controls[0], bool(controls[1][2] and controls[1][3])),
                   'Main and TAGE actually enabled at acceptance')
        self.accepted.extend(events)
        if last == self.input_count:
            self.reach(self.rules[2], accepted_ticks=list(self.input_ticks), sources=INPUT_NAMES,
                       prediction_concurrent=True, reread=False)

    def pending(self):
        self.check('holding', self.phase, 'pending learning remains under held reads')
        self.check(True, self.pending_round < 2, 'each pending boundary is single-use')
        count = 3 if self.pending_round == 0 else self.input_count
        self.check(count, len(self.accepted), 'all actual burst acceptances required')
        self.check(count, len(self.offered), 'all actual complete proposals required')
        tage = self.pipeline.model.sources.tage
        self.check(False, learning_inflight(tage), 'learning maturity is distinct from input acceptance')
        expected = self.concrete(PRELUDE_PLAN if self.pending_round == 0 else FINAL_PLAN)
        self.check(expected, pending_plan(tage, TABLE, self.bank), 'latest result per logical identity and current owner')
        self.check(self.initial_overflows, tage.cache[TABLE, self.bank].overflows, 'no pending logical result replaced')
        self.check((0, 0), tuple(map(len, self.written.values())), 'no service under held reads')
        self.reach(self.rules[8 if self.pending_round == 0 else 3], actual_proposals=deepcopy(self.offered),
                   expected_pending=expected, service_identities=SERVICE_IDENTITIES, actual_commits=0)
        self.pending_round += 1
        self.pending_ready = True

    def release(self):
        self.check(2, self.pending_round, 'late learning required before release')
        super().release()

    def write_accepted(self, owner, transfer):
        self.check('service', self.phase, 'actual SDK service follows read release')
        self.check(True, owner in (0, 1) and len(self.written[owner]) < self.service_count,
                   'no duplicate or undeclared service')
        index = len(self.written[owner])
        self.check(True, transfer.accepted_tick > self.release_tick and transfer.accepted_tick > self.offered[-1]['tick'],
                   'service follows all original proposals and read release')
        self.check(self.expected_plan[owner][index], transfer.value,
                   f'complete {SERVICE_IDENTITIES[owner][index]} service on current owner {owner}')
        if index:
            self.check(self.written[owner][-1][0] + 2, transfer.accepted_tick, 'each owner drains its two pending identities on adjacent cycles')
        self.written[owner].append((transfer.accepted_tick, deepcopy(transfer.value)))

    def services_complete(self):
        self.check('service', self.phase, 'service completion is single-use')
        self.check((2, 2), tuple(map(len, self.written.values())), 'all four complete SDK services mandatory')
        # Same ordinal across owners is deliberately NOT one paired transaction.
        self.reach(self.rules[5], identities=SERVICE_IDENTITIES, actual_writes=deepcopy(self.written))
        self.phase = 'consuming'

    def finish(self):
        self.check(False, self.closed, 'final checked credit is single-use')
        self.check('consuming', self.phase, 'all actual services required')
        self.check({(p, n) for p in ('blocked', 'serviced') for n in self.history_paths}, set(self.consumers),
                   'all six complete history consumers required')
        self.check(self.input_frozen, tuple(s.meta for s in self.requests), 'all five complete actual input snapshots immutable')
        self.check(self.input_defined, tuple(self.pipeline.model.sources.defined_metadata(self.pipeline.source_token(s))
                   for s in self.requests), 'all five independent source definitions immutable')
        self.reach(self.rules[7], input_meta_ticks=[s.meta_tick for s in self.requests], compared_consumers=len(self.consumers))
        self.check(set(self.rules), self.completed, 'every semantic obligation required before checked')
        for rule in self.rules:
            self.coverage.record('checked', rule, **self.witnesses[rule])
        self.closed = True
        retired = set()
        for s in (*self.requests, *self.migration_before.values(), *self.neighbor_before.values(),
                  *self.before.values(), *self.consumers.values()):
            if s.meta_tick not in retired:
                self.pipeline.retire_source(s.meta_tick)
                retired.add(s.meta_tick)
