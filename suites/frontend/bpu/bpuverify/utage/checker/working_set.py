"""Actual source/admission/state/consumer closure for logical working sets."""
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256

from toffee import CheckContext, Scoreboard, ScoreboardMode, TransferState

from bpuverify.utage.checker.source_ownership import actual_fields
from bpuverify.utage.model.working_set import (PC, POSITION, PHASES, RULES, WorkingSetReference, expected)
from bpuverify.utage.transaction.types import UtageTraining
from bpuverify.utage.checker.checking import UtageUsefulChecker


class WorkingSetChecks:
    def __init__(self, program, coverage):
        self.program, self.coverage = program, coverage
        self.reference = WorkingSetReference(program)
        self.board = Scoreboard('utage.working-set')
        self.originals, self.completed, self.witnesses = [], set(), {}
        self.phase_receipts = {}
        self.source_payloads = {}

    def check(self, wanted, actual, point):
        self.board.check(expected=wanted, actual=actual, context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT, request=dict(point=point, size=self.program.size, mode=self.program.mode,
                phase=self.reference.phase, live_histories=len(self.reference.states),
                original_sources=len(self.reference.sources), consumed_sources=len(self.reference.consumed))))

    def reach(self, rule, **witness):
        self.coverage.record('reached', rule, **witness)
        self.witnesses[rule] = witness

    def responses(self, histories, transfers, predictions, base, states, *, table=1, position=POSITION,
                  after=None):
        self.check((len(histories), len(histories)), (len(transfers), len(predictions)),
                   'each declared history has exactly one actual response')
        self.check(True, all(transfer.state is TransferState.COMPLETED for transfer in transfers),
                   'all query transfers actually completed')
        self.check(True, all(a.accepted_event.tick < b.accepted_event.tick < a.completed_event.tick
                            for a, b in zip(transfers, transfers[1:])), 'actual consecutive queries overlap')
        for history, transfer, prediction in zip(histories, transfers, predictions, strict=True):
            request = transfer.request
            self.check((PC, position, base, history, PC, history),
                (request.pc, request.position, request.base_taken, request.folded_history,
                 request.read_pc, request.read_history), 'query keeps its complete logical owner')
            if after is not None:
                self.check(True, transfer.accepted_event.tick > after, 'consumer is fresh after learning drains')
            wanted = expected(history, base, states.get(history), table=table, position=position)
            self.check(wanted, actual_fields(prediction, wanted), f'complete independent prediction and metadata: history{history}')
            self.originals.append((prediction, deepcopy(prediction.meta)))

    def capture(self, phase, transfers, predictions):
        histories = self.program.order(phase)
        self.responses(histories, transfers, predictions, self.program.base(phase), self.reference.states)
        owners = tuple(transfer.accepted_event.tick for transfer in transfers)
        for owner, history, prediction in zip(owners, histories, predictions, strict=True):
            self.reference.capture(owner, phase, history)
            state = self.reference.states.get(history)
            predicted = self.program.base(phase) if state is None else state.taken
            transaction = UtageTraining(PC, POSITION, self.program.actual(phase), deepcopy(prediction.meta),
                                       mispredict=int(predicted != self.program.actual(phase)))
            self.source_payloads[owner] = UtageUsefulChecker._payload(transaction)
        self.reach('actual-query-overlap', queries=len(histories),
                   first_tick=owners[0], last_tick=owners[-1])
        self.completed.add('actual-query-overlap')
        return owners

    def admissions(self, phase, owners, receipts, payloads, *, cycle_ticks):
        self.reference.preview(phase, owners)
        self.check(len(owners), len(receipts), 'all original feedback actually accepted')
        self.check(tuple(self.source_payloads[owner] for owner in owners), tuple(payloads),
                   'feedback proposal derives from its own complete immutable original source')
        self.check(tuple(payloads), tuple(payload for _, payload in receipts),
                   'original payloads accepted exactly once in declared order')
        ticks = tuple(tick for tick, _ in receipts)
        self.check(True, all(tick > owner for tick, owner in zip(ticks, owners, strict=True)),
                   'feedback follows its own original query')
        self.check(True, all((b - a == cycle_ticks if self.program.mode == 'adjacent' else b - a > cycle_ticks)
                            for a, b in zip(ticks, ticks[1:])), 'actual feedback cadence')
        self.phase_receipts[phase] = ticks
        witness = dict(accepted=len(ticks), first_tick=ticks[0], last_tick=ticks[-1])
        self.reach(phase, **witness)
        self.reach('actual-feedback-cadence', **witness)

    def verified_phase(self, phase, owners, actual_values, consumers, *, confirmation_tick):
        states = self.reference.preview(phase, owners)
        self.check(True, phase in self.phase_receipts, 'no learning credit without actual complete inputs')
        self.check(True, confirmation_tick > self.phase_receipts[phase][-1],
                   'learning confirmation follows the final actual feedback acceptance')
        self.check(self.reference.values(states), tuple(actual_values),
                   'all1024 protection cells, including untrained identities, retain independent state')
        histories, transfers, predictions = consumers
        self.check(self.program.histories, tuple(histories), 'every live identity has a fresh consumer')
        self.responses(histories, transfers, predictions, 0, states, after=confirmation_tick)
        self.reference.commit(phase, owners)
        self.completed.update((phase, 'actual-feedback-cadence'))
        self.witnesses[phase].update(compared_protection_cells=1024, consumers=len(histories),
            confirmation_tick=confirmation_tick, final_protection_sha256=sha256(bytes(actual_values)).hexdigest())

    def finish(self, actual_values, consumers, *, confirmation_tick):
        self.check(len(PHASES), self.reference.phase, 'all logical learning phases complete')
        self.check(self.reference.values(), tuple(actual_values), 'late complete protection remains unchanged')
        histories, transfers, predictions = consumers
        self.check(self.program.histories, tuple(histories), 'late consumers cover every live logical identity')
        self.responses(histories, transfers, predictions, 0, self.reference.states, after=confirmation_tick)
        self.reach('late-retained-consumers', consumers=len(histories), compared_protection_cells=1024)
        self.completed.add('late-retained-consumers')
        self.check(tuple(frozen for _, frozen in self.originals), tuple(p.meta for p, _ in self.originals),
                   'all genuine original prediction snapshots remain immutable')
        self.reach('immutable-original-sources', predictions=len(self.originals))
        self.completed.add('immutable-original-sources')
        self.check(set(RULES), self.completed, 'all declared working-set obligations completed')
        for rule in RULES:
            self.coverage.record('checked', rule, **self.witnesses[rule])

    def summary(self):
        """One bounded lifetime receipt, never a per-cycle/source trace."""
        return dict(program=asdict(self.program), logical_histories=len(self.program.histories),
            selected_histories=len(self.program.selected), completed_phases=self.reference.phase,
            accepted_learning_feedback=sum(len(ticks) for ticks in self.phase_receipts.values()),
            consumed_original_sources=len(self.reference.consumed),
            actual_prediction_snapshots=len(self.originals), completed_obligations=sorted(self.completed),
            obligations=deepcopy(self.witnesses), checks=asdict(self.board.status))
