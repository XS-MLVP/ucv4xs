"""Do not retroactively judge an old prediction using a new table direction."""
from copy import deepcopy
from toffee import CheckContext, Scoreboard, ScoreboardMode, TransferState
from suites.frontend.bpu.utage.checker.selective_protection import Checks as ProtectionChecks
from suites.frontend.bpu.utage.checker.read_lifetime import values
from suites.frontend.bpu.utage.model.semantic import Context, index_view, tag_view
from suites.frontend.bpu.utage.model.delayed_protection import PC, READ_PCS, RULES


class Checks(ProtectionChecks):
    def __init__(self, program):
        super().__init__(program)
        self.board = Scoreboard('utage.original-correctness-delayed-protection')
        self.origins, self.late, self.consumers = {}, {}, {}
        self.read_entries = []
        self.closed = False

    def check(self, expected, actual, point):
        self.board.check(expected=expected, actual=actual, context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT, request=dict(program=self.program.state(), point=point,
                sent=getattr(self, 'sent', ()), compared=getattr(self, 'compared', 0),
                late=getattr(self, 'late', {}))))

    def occurrence(self, owner, history, transfer, source, monitor):
        self.check(TransferState.COMPLETED, transfer.state, 'original response has actual framework completion')
        accepted, completed = transfer.accepted_event.tick, transfer.completed_event.tick
        self.check(accepted+4, completed, 'complete original response follows its declared pipeline protocol')
        read, response = monitor.at(accepted+2), monitor.at(completed)
        self.check((True, READ_PCS[owner], Context(), self.program.read_indices(owner)),
            (bool(read['events'].select), read['events'].read_pc, index_view(read['events'].read_context), read['read'].indices),
            'source owns its genuine original complete read identity')
        self.check((PC, tag_view(Context.from_recent(history))), (response['frame'].pc, tag_view(response['frame'].context)),
            'source owns its matching PC/history, not a reconstructed old metadata packet')
        self.check(True, response['frame'].read.entries is read['read'].entries, 'response retains its exact original read tuple')
        self.check(True, all(read['read'].entries is not old for old in self.read_entries), 'equal-valued queries are distinct occurrences')
        self.read_entries.append(read['read'].entries)
        return dict(accepted=accepted, read=read['tick'], completed=completed)

    def owned_source(self, step, transfer, source, monitor):
        key = step.phase, step.owner
        self.check(False, key in self.origins, 'one actual original per feedback role')
        ordinal = self.source(step, source)
        witness = self.occurrence(step.owner, step.history, transfer, source, monitor)
        self.origins[key] = dict(ordinal=ordinal, source=source, **witness)
        return ordinal

    def before_late(self, step, actual_cell, latest_write, tick, protection):
        self.check(True, step in self.program.steps and step.phase.startswith('late'), 'only a declared delayed original is evaluated')
        self.check(True, self.compared <= step.ordinal and all(prior.owner != step.owner
            for prior in self.program.steps[self.compared:step.ordinal]),
            'every earlier learning for this identity is compared; another queued identity cannot rebase its current value')
        original = self.origins[step.phase, step.owner]
        self.check(step.expected, values(original['source']), 'old source still carries its original direction and confidence')
        self.check(step.current_cell, actual_cell, 'actual current retained identity and confidence precede the delayed send')
        self.check(step.current_cell, latest_write['new_cell'], 'current retained version is the most recent compared actual learning')
        self.check(step.before.taken != step.current.taken, True, 'original prediction and current direction must really disagree')
        self.check(self.program.protection_after(self.compared), protection, 'complete pre-burst protection prestate is independently declared')
        flip = next(row for prior, row in zip(self.program.steps, self._records, strict=False)
            if prior.phase == 'flip' and prior.owner == step.owner)
        if step.phase in getattr(self.program, 'initial_roles', ('late-correct', 'flip')):
            self.check(True, original['completed'] < flip['tick'], 'correct old prediction was completed before the other feedback flipped direction')
        else:
            restoration = next(row for prior, row in zip(self.program.steps, self._records, strict=False)
                if prior.phase == 'late-correct' and prior.owner == step.owner)
            self.check(True, flip['tick'] < original['completed'] < restoration['tick'],
                'wrong old prediction belongs to the opposite-direction interval, not a fresh current query')
        self.check(True, tick > original['completed'], 'delayed input follows its own original completion')
        self.late[step.phase, step.owner] = dict(owner=step.owner, phase=step.phase,
            original=deepcopy(original | {'source':None}), original_direction=step.before.taken,
            current=deepcopy(actual_cell), current_direction=step.current.taken,
            protection_before=step.current.useful, observed_before_tick=tick,
            expected_after=(step.after.counter, step.after.useful), actual_effect_tick=None)

    def prefix(self, monitor, count):
        super().prefix(monitor, count)
        self._records = monitor.records
        for step, row in zip(self.program.steps[:count], monitor.records[:count], strict=True):
            key = step.phase, step.owner
            if not step.phase.startswith('late') or key not in self.late: continue
            witness = self.late[key]
            self.check(True, witness['observed_before_tick'] < monitor.public[step.ordinal]['tick'] < row['tick'],
                'compared current prestate, actual original acceptance and actual new learning are distinct ordered facts')
            witness['actual_effect_tick'] = row['tick']

    def consume(self, phase, owner, transfer, source, monitor, *, existing_source=False):
        self.check(False, (phase, owner) in self.consumers, 'every phase/history consumer compares once')
        if phase == 'final-long':
            wanted, history = (1, 1, 3 if owner == 0 else 4, owner), 0
        else:
            history = 64
            step = self.program.step('late-wrong' if phase == 'final-short' else phase, owner)
            wanted = 1, 0, step.after.counter, step.after.taken
        self.prediction(owner, history, source, wanted)
        if existing_source:
            witness = {k:v for k,v in self.origins['late-wrong', owner].items() if k != 'source'}
        else:
            witness = self.occurrence(owner, history, transfer, source, monitor)
            self.remember(source)
        effect = next(row for prior, row in zip(self.program.steps, monitor.records, strict=False)
            if prior.phase == ('flip' if phase == 'final-long' else 'late-wrong' if phase == 'final-short' else phase)
            and prior.owner == owner)
        self.check(True, witness['accepted'] > effect['tick'], 'consumer must be a fresh query after its actual learned result')
        self.consumers[phase, owner] = dict(expected=wanted, actual=values(source), **witness)

    def finish(self, monitor):
        self.check(False, self.closed, 'one complete original-correctness cohort')
        super().finish(monitor)
        self.check({(step.phase, step.owner) for step in self.program.steps},
            set(self.origins), 'all declared actual original sources teach once')
        self.check({(step.phase, step.owner) for step in self.program.steps if step.phase.startswith('late')}, set(self.late),
            'both originally correct and wrong delayed predictions are distinguished in both directions')
        self.check(True, all(row['actual_effect_tick'] is not None for row in self.late.values()), 'each delayed source really learns')
        self.check({(step.phase, step.owner) for step in self.program.steps if step.phase != 'allocate'} |
            {(phase, owner) for phase in ('final-short', 'final-long') for owner in (0, 1)},
            set(self.consumers), 'all declared fresh semantic consumers mandatory')
        self.check(sum(len(group)>1 for group in self.program.groups), len(self.cadences), 'all multi-input groups have their actual cadence compared')
        self.closed = True

    def snapshot(self):
        return deepcopy(dict(program=self.program.label, closed=self.closed, sent=self.sent, compared=self.compared,
            originals={phase+'.'+str(owner):{k:v for k,v in row.items() if k != 'source'}
                for (phase, owner), row in self.origins.items()},
            delayed={phase+'.'+str(owner):row for (phase, owner), row in self.late.items()},
            consumers={phase+'.'+str(owner):row for (phase, owner), row in self.consumers.items()},
            actual_cadences=self.cadences, immutable_original_count=len(self.originals),
            full_FTQ_source_eligibility_proved=False))
