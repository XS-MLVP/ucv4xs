"""Compare declared sources, actual lineage, recovery and fresh consumers."""
from toffee import CheckContext, Scoreboard, ScoreboardMode, TransferState
from bpuverify.utage.model.semantic import Context, tag
from bpuverify.utage.model.source_ownership import ASSOCIATION_RULES, RECOVERY_RULES, POSITION


def actual_fields(prediction, keys):
    meta = prediction.meta; slot = meta['abtbResult'][0]
    values = dict(indices=tuple(meta['readIndex']),
        folds=tuple(row['foldedHist'] for row in meta['foldedPathHistForTrain_hist']),
        valid=tuple(row['valid'] for row in meta['abtbResult']),
        positions=tuple(row['cfiPosition'] for row in meta['abtbResult']),
        base=slot['baseTaken'], strong=slot['baseIsStrongBias'], hit=prediction.hit,
        provider=slot['tableId'], counter=slot['takenCtr_value'], taken=prediction.taken,
        predicted=slot['predTaken'])
    return {key: values[key] for key in keys}


class SourceOwnershipChecks:
    def __init__(self, program, coverage):
        self.program, self.coverage = program, coverage
        self.board = Scoreboard('utage.'+program.family)
        self.completed = set()

    def check(self, expected, actual, point):
        self.board.check(expected=expected, actual=actual, context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT, request=dict(point=point, program=self.program.state())))

    def begin(self, rule): self.coverage.record('reached', rule)
    def end(self, rule):
        self.completed.add(rule)
        self.coverage.record('checked', rule)

    def profile(self, profile, actual, base, *, override_history=None):
        wanted = profile.expected(base, override_history=override_history)
        self.check(wanted, actual_fields(actual, wanted), 'complete actual source '+profile.name)

    def overlapping(self, transfers):
        self.begin('actual-overlap')
        self.check(len(self.program.sequence), len(transfers), 'all requests complete exactly once')
        self.check(True, all(t.state is TransferState.COMPLETED for t in transfers), 'all real query transfers completed')
        self.check(True, all(a.accepted_event.tick < b.accepted_event.tick < a.completed_event.tick
            for a, b in zip(transfers, transfers[1:])), 'every adjacent request actually overlaps its predecessor')
        self.end('actual-overlap')

    def lineage(self, rows, accepted):
        p = self.program
        self.check(4, len(accepted), 'four compound input-only transfers accepted')
        expected = tuple((profile.pc, profile.context, None) for profile in p.profiles)
        expected += ((p.decoy.pc, p.decoy.context, p.stage),)
        actual = tuple((row.inputs.read_pc, row.inputs.read_context, row.inputs.override) for row in rows)
        self.check(expected, actual, 'three consecutive public source inputs then actual override')
        self.check(True, all(row.inputs.select and row.inputs.advance for row in rows), 'all source stages advanced')
        self.check((p.target.pc, Context.from_recent(p.history)),
            (rows[-1].inputs.override_pc, rows[-1].inputs.override_context),
            'actual recovery PC and complete folded context')
        self.begin('actual-input-lineage'); self.end('actual-input-lineage')
        self.begin('discriminating-ages')
        self.profile(p.old, rows[1].prediction, 1)
        self.profile(p.young, rows[2].prediction, 1)
        self.end('discriminating-ages')

    def recovery(self, row):
        p = self.program
        self.begin('selected-snapshot')
        self.profile(p.target, row.prediction, 1, override_history=p.history)
        self.end('selected-snapshot')
        if p.learning:
            self.begin('new-content-visible')
            cells = row.shadow['cells']
            actual = cells[(row.shadow['enq']-1) % len(cells)]
            self.check(dict(valid=1, data_valid=1, index=p.target.indices[0],
                tag=tag(p.target.pc, p.target.context, 0), position=POSITION, counter=p.latest.counter),
                actual, 'latest actual target version already visible AT recovery, not only afterwards')
            self.end('new-content-visible')

    def immutable(self, originals):
        self.begin('immutable-sources')
        self.check(tuple(frozen for _, frozen in originals), tuple(source.meta for source, _ in originals),
                   'all ordinary prediction snapshots remain immutable')
        self.end('immutable-sources')
        needed = set(ASSOCIATION_RULES if self.program.family == 'request-ownership' else RECOVERY_RULES)
        if getattr(self.program, 'learning', False): needed.add('new-content-visible')
        self.check(needed, self.completed, 'all declared semantic obligations checked')
