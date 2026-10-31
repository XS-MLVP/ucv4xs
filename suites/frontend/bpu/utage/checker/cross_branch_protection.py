"""Different matching branches retain their own original reward qualification."""
from copy import deepcopy
from toffee import Scoreboard, TransferState
from suites.frontend.bpu.utage.checker.delayed_protection import Checks as DelayedChecks
from suites.frontend.bpu.utage.checker.selective_protection import Checks as VersionChecks
from suites.frontend.bpu.utage.checker.read_lifetime import values
from suites.frontend.bpu.utage.model.semantic import Context, index_view, tag_view
from suites.frontend.bpu.utage.model.cross_branch_protection import POSITION


class Checks(DelayedChecks):
    def __init__(self, program):
        super().__init__(program)
        self.board = Scoreboard('utage.cross-branch-original-protection')

    def occurrence(self, owner, history, transfer, source, monitor):
        self.check(TransferState.COMPLETED, transfer.state, 'original response really completed')
        accepted, completed = transfer.accepted_event.tick, transfer.completed_event.tick
        self.check(accepted+4, completed, 'actual original protocol completion')
        read, response = monitor.at(accepted+2), monitor.at(completed)
        self.check((True, self.program.read_pc(owner), Context(), self.program.read_indices(owner)),
            (bool(read['events'].select), read['events'].read_pc, index_view(read['events'].read_context), read['read'].indices),
            'original complete index ancestor belongs to this branch')
        self.check((self.program.pc(owner), tag_view(Context.from_recent(history))),
            (response['frame'].pc, tag_view(response['frame'].context)), 'matching PC is this real branch, not one shared matching PC')
        self.check(True, response['frame'].read.entries is read['read'].entries, 'original read tuple survives to its own completed response')
        self.check(True, all(read['read'].entries is not old for old in self.read_entries), 'all original occurrences are distinct even for equal values')
        self.read_entries.append(read['read'].entries)
        return dict(accepted=accepted, read=read['tick'], completed=completed,
            match_pc=self.program.pc(owner), read_pc=self.program.read_pc(owner))

    def owned_feedback(self, step, ordinal, transaction):
        self.check(len(self.sent), step.ordinal, 'declared cross-branch return order cannot be skipped')
        predicted = step.base if step.before is None else step.before.taken
        self.check((step.pc, POSITION, step.actual, int(predicted != step.actual), step.indices),
            (transaction.pc, transaction.position, transaction.actual_taken, transaction.mispredict, tuple(transaction.meta['readIndex'])),
            'complete feedback retains original matching branch, outcome and read identity')
        self.original_feedback(ordinal, transaction)
        self.sent.append(step.ordinal)

    def cadence(self, group, public):
        self.check(len(group), len(public), 'all four complete feedbacks have real admissions')
        deltas = tuple(b['tick']-a['tick'] for a, b in zip(public, public[1:]))
        self.check(True, all(delta == 2 if self.program.mode == 'adjacent' else delta > 2 for delta in deltas),
            'every adjacent or serial admission gap is checked, not just the first pair')
        self.cadences.append(dict(phase=group[0].phase, owners=[s.owner for s in group], deltas=deltas, mode=self.program.mode))

    def consume(self, phase, owner, transfer, source, monitor, *, existing_source=False):
        self.check(False, (phase, owner) in self.consumers, 'one distinct checked consumer for this phase and real branch')
        history = 0 if phase == 'final-long' else 64
        if phase == 'final-long':
            wanted = 1, 1, 3 if self.program.taken(owner) else 4, 1-self.program.taken(owner)
        else:
            step = self.program.step('late-wrong' if phase == 'final-short' else phase, owner)
            wanted = 1, 0, step.after.counter, step.after.taken
        self.prediction(owner, history, source, wanted)
        if existing_source:
            witness = {k: v for k, v in self.origins['late-wrong', owner].items() if k != 'source'}
        else:
            witness = self.occurrence(owner, history, transfer, source, monitor)
            self.remember(source)
        effect = next(row for prior, row in zip(self.program.steps, monitor.records, strict=False)
            if prior.phase == ('flip' if phase == 'final-long' else 'late-wrong' if phase == 'final-short' else phase) and prior.owner == owner)
        self.check(True, witness['accepted'] > effect['tick'], 'consumer is fresh after its own actual learning')
        self.consumers[phase, owner] = dict(expected=wanted, actual=values(source), **witness)

    def finish(self, monitor):
        self.check(False, self.closed, 'one complete four-branch cohort')
        VersionChecks.finish(self, monitor)
        self.check({(s.phase, s.owner) for s in self.program.steps}, set(self.origins), 'every declared source teaches once')
        self.check({(s.phase, s.owner) for s in self.program.steps if s.phase.startswith('late')}, set(self.late),
            'all correct/agreement and originally wrong late sources have distinct current-state witnesses')
        self.check(True, all(r['actual_effect_tick'] is not None for r in self.late.values()), 'all delayed effects actually occurred')
        expected = {(phase, owner) for phase in ('flip', 'late-correct', 'late-wrong', 'final-short', 'final-long') for owner in self.program.owners}
        self.check(expected, set(self.consumers), 'every branch has all mandatory fresh short/long consumers')
        self.check(4, len(self.cadences), 'all four feedback groups have their full cadence checked')
        self.check(set(self.program.pc(o) for o in self.program.owners), {r['match_pc'] for r in self.origins.values()},
            'four actual matching PCs, not only different index ancestors')
        self.closed = True

    def snapshot(self):
        return deepcopy(dict(super().snapshot(), program_state=self.program.state()))
