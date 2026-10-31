"""Online pipeline reference comparison through toffee Scoreboard."""
from collections import deque
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256

from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from suites.frontend.bpu.utage.transaction.types import UtageTraining
from suites.frontend.bpu.utage.model.model import UtageUsefulReference


class UtageUsefulChecker:
    def __init__(self, *, mode, allocation_coverage=None, update_coverage=None, scope=None):
        if mode not in ('serial', 'adjacent'):
            raise ValueError('feedback mode must be serial or adjacent')
        self.mode = mode
        self.scope = deepcopy(scope)
        self.reference = UtageUsefulReference()
        self.scoreboard = Scoreboard('utage.useful_cells')
        self.allocation_coverage = allocation_coverage
        self.update_coverage = update_coverage
        self._planned = deque()
        self._accepted = {}
        self._sequence = 0
        self._actual = [0] * 1024
        self._last_event = None
        self._last_phase = 'initial'
        self.records = []
        self.route_bins = set()
        self.accepted_count = 0
        self.cell_comparisons = 0
        self._failure = None

    def raise_failure(self):
        if self._failure is not None:
            raise self._failure

    @property
    def accepted_feedback(self):
        """Validated actual public payload receipts; callers cannot mutate them."""
        return tuple((tick, deepcopy(entry['actual_payload'])) for tick, entry in self._accepted.items())

    def capture(self, observation):
        """Preserve the first error for the next foreground check/context exit."""
        if self._failure is None:
            try:
                self.observe(observation)
            except Exception as error:
                self._failure = error

    @staticmethod
    def _payload(transaction):
        if not isinstance(transaction, UtageTraining):
            raise TypeError('useful checker plans UtageTraining transactions')
        return dict(start_pc=transaction.pc, meta=deepcopy(transaction.meta),
            branch=dict(taken=transaction.actual_taken, position=transaction.position,
                branch_type=transaction.branch_type))

    def plan(self, transactions, *, phase):
        self.raise_failure()
        if not isinstance(phase, str) or not phase:
            raise ValueError('feedback phase must be a nonempty string')
        transactions = tuple(transactions)
        if not transactions:
            raise ValueError('feedback plan cannot be empty')
        # Validate the complete burst before making any part of it pending.
        payloads = tuple(self.reference.validate(self._payload(transaction)) for transaction in transactions)
        for payload in payloads:
            self._sequence += 1
            self._planned.append(dict(sequence_id=self._sequence, phase=phase, payload=payload))
        self._last_phase = phase

    def _context(self, event, accepted=None):
        entry = self._accepted.get(event.tick - 6) or self._accepted.get(event.tick - 4) or accepted
        return CheckContext(scoreboard=self.scoreboard.name, mode=ScoreboardMode.DIRECT,
            sequence_id=None if entry is None else entry['sequence_id'],
            request=dict(scope=self.scope, phase=self._last_phase if entry is None else entry['phase'], cadence=self.mode),
            accepted_event=None if entry is None else entry['event'], observed_event=event)

    def observe(self, observation):
        row, event = observation.value, observation.event
        self._last_event = event
        accepted = None
        if row['public']['valid']:
            preliminary = self._context(event)
            self.scoreboard.check(expected=True, actual=bool(self._planned), context=preliminary)
            accepted = self._planned.popleft()
            accepted['event'] = event
            self.scoreboard.check(expected=accepted['payload'], actual=row['public']['bits'],
                context=self._context(event, accepted))
            accepted['actual_payload'] = deepcopy(row['public']['bits'])
            self._accepted[event.tick] = accepted
            self.accepted_count += 1
        context = self._context(event, accepted)
        if self.reference.last_tick is not None:
            self.scoreboard.check(expected=self.reference.last_tick + self.reference.cycle_ticks,
                actual=event.tick, context=context)
        self.scoreboard.check(expected=dict(reset=0, enable=1),
            actual=dict(reset=row['reset'], enable=row['enable']), context=context)
        expected = self.reference.advance(event.tick, None if accepted is None else accepted['payload'])
        for table, actual in enumerate(row['tables']):
            control = None if expected.controls is None else expected.controls[table]
            if control is None:
                wanted = dict(allocate=0, update=0, age=0)
            else:
                wanted = dict(index=control.index, allocate=control.allocate, update=control.update, age=0)
                if control.update:
                    wanted.update(useful_valid=control.useful_valid, increase=control.increase)
            self.scoreboard.check(expected=wanted, actual={field: actual[field] for field in wanted}, context=context)
        sampled = 'all_cells_sha256' in row
        self.scoreboard.check(expected=expected.sampled, actual=sampled, context=context)
        if sampled:
            for address, old, new in row['changes']:
                if type(address) is not int or address not in range(1024) or new not in range(4):
                    raise ValueError(f'invalid useful delta at tick{event.tick}: {(address, old, new)!r}')
                self.scoreboard.check(expected=self._actual[address], actual=old, context=context)
                self._actual[address] = new
            self.scoreboard.check(expected=sha256(bytes(self._actual)).hexdigest(), actual=row['all_cells_sha256'], context=context)
            self.scoreboard.check(expected=tuple(self.reference.values), actual=tuple(self._actual), context=context)
            self.cell_comparisons += 1024
        for effect in expected.effects:
            self.route_bins.add((effect.table, effect.index, effect.role))
            if effect.role == 'allocate':
                if self.allocation_coverage is not None:
                    self.allocation_coverage.sample(dict(mode=self.mode, table=effect.table, index=effect.index))
            elif self.update_coverage is not None:
                self.update_coverage.sample(dict(mode=self.mode, table=effect.table, index=effect.index, role=effect.role))
        self.records.append(dict(tick=event.tick, **row))

    def finish_phase(self):
        self.raise_failure()
        if self._last_event is None:
            raise RuntimeError('no useful observations received')
        context = self._context(self._last_event)
        self.scoreboard.check(expected=0, actual=len(self._planned), context=context)
        self.scoreboard.check(expected=0, actual=self.reference.pending, context=context)
        self.scoreboard.check(expected=tuple(self.reference.values), actual=tuple(self._actual), context=context)

    def summary(self):
        self.finish_phase()
        return dict(cycles=len(self.records), accepted=self.accepted_count,
            cell_comparisons=self.cell_comparisons, route_bins=sorted(self.route_bins),
            final_expected=list(self.reference.values), final_actual=list(self._actual),
            checks=asdict(self.scoreboard.status))
