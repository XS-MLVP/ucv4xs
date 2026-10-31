"""Declared query identities and saved-source obligations, independent of DUT."""
from dataclasses import asdict, dataclass, replace

from suites.frontend.bpu.utage.model.semantic import Context, training_folds, training_folds, indices, tag

PC, POSITION = 0x40000000, 5
ASSOCIATION_MODES = ('pc-only', 'history-only', 'mixed')
ASSOCIATION_RULES = ('prepared-identities', 'actual-overlap', 'complete-responses',
                     'preserved-neighbors', 'immutable-sources')
RECOVERY_RULES = ('discriminating-ages', 'actual-input-lineage', 'selected-snapshot',
                  'fresh-consumers', 'immutable-sources')


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    pc: int
    history: int
    counter: int | None

    @property
    def context(self): return Context.from_recent(self.history)
    @property
    def indices(self): return indices(self.pc, self.context)
    @property
    def taken(self):
        if self.counter is None: raise ValueError('a cold profile has no defined direction')
        return int(self.counter >= 4)

    def expected(self, base, *, override_history=None):
        history = self.history if override_history is None else override_history
        hit = self.counter is not None and tag(self.pc, Context.from_recent(history), 0) == tag(self.pc, self.context, 0)
        fields = dict(indices=self.indices, folds=training_folds(Context.from_recent(history)),
                      valid=(1, 0, 0, 0), positions=(5, 6, 7, 8), base=base, strong=0, hit=int(hit))
        if hit: fields.update(provider=0, counter=self.counter, taken=self.taken, predicted=self.taken)
        return fields


class AssociationProgram:
    family = 'request-ownership'

    def __init__(self, mode):
        if mode not in ASSOCIATION_MODES: raise ValueError('unknown identity distinction')
        self.mode = mode
        pcs = (PC,) * 4 if mode == 'history-only' else (PC, PC+1, PC+0x40, PC+0x80)
        histories = (5,) * 4 if mode == 'pc-only' else (5, 11, 19, 25)
        self.profiles = tuple(Profile(name, pc, history, counter) for name, pc, history, counter in zip(
            ('old', 'young', 'decoy', 'cold'), pcs, histories, (5, 2, 4, None), strict=True))
        self.sequence = tuple((self.profiles[index], base) for index, base in
                              ((0, 0), (1, 1), (2, 0), (3, 1), (1, 0), (0, 1), (3, 0), (2, 1)))
        if len({p.indices for p in self.profiles}) != 4: raise ValueError('identities must not share table rows')

    def state(self): return dict(mode=self.mode, profiles=tuple(asdict(p) for p in self.profiles))


class RecoveryProgram:
    def __init__(self, stage, *, retag=False, learning=False):
        if stage not in ('s2', 's3') or type(retag) is not bool or type(learning) is not bool:
            raise ValueError('unknown recovery program')
        self.stage, self.retag, self.learning = stage, retag, learning
        self.family = stage+'-snapshot'
        self.mode = ('retag' if retag else 'match') + ('.learning' if learning else '.stable')
        self.profiles = AssociationProgram('mixed').profiles[:3]
        self.old, self.young, self.decoy = self.profiles
        self.target = self.young if stage == 's2' else self.old
        self.history = self.target.history ^ int(retag)
        self.latest = replace(self.target, counter=self.target.counter + (1 if self.target.taken else -1)) if learning else self.target
        assert self.old.taken != self.young.taken and len({p.counter for p in self.profiles}) == 3

    def state(self):
        return dict(stage=self.stage, mode=self.mode, profiles=tuple(asdict(p) for p in self.profiles),
                    selected=asdict(self.target), latest=asdict(self.latest), override_history=self.history)
