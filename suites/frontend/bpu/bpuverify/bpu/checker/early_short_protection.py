"""Compare one original short record, then terminate its actual issue window."""
import asyncio
from dataclasses import asdict

from bpuverify.bpu.checker.early_opposition import EarlyOppositionChecks
from bpuverify.bpu.checker.early_protection import EarlyProtectionChecks
from bpuverify.bpu.model.early_aging import allocation
from bpuverify.bpu.model.early_opposition import provider
from bpuverify.bpu.model.early_protection import ProtectionLedger, guidance, Identity
from bpuverify.bpu.model.early_short_protection import EDGES, rules, original_identity
from bpuverify.utage.model.semantic import tag


class EarlyShortProtectionChecks(EarlyProtectionChecks):
    edge_definitions = EDGES
    provider_rule = 'short-not-long-provider'

    def __init__(self, coverage, mode, pc):
        super().__init__(coverage, mode, pc)
        self.intended = original_identity(pc)
        self.acceptance = self.selected = None
        self.selected_tick = None
        self.accepted_sources = []
        self.read_allocation = self.processing_allocation = None
        self.parallel_pending = None
        self.parallel_confirmed = []
        self.parallel_directions = {}
        self.seeded = False
        self.window_active = self.longer_window = False

    def rule_names(self):
        return rules(self.mode)

    def strong_negative(self, source):
        # Keep the normal long-path discovery proof, but it is NOT the short
        # record whose strength is about to be tracked.
        EarlyOppositionChecks.strong_negative(self, source)
        self.remember(source)

    @property
    def requires_parallel_allocation(self):
        return self.mode != 'upper-hold'

    def open_original(self, *, longer=False, expect_taken=None):
        self.check(False, self.window_active, 'one issue window at a time, including S3 receipt delivery')
        self.check(True, self.acceptance is None or self.acceptance.done(), 'prior issue window has completed')
        self.check(True, expect_taken is None or type(expect_taken) is bool,
                   'window direction is an explicitly declared semantic boolean')
        self.check(True, not longer or expect_taken is None, 'allocated direction comes from original S3 guidance')
        if longer:
            self.check(True, bool(self.parallel_confirmed), 'new longer record was actually confirmed before querying')
            self.check(True, self.parallel_confirmed[-1][3] in self.parallel_directions,
                       'confirmed longer record retains its original semantic direction owner')
        taken = self.parallel_directions[self.parallel_confirmed[-1][3]] if longer else self.record_taken
        self.window_taken = taken if expect_taken is None else expect_taken
        self.acceptance = asyncio.get_running_loop().create_future()
        self.selected = self.selected_tick = None
        self.window_active, self.longer_window = True, longer
        self.acceptance_identity = self.parallel_confirmed[-1][0] if longer else self.intended
        return self.acceptance

    def candidates(self, row, events, cycle, model, phase, previous):
        result = super().candidates(row, events, cycle, model, phase, previous)
        self.first = (cycle.tokens[0] if cycle.fires[1] and not cycle.flushes[0] else None)
        self.enabled_short = cycle.enabled[1]
        self.observed_protection = row['observed']['early_direction']['useful']
        short = model.sources.short
        self.read_allocation = None
        if short.offered is not None and cycle.enabled[1] and events.initialization_complete:
            protection = tuple(short.useful[table].get(index, 0)
                for table, index in enumerate(short.offered.indices))
            self.read_allocation = short.offered, allocation(short.offered, protection), protection
        self.current_parallel = None
        self.current_eligibility = None
        if self.applied is not None and self.identity is not None:
            decision = guidance(self.applied.feedback, self.identity)
            if decision is not None and decision[1] == 'penalty':
                self.check(True, self.processing_allocation is not None
                    and self.processing_allocation[0] is self.applied.feedback,
                    'allocation read keeps the exact original guidance')
                feedback, proposed, protection = self.processing_allocation
                self.check(self.identity.table, proposed.provider, 'wrong original provider owns allocation eligibility')
                self.check(True, proposed.candidate is None or self.identity.table < proposed.candidate < 2,
                           'only a strictly longer record may be allocated')
                control = row['observed']['early_direction']['maintenance']
                permitted = int(proposed.candidate == 1)
                commands = tuple((int(proposed.candidate == table), int(self.identity.table == table))
                                 for table in range(2))
                self.check((1, 1, 2*permitted, commands),
                    (control['fire'], control['need'], control['mask'],
                     tuple((table['allocate'], table['update']) for table in control['tables'])),
                    'same event updates its original provider and only permits eligible longer allocation')
                identity = Identity(1, feedback.indices[1], tag(feedback.pc, feedback.context, 1),
                                    self.identity.position)
                self.current_eligibility = identity, protection, permitted
                if permitted:
                    self.current_parallel = identity, protection, decision[0]
        if self.parallel_pending is not None:
            identity, written, owner, protection = self.parallel_pending
            self.check(written+2, self.pipeline.current_event.tick,
                       'long allocation has the same next actual-state confirmation as short penalty')
            self.check(2, self.observed_protection[1][identity.index],
                       'actual new longer protection initialized from common prestate')
        return result

    def checked(self, tick, *candidates):
        was_pending = self.pending
        super().checked(tick, *candidates)
        if self.current_eligibility is not None:
            identity, protection, permitted = self.current_eligibility
            self.reach('longer-allocation-eligibility', tick, identity=asdict(identity),
                       common_read_protection=protection, permitted=bool(permitted))
        if self.parallel_pending is not None:
            identity, written, owner, protection = self.parallel_pending
            self.parallel_confirmed.append((identity, written, tick, owner))
            self.reach('parallel-long-allocation', tick, identity=asdict(identity),
                       owner=owner, written_tick=written, actual_confirmation_tick=tick,
                       common_read_protection=protection)
        self.parallel_pending = None
        if self.current_parallel is not None:
            identity, protection, taken = self.current_parallel
            self.check(True, self.pending is not None, 'parallel allocation belongs to the short event ledger')
            written, event, _ = self.pending
            self.parallel_pending = identity, written, event.owner, protection
            self.parallel_directions[event.owner] = taken
        self.processing_allocation = self.read_allocation
        if (was_pending is not None and was_pending[1].kind == 'neutral'
                and was_pending[1].counter_after == 0 and was_pending[1].after == 1):
            self.seeded = True
            self.reach('neutral-seed-confirmed', tick)
        if (self.window_active and self.selected is not None and self.first is not None
                and tick > self.selected_tick):
            self.check(False, True, 'no younger S1 acceptance after the declared window endpoint')
        if self.acceptance is None or self.acceptance.done() or self.first is None or not self.enabled_short:
            return
        value = provider(self.pipeline.model.sources, self.first)
        if (value is None or (value.key, value.tag, value.position) !=
                (self.acceptance_identity.key, self.acceptance_identity.tag, self.acceptance_identity.position)
                or (value.counter >= 4) != self.window_taken):
            return
        self.accepted_provider(value, tick)
        self.selected, self.selected_tick = self.first, tick
        self.accepted_sources.append((self.first, tick))
        # PipelineChecker calls checked only AFTER full DUT comparison and
        # reference advancement. Return the original native event, not a new
        # event manufactured from a mutable monitor predicate.
        self.acceptance.set_result(self.pipeline.current_event)

    def accepted_provider(self, value, tick):
        """Validate the declared endpoint after common identity/direction matching."""
        if self.longer_window:
            self.check(4 if self.window_taken else 3, value.counter,
                       'new longer provider presents its independently initialized direction strength')
        elif self.identity is None:
            self.check((1, 1), (value.counter, self.observed_protection[0][value.index]),
                       'normal learning left the declared original short NT record')
            self.identity = self.intended
            self.ledger = ProtectionLedger(counter=1, protection=1)
        elif self.seeded:
            self.reach('stable-original', tick, identity=asdict(self.identity), owner=self.first.sequence)
        if not self.longer_window:
            self.reach(self.provider_rule, tick, identity=asdict(self.identity), owner=self.first.sequence)

    def window_receipt(self, source):
        token = self.remember(source)
        self.check(True, token.sequence == self.selected.sequence and token.history is self.selected.history
                   and source.prediction_tick == self.selected_tick,
                   'one complete S3 receipt belongs to the exact bounded S1 acceptance')
        self.check(True, self.acceptance.done(), 'monitor, not a fixed duration, closed issue')
        self.window_active = False
        if self.longer_window:
            identity, _, compared, owner = self.parallel_confirmed[-1]
            self.check(True, source.prediction_tick > compared, 'new longer consumer follows actual allocation confirmation')
            self.reach('fresh-long-consumer', source.meta_tick, identity=asdict(identity),
                       owner=token.sequence, allocation_owner=owner, prediction_tick=source.prediction_tick)
        else:
            self.reach('actual-acceptance-window', source.meta_tick, owner=token.sequence,
                       prediction_tick=self.selected_tick)

    def finish_boundaries(self, owners):
        self.check(True, self.seeded, 'neutral bootstrap crossed a complete actual comparison')
        self.check(None, self.parallel_pending, 'parallel longer allocation is actually compared')
        if self.requires_parallel_allocation:
            self.check(True, bool(self.parallel_confirmed), 'penalty and longer allocation both confirmed')
        super().finish_boundaries(owners)
