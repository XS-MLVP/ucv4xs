"""Associate public input, check every shadow/counter cell, derive drain independently."""
from collections import deque
from copy import deepcopy
from dataclasses import asdict

from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from suites.frontend.bpu.abtb.monitor.state.counter import public_transaction
from suites.frontend.bpu.abtb.model.state.writebuffer import CapacityReference


class CapacityChecker:
    def __init__(self, *, scope):
        self.scope, self.reference = scope, CapacityReference()
        self.scoreboard = Scoreboard('abtb.write_buffer_capacity')
        self.planned, self.records, self.accepted_events = deque(), [], []
        self.drains, self.actions, self.pending_drains, self.pending_actions = [], [], [], []
        self.failure, self.last_tick, self.initialized = None, None, False

    def raise_failure(self):
        if self.failure is not None:
            raise self.failure

    def check(self, expected, actual, **request):
        self.raise_failure()
        self.scoreboard.check(expected=expected, actual=actual,
            context=CheckContext(scoreboard=self.scoreboard.name, mode=ScoreboardMode.DIRECT,
                request=dict(scope=self.scope, observed_tick=self.last_tick, **request)))

    def plan(self, transaction):
        self.raise_failure()
        self.planned.append(asdict(transaction))

    def capture(self, observation):
        if self.failure is None:
            try:
                self.observe(observation)
            except Exception as error:
                self.failure = error

    def observe(self, observation):
        row, event = observation.value, observation.event
        self.records.append(dict(tick=event.tick, **deepcopy(row)))
        self.last_tick = event.tick
        counter = row['counter']
        ref = self.reference
        if counter['reset']:
            # The sampled RisingEdge is after the reset edge: the DUT shadow
            # slots and counters have already cleared, while the reference
            # still holds the pre-reset state until advance() below. Check the
            # cleared hardware against a fresh reference instead of comparing
            # it with stale expectations.
            from suites.frontend.bpu.abtb.model.state.writebuffer import CapacityReference
            ref = CapacityReference()
            self.reference = ref
            for bank, actual in enumerate(row['banks']):
                for slot, wanted in enumerate(ref.buffers[bank].slots):
                    self.check(wanted, actual['slots'][slot],
                               phase='reset-clears-shadow-slot', bank=bank, slot=slot)
                self.check(ref.buffers[bank].plru, actual['plru'],
                           phase='reset-clears-write-buffer-plru', bank=bank)
            self.check(tuple(ref.counter.cells), counter['cells'],
                       phase='reset-clears-all-1024-counters')
            self.initialized = True
        elif self.initialized:
            self.check(self.records[-2]['tick'] + 2, event.tick, phase='continuous-cycle-observation')
            for bank, actual in enumerate(row['banks']):
                for slot, wanted in enumerate(ref.buffers[bank].slots):
                    self.check(wanted, actual['slots'][slot], phase='full-shadow-slot', bank=bank, slot=slot)
                self.check(ref.buffers[bank].plru, actual['plru'], phase='write-buffer-miss-plru', bank=bank)
            mismatch = next((i for i, (wanted, observed) in enumerate(zip(ref.counter.cells, counter['cells'], strict=True))
                             if wanted != observed), None)
            point = None if mismatch is None else dict(bank=mismatch // 256,
                set_index=(mismatch % 256) // 4, way=mismatch % 4,
                expected=ref.counter.cells[mismatch], actual=counter['cells'][mismatch])
            self.check(tuple(ref.counter.cells), counter['cells'], phase='all-1024-counters', first_mismatch=point)
            self.drains.extend(dict(checked_tick=event.tick, **item) for item in self.pending_drains)
            self.actions.extend(dict(checked_tick=event.tick, **item) for item in self.pending_actions)
        else:
            self.check(1, counter['reset'], phase='initialize-from-real-reset')
            self.initialized = True
        accepted = None
        if counter['training']['valid']:
            self.check(True, bool(self.planned), phase='every-public-input-is-planned')
            expected = self.planned.popleft()
            self.check(expected, public_transaction(counter['training']['bits']), phase='complete-public-payload')
            self.accepted_events.append(event)
            if counter['enable'] and expected['meta']['valid']:
                accepted = expected
        if not counter['reset']:
            for bank, actual in enumerate(row['banks']):
                request = ref.request2[bank]
                self.check(int(request is not None), actual['write']['valid'], phase='public-t2-write-request', bank=bank)
                if request is not None:
                    self.check(request, actual['write']['bits'], phase='full-independently-derived-write', bank=bank)
                dirty = [slot for slot in ref.buffers[bank].slots if slot['dirty']]
                self.check(int(bool(dirty)), actual['drain']['valid'], phase='dirty-entry-drain-valid', bank=bank)
                if actual['read_pressure']:
                    self.check(0, actual['drain']['ready'], phase='real-read-pressure-blocks-drain', bank=bank)
                fire = int(bool(dirty) and actual['drain']['ready'])
                self.check(fire, counter['writes'][bank]['valid'], phase='drain-response-valid', bank=bank)
                if fire:
                    payload = dirty[0]['payload']
                    slot = next(i for i, state in enumerate(ref.buffers[bank].slots) if state['dirty'])
                    self.check(payload, actual['drain']['bits'], phase='full-oldest-dirty-payload', bank=bank, slot=slot)
                    self.check((payload['set_index'], payload['way'], payload['need_reset']),
                        tuple(counter['writes'][bank][name] for name in ('set_index', 'way', 'reset_counter')),
                        phase='drain-response-identity', bank=bank)
        drains, actions = ref.advance(reset=counter['reset'], accepted=accepted,
                                     ready=[port['drain']['ready'] for port in row['banks']])
        self.pending_drains, self.pending_actions = drains, actions

    def summary(self):
        self.raise_failure()
        self.check(0, len(self.planned), phase='every-submitted-public-pulse-observed')
        return dict(cycles=len(self.records), public_feedback=len(self.accepted_events),
            shadow_slot_comparisons=max(0, len(self.records) - 1) * 16,
            counter_comparisons=max(0, len(self.records) - 1) * 1024,
            confirmed_drains=len(self.drains), confirmed_actions=len(self.actions),
            checks=asdict(self.scoreboard.status))
