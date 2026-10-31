"""Protocol and consumer closure; reuse existing independent semantic states."""
from dataclasses import asdict

from toffee import CheckContext, Scoreboard, ScoreboardMode

from suites.frontend.bpu.utage.coverage.learning_retention import RULES
from suites.frontend.bpu.utage.model.semantic import Context, indices
from suites.frontend.bpu.utage.model.working_set import PC, POSITION


# Architectural retained-version capacity; not a delay or address sweep.
RECENT_VERSION_CAPACITY = 8


def cohorts(program):
    if len(program.histories) < 2 * RECENT_VERSION_CAPACITY:
        raise ValueError('need independent retained and turnover cohorts')
    retained = tuple(reversed(program.histories[-RECENT_VERSION_CAPACITY:]))
    turnover = program.histories[:RECENT_VERSION_CAPACITY]
    if set(retained) & set(turnover):
        raise ValueError('turnover feedback cannot relearn a retained identity')
    return retained, turnover


class LearningRetentionChecks:
    def __init__(self, base, coverage):
        self.base, self.coverage = base, coverage
        self.stage = 'not-started'
        self.retained, self.turnover = cohorts(base.program)
        self.states = {}
        self.feedback = []
        self.consumers = []
        self.eviction = None
        self.witnesses = {}
        self.finalized = False
        self.board = Scoreboard('utage.learning-retention')

    def check(self, expected, actual, point):
        self.board.check(expected=expected, actual=actual, context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT, request=dict(point=point, stage=self.stage, mode=self.base.program.mode,
                feedback=len(self.feedback), consumers=len(self.consumers), departure=self.eviction)))

    def mark(self, rule, **witness):
        self.check(False, rule in self.witnesses, 'one reached witness per declared lifetime obligation')
        self.coverage.record('reached', rule, **witness)
        self.witnesses[rule] = witness

    def initialize(self):
        self.check({}, self.states, 'independent initial state is installed only once')
        self.check(1, self.base.checks.reference.phase, 'normal initial admissions completed')
        # The reference owns these states, derived from original input events.
        # No actual counter, cache payload or prediction seeds expected state.
        self.states = dict(self.base.checks.reference.states)

    def predictions(self, histories, transfers, predictions):
        self.base.checks.responses(histories, transfers, predictions, 0, self.states)

    def accepted_learning(self, histories, transfers, receipts, payloads, *, label, actual_values):
        self.stage = label
        expected_histories = self.retained if label == 'retained-learning' else self.turnover
        self.check(True, label in ('retained-learning', 'unrelated-learning'), 'declared semantic learning phase')
        self.check(set(self.base.program.histories), set(self.states), 'all declared initial learning identities exist')
        self.check(label == 'unrelated-learning', bool(self.consumers),
                   'unrelated learning follows the immediate consumer, not an unobserved initial update')
        self.check(expected_histories, tuple(histories), 'feedback belongs exactly to its original cohort')
        self.check(False, any(row['stage'] == label for row in self.feedback), 'each cohort learns only once')
        self.check((len(histories), len(histories)), (len(transfers), len(receipts)),
                   'all original requests and intended feedback actually accepted')
        self.check(tuple(payloads), tuple(payload for _, payload in receipts), 'actual inputs equal owned original payloads')
        self.check(tuple((PC, POSITION, history) for history in histories),
            tuple((transfer.request.pc, transfer.request.position, transfer.request.folded_history) for transfer in transfers),
            'actual original requests retain their declared PC, branch and history')
        self.check(len(transfers), len({transfer.accepted_event.tick for transfer in transfers}),
                   'distinct original queries cannot share one acceptance')
        ticks = tuple(tick for tick, _ in receipts)
        self.check(True, all(tick > transfer.completed_event.tick for tick, transfer in
            zip(ticks, transfers, strict=True)), 'feedback follows its own completed original prediction')
        cycle = self.base.monitor.reference.cycle_ticks
        self.check(True, all(b - a == cycle if self.base.program.mode == 'adjacent' else b - a > cycle
            for a, b in zip(ticks, ticks[1:])), 'actual driver cadence')
        for history, transfer, tick in zip(histories, transfers, ticks, strict=True):
            previous = self.states[history]
            learned = previous.feedback(predicted=previous.taken, base=0, actual=1)
            self.states[history] = learned
            self.feedback.append(dict(stage=label, history=history,
                query_tick=transfer.accepted_event.tick, completed_tick=transfer.completed_event.tick,
                actual_feedback_tick=tick, before=asdict(previous), after=asdict(learned)))
        self.mark('owned-feedback' if label == 'retained-learning' else 'unrelated-turnover',
                  first_tick=ticks[0], last_tick=ticks[-1], accepted=len(ticks))
        self.check(tuple(self.base.checks.reference.values(self.states)), tuple(actual_values),
                   'all1024 protection cells including unrelated identities')

    def consumed(self, histories, transfers, predictions, *, label):
        self.stage = label
        wanted_label = 'immediate-bypass-consumers' if not self.consumers else 'fresh-after-turnover-consumers'
        self.check(wanted_label, label, 'immediate and post-departure consumers occur once in order')
        self.check(self.retained, tuple(histories), 'every retained identity has its own consumer')
        self.check(True, 'owned-feedback' in self.witnesses, 'consumer cannot replace absent actual owned learning')
        after = max(record['actual_feedback_tick'] for record in self.feedback)
        if label == 'fresh-after-turnover-consumers':
            self.check(True, self.eviction is not None, 'late consumption requires observed complete cache departure')
            after = max(after, self.eviction['tick'])
        self.base.checks.responses(histories, transfers, predictions, 0, self.states, after=after)
        self.consumers.append(dict(stage=label, histories=tuple(histories),
            accepted_ticks=tuple(transfer.accepted_event.tick for transfer in transfers),
            completed_ticks=tuple(transfer.completed_event.tick for transfer in transfers),
            expected_counters=tuple(self.states[history].counter for history in histories)))
        self.mark('immediate-consumption' if label == 'immediate-bypass-consumers' else 'late-consumption',
                  first_tick=transfers[0].accepted_event.tick, last_tick=transfers[-1].completed_event.tick,
                  identities=len(histories))

    def confirm_turnover(self, observation):
        self.stage = 'confirmed-full-turnover-without-own-relearning'
        self.check(True, observation is not None, 'read-only shadow witness exists')
        self.check(True, bool(self.consumers), 'learning was visible before its storage departed')
        owners = {indices(PC, Context.from_recent(history))[1] for history in self.retained}
        resident = {cell['index'] for cell in observation.value['cells'] if cell['valid']}
        self.check(set(), owners & resident, 'retained identities are absent from all recent versions')
        self.check(2 * RECENT_VERSION_CAPACITY, len(self.feedback), 'one owned feedback per cohort identity')
        self.check(set(self.retained), {row['history'] for row in self.feedback if row['stage'] == 'retained-learning'},
                   'original learning belongs exactly to retained identities')
        self.check(set(self.turnover), {row['history'] for row in self.feedback if row['stage'] == 'unrelated-learning'},
                   'turnover learning belongs only to unrelated identities')
        self.check(True, observation.event.tick > max(row['actual_feedback_tick'] for row in self.feedback),
                   'cache departure is observed after actual other-identity feedback')
        self.eviction = dict(tick=observation.event.tick, retained_owners=sorted(owners),
            resident_owners=sorted(resident), all_retained_absent=True,
            no_retained_feedback_during_turnover=True)
        self.mark('left-recent-storage', **self.eviction)

    def finish(self):
        self.stage = 'finished'
        self.check(False, self.finalized, 'a complete lifetime publishes checked credit only once')
        self.check(0, self.board.status.failed, 'an earlier mismatch cannot gain completed credit')
        self.check(True, self.eviction is not None, 'no persistence claim without full cache departure')
        self.check(('immediate-bypass-consumers', 'fresh-after-turnover-consumers'),
                   tuple(row['stage'] for row in self.consumers), 'both observation boundaries completed')
        self.check(tuple(frozen for _, frozen in self.base.checks.originals),
            tuple(prediction.meta for prediction, _ in self.base.checks.originals),
            'every retained original metadata snapshot is immutable')
        self.base.agent.reference.raise_failure()
        self.mark('immutable-originals', predictions=len(self.base.checks.originals))
        self.check(set(RULES), set(self.witnesses), 'all semantic obligations actually completed')
        for rule in RULES:
            self.coverage.record('checked', rule, **self.witnesses[rule])
        self.finalized = True

    def summary(self):
        return dict(stage=self.stage, mode=self.base.program.mode, initial_histories=len(self.base.program.histories),
            retained=self.retained, turnover=self.turnover, actual_feedback=self.feedback,
            consumers=self.consumers, confirmed_departure=self.eviction,
            actual_all_cell_comparisons=self.base.monitor.cell_comparisons,
            original_snapshots=len(self.base.checks.originals), reached=tuple(self.witnesses),
            finalized=self.finalized, checks=self.board.status.checked,
            oracle='existing independent semantic/working_set/ProtectionState; no new DUT model')
