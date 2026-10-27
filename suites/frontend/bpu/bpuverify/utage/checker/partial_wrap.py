"""bpuverify.utage.checker.partial_wrap components."""

from collections import deque
from copy import deepcopy
from dataclasses import asdict
from toffee import CheckContext
from toffee import Scoreboard
from toffee import ScoreboardMode
from bpuverify.utage.agent.main import UtageAgent
from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.model.partial_wrap import UtagePartialWrapReference


class UtagePartialWrapChecker:
    def __init__(self, cells, *, bank, mode):
        if type(bank) is not int or bank not in range(4) or mode not in ('serial', 'adjacent'):
            raise ValueError('partial wrap requires bank0..3 and serial/adjacent cadence')
        self.reference = UtagePartialWrapReference(cells)
        self.bank, self.mode = bank, mode
        self.scoreboard = Scoreboard('utage.partial_shadow_wrap')
        self.planned = deque()
        self.accepted = []
        self.last_event = None
        self.witness_ticks = []
        self.cycles = 0
        self._failure = None

    def raise_failure(self):
        if self._failure is not None:
            raise self._failure

    def capture(self, observation):
        """Hand the first comparison failure to the foreground, not the pump.

        The next foreground check or context exit raises the original error;
        cleanup therefore does not report the same failure as a second ERROR.
        """
        if self._failure is None:
            try:
                self.observe(observation)
            except Exception as error:
                self._failure = error

    def plan(self, transactions):
        self.raise_failure()
        transactions = tuple(transactions)
        if len(transactions) != 2 or self.planned or self.accepted:
            raise ValueError('plan exactly one two-write partial-wrap burst')
        if any(not isinstance(transaction, UtageTraining) for transaction in transactions):
            raise TypeError('partial wrap plans UtageTraining transactions')
        payloads = tuple(self.reference.validate(deepcopy(UtageAgent.encode_training(transaction)))
            for transaction in transactions)
        self.planned.extend(payloads)

    def check(self, expected, actual, *, point, event=None):
        self.raise_failure()
        event = self.last_event if event is None else event
        entry = next((entry for entry in reversed(self.accepted)
            if event is not None and entry.tick + 6 <= event.tick), None)
        self.scoreboard.check(expected=expected, actual=actual,
            context=CheckContext(scoreboard=self.scoreboard.name, mode=ScoreboardMode.DIRECT,
                sequence_id=None if entry is None else self.accepted.index(entry) + 1,
                request=dict(bank=self.bank, cadence=self.mode, point=point),
                accepted_event=entry, observed_event=event))

    def observe(self, observation):
        row, event = observation.value, observation.event
        self.last_event = event
        payload = None
        if row['public']['valid']:
            self.check(True, bool(self.planned), point='planned public acceptance')
            payload = self.planned.popleft()
            self.check(payload, row['public']['bits'], point='complete accepted feedback')
            self.accepted.append(event)
        # a1_chosenFirstMask is registered with a1_entryHit and therefore
        # uses the preceding cycle's priority mask, before this cycle's write.
        prediction_mask = self.reference.mask
        self.reference.advance(event.tick, payload)
        self.check(tuple(self.reference.cells), tuple(row['cells']), point='all retained and updated shadow cells')
        self.check((self.reference.enq, self.reference.mask), (row['enq'], row['mask']),
            point='three-cycle enqueue pointer and priority mask')
        hits = tuple(row['hits'])
        self.check(True, len(hits) == 8 and all(bit in (0, 1) for bit in hits), point='hit-vector shape')
        hit_bits = sum(bit << slot for slot, bit in enumerate(hits))
        preferred = hit_bits & prediction_mask
        if hit_bits:
            # With no hit, the priority encoder's raw default is not valid.
            self.check(preferred, row['chosen_first'], point='registered first priority-group hit mask')
            selected = (preferred or hit_bits).bit_length() - 1
            cell = self.reference.cells[selected]
            self.check(dict(hit=1, valid=cell['data_valid'], tag=cell['tag'],
                position=cell['position'], counter=cell['counter']), row['response'],
                point='complete selected shadow response')
        if hits == (0, 0, 1, 0, 0, 0, 0, 0) and preferred == 0:
            self.check((2, 3), (self.reference.enq, self.reference.mask), point='old slot2 after partial wrap')
            self.witness_ticks.append(event.tick)
        self.cycles += 1

    def finish(self):
        self.check((0, 0, 2), (len(self.planned), self.reference.pending, len(self.accepted)),
            point='complete feedback and pipeline drain')
        ticks = [event.tick for event in self.accepted]
        self.check(True, ticks[1] - ticks[0] == 2 if self.mode == 'adjacent' else ticks[1] - ticks[0] > 2,
            point='actual requested feedback cadence')
        self.check(True, bool(self.witness_ticks), point='second-group old-slot2 payload witness')
        return dict(cycles=self.cycles, accepted_ticks=ticks, witness_ticks=self.witness_ticks,
            final_cells=self.reference.cells, checks=asdict(self.scoreboard.status))
