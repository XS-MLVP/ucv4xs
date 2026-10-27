"""Declared real predecessor paths and branch-owned protection lifetimes.

Path choices are fixed before any DUT exists. No sampled fold, provider, victim
or uncovered row selects stimulus. Index ancestry and tag ancestry differ from
the current token history; only their relevant <=12-bit features are compiled.
The full composed model still owns and checks all higher history bits.
"""
from collections import Counter
from dataclasses import asdict, dataclass, replace
from functools import lru_cache

from bpuverify.abtb.model.semantic import coordinate as ahead_coordinate
from bpuverify.bpu.model.abtb.alias import mainbtb_route
from bpuverify.bpu.model.ahead_working_set import Edge
from bpuverify.bpu.model.path_history import PathHistoryReference
from bpuverify.utage.model.semantic import ALT_FOLDS, INDEX_FOLDS, TAG_FOLDS, Context, indices, tag
from bpuverify.utage.model.usefulness_events import ProtectionState

ANCHOR, SHORT_POSITION, POSITION, FALLBACK = 0x40000000, 2, 10, 12
PROFILES = {'turnover-forward': (32, False), 'turnover-reverse': (32, True), 'capacity-reverse': (512, True)}
# The first four decisions change only long-history bits 5..8; they
# preserve the short owner's index and tag. The fifth contributes bit 4.
# The last four decisions change the real tail and contribute bits 0..3.
# In DefaultConfig the 9-bit long history is an unfurled index, so a single
# Ahead index cannot own all 512 rows. Sixteen declared tail/helper pairs
# cover every row while preserving ordinary, independently owned feedback.
CONTROLS = tuple(((site, bit),) for site,bit in
                 ((3,2),(3,1),(4,2),(2,1),(4,1),(5,1),(5,2),(6,1),(6,2)))
FEATURES = tuple(sorted(set((*INDEX_FOLDS, *TAG_FOLDS, *ALT_FOLDS))))
RULES = ('genuine-predecessor-paths', 'distinct-original-history-owners', 'protected-short-prerequisites',
         'long-history-admissions', 'retained-after-shadow-turnover', 'correct-opposition-reward',
         'upper-protection-hold', 'selective-penalty', 'selective-recovery',
         'untouched-identities-preserved', 'late-all-history-consumers', 'immutable-original-sources',
         'selected-direction-reversal', 'mixed-history-directions', 'selected-direction-restoration')
MAINTENANCE_RULES = ('qualified-failure-pressure', 'shared-prestate-protection',
                     'directions-retained', 'all-post-maintenance-consumers', 'immutable-original-sources')
SHORT_PROFILES = ('retained-oldest','retained-newest','turnover-oldest','turnover-newest')
SHORT_RULES = ('real-read-and-match-ancestors','all-short-identities-learned','short-not-long-consumers',
    'selected-gains-protection','selected-direction-and-protection-boundaries','other-paths-preserved',
    'native-SRAM-and-retention','fresh-all-path-consumers','immutable-original-sources')
SHORT_MIXED_PROFILES = tuple(age+'-'+order for age in ('oldest','newest') for order in ('forward','reverse'))
SHORT_MIXED_RULES = ('real-path-owners','all-initial-NT-consumers','persistent-mixed-directions',
    'selected-NT-to-T','selected-T-to-NT','unrelated-experience-preserved','original-learning-once',
    'no-longer-substitution','mixed-SRAM-after-turnover','restored-SRAM-after-turnover',
    'fresh-all-final-consumers','immutable-originals')
SHORT_TURNAROUND_PATHS = (15,8,9,10)
SHORT_RESTORATION_PATHS = (11,12,13,14)


@dataclass(frozen=True, slots=True)
class HistoryPath:
    ordinal: int
    word: int
    pcs: tuple[int, ...]
    read_indices: tuple[int, int]
    tag_features: tuple[int, ...]
    tags: tuple[int, int]
    ahead_key: tuple[int, int]
    tail_key: tuple[int, ...] | None = None

    @property
    def tail_variant(self): return tuple(self.pcs[5:]) if self.tail_key is None else self.tail_key

    def edges(self):
        return tuple(Edge(pc, self.pcs[i+1] if i<7 else ANCHOR, 3, max(7,pc%16))
                     for i, pc in enumerate(self.pcs))


@lru_cache(maxsize=512)
def history_path(ordinal):
    if type(ordinal) is not int or not 0 <= ordinal < 512:
        raise ValueError('one declared nine-decision predecessor path required')
    word = ordinal ^ (ordinal >> 1)
    pcs = [0x40080000+i*0x10000+(i//2)*512+32+16*i+2*(i%4) for i in range(8)]
    for decision, changes in enumerate(CONTROLS):
        if word & (1 << decision):
            for site, bit in changes: pcs[site] ^= 1 << bit
    history, samples = PathHistoryReference(), [0]
    for i, pc in enumerate(pcs):
        samples.append(history.advance(taken=True, cfi_pc=(pc&~15)+max(7,pc%16),
            target=pcs[i+1] if i<7 else ANCHOR).history)
    index_context, tag_context = (Context.from_recent(samples[i]&4095) for i in (6, 7))
    return HistoryPath(ordinal, word, tuple(pcs), indices(pcs[7], index_context),
        tuple(tag_context.folds[i] for i in FEATURES),
        tuple(tag(ANCHOR, tag_context, table) for table in range(2)),
        ahead_coordinate(pcs[7], samples[6]&15))


@lru_cache(maxsize=16)
def short_history_path(ordinal):
    """A fixed two-stage dispatch, compiled before observing any hardware."""
    if type(ordinal) is not int or not 0<=ordinal<16:
        raise ValueError('one of the sixteen declared incoming program paths required')
    word = ordinal^(ordinal>>1)
    pcs = list(history_path(0).pcs)
    # Paired real tail choices keep the Ahead index fixed. They vary only
    # the low five long-index bits, leaving the four older bits available
    # for independent learning companions with the same short identity.
    pcs[6] ^= ((word&7)<<2) | ((word&8)<<2)
    pcs[7] ^= word&7
    history,samples = PathHistoryReference(),[0]
    for i,pc in enumerate(pcs):
        samples.append(history.advance(taken=True,cfi_pc=(pc&~15)+max(7,pc%16),
            target=pcs[i+1] if i<7 else ANCHOR).history)
    read,match = Context.from_recent(samples[6]&4095),Context.from_recent(samples[7]&4095)
    return HistoryPath(ordinal,word,tuple(pcs),indices(pcs[7],read),
        tuple(match.folds[i] for i in FEATURES),tuple(tag(ANCHOR,match,t) for t in range(2)),
        ahead_coordinate(pcs[7],samples[6]&15),tuple(pcs[5:]))


@dataclass(frozen=True,slots=True)
class ShortWorkingSetProgram:
    profile: str
    short_only = True

    def __post_init__(self):
        if self.profile not in SHORT_PROFILES:
            raise ValueError('declared short-path retention lifetime required')

    @property
    def paths(self):
        return tuple(short_history_path(i) for i in range(8 if self.profile.startswith('retained-') else 16))

    @property
    def helper(self):return self.paths[0]

    @property
    def helpers(self):return (self.helper,)

    @property
    def positives(self):return self.paths[1:]

    @property
    def selected(self):return self.positives[:1] if self.profile.endswith('-oldest') else self.positives[-1:]

    @property
    def rules(self):return SHORT_RULES

    def edges(self,cohort):
        if cohort!=0:raise ValueError('one declared incoming program, not physical cohorts')
        return (Edge(ANCHOR,self.helper.pcs[0],1,SHORT_POSITION),*self.helper.edges())

    def state(self):
        return dict(profile=self.profile,short_paths=len(self.positives),selected=self.selected[0].ordinal,
            semantic_event='independent incoming short experience survives turnover and selective reward',
            physical_enumeration=False,new_predictor_algorithm=False,full_FTQ_reachability_proved=False)


@lru_cache(maxsize=128)
def short_learning_path(ordinal, older):
    """A different older program reaches the SAME recent incoming path.

    Fixed declared code, compiled before any DUT exists. Distinct longer
    companions are intentional; they must not mask the original consumers.
    """
    if older not in (*SHORT_TURNAROUND_PATHS,*SHORT_RESTORATION_PATHS):
        raise ValueError('declared older direction-learning path required')
    original=short_history_path(ordinal)
    pcs=(*history_path(older).pcs[:-2],*original.pcs[-2:])
    history,samples=PathHistoryReference(),[0]
    for i,pc in enumerate(pcs):
        samples.append(history.advance(taken=True,cfi_pc=(pc&~15)+max(7,pc%16),
            target=pcs[i+1] if i<7 else ANCHOR).history)
    read,match=Context.from_recent(samples[6]),Context.from_recent(samples[7])
    return replace(original,pcs=pcs,read_indices=indices(pcs[7],read),
        tag_features=tuple(match.folds[i] for i in FEATURES),
        tags=tuple(tag(ANCHOR,match,t) for t in range(2)),
        ahead_key=ahead_coordinate(pcs[7],samples[6]&15),tail_key=tuple(pcs[5:]))


@dataclass(frozen=True,slots=True)
class ShortMixedWorkingSetProgram(ShortWorkingSetProgram):
    def __post_init__(self):
        if self.profile not in SHORT_MIXED_PROFILES:
            raise ValueError('declared mixed short-experience lifetime required')
        originals={path.read_indices[1] for path in self.paths}
        for path in self.positives:
            companions=tuple(short_learning_path(path.ordinal,older) for older in
                (*SHORT_TURNAROUND_PATHS,*SHORT_RESTORATION_PATHS))
            if any((item.read_indices[0],item.tags[0])!=(path.read_indices[0],path.tags[0]) for item in companions):
                raise ValueError('older learning must retain the original short identity')
            if len({item.read_indices[1] for item in companions})!=len(companions) or any(
                    item.read_indices[1] in originals for item in companions):
                raise ValueError('longer companions cannot mask original short consumers')

    @property
    def paths(self):return tuple(short_history_path(i) for i in range(16))

    @property
    def learning_order(self):
        return self.positives[::-1] if self.profile.endswith('reverse') else self.positives

    @property
    def selected(self):
        return (self.learning_order[0 if self.profile.startswith('oldest') else -1],)

    @property
    def mixed(self):return tuple(path for path in self.positives if path.ordinal%2==0)

    @property
    def rules(self):return SHORT_MIXED_RULES

    def reversal(self,path,*,counter,protection,taken):
        if path not in self.positives or type(taken) is not bool:
            raise ValueError('declared incoming owner and explicit direction required')
        state=ProtectionState(counter,protection)
        if bool(state.taken)==taken:raise ValueError('declared direction is already present')
        result=[]
        for older in SHORT_TURNAROUND_PATHS if taken else SHORT_RESTORATION_PATHS:
            after=state.feedback(predicted=state.taken,base=int(not taken),actual=int(taken))
            result.append((short_learning_path(path.ordinal,older),state,after))
            state=after
            if bool(state.taken)==taken:return tuple(result)
        raise ValueError('declared distinct originals cannot complete the direction change')

    def state(self):
        return dict(profile=self.profile,short_paths=len(self.positives),selected=self.selected[0].ordinal,
            learning_order=tuple(path.ordinal for path in self.learning_order),
            mixed_taken=tuple(path.ordinal for path in self.mixed),
            semantic_event='mixed incoming experience survives selective reversal, restoration and shadow turnover',
            physical_enumeration=False,new_predictor_algorithm=False,full_FTQ_reachability_proved=False)


@dataclass(frozen=True, slots=True)
class HistoryWorkingSetProgram:
    profile: str

    def __post_init__(self):
        if self.profile not in PROFILES: raise ValueError('unknown history lifetime profile')

    @property
    @lru_cache(maxsize=len(PROFILES))
    def paths(self): return tuple(history_path(i) for i in range(PROFILES[self.profile][0]))

    @property
    def helper(self): return self.paths[0]

    @property
    @lru_cache(maxsize=len(PROFILES))
    def helpers(self):
        # These words use the fixed Main predecessor choices followed by
        # their declared tail variant. Helpers can run naturally; a helper is
        # not rebuilt with six recoveries for every protection update.
        return tuple(path for path in self.paths if path.word & 31 == 0)

    def helper_for(self, path):
        return next(helper for helper in self.helpers if helper.tail_variant == path.tail_variant)

    @property
    @lru_cache(maxsize=len(PROFILES))
    def positives(self):
        helpers = {path.ordinal for path in self.helpers}
        return tuple(path for path in self.paths if path.ordinal not in helpers)

    @property
    @lru_cache(maxsize=len(PROFILES))
    def selected(self): return self.positives[::4][:32]

    @property
    @lru_cache(maxsize=len(PROFILES))
    def short_prerequisites(self):
        selected = {}
        for path in self.paths: selected.setdefault(path.read_indices[0], path)
        return tuple(selected.values())

    @property
    @lru_cache(maxsize=len(PROFILES))
    def short_consumers(self):
        selected = {}
        for path in self.positives:selected.setdefault(path.read_indices[0],path)
        return tuple(selected.values())

    @property
    @lru_cache(maxsize=len(PROFILES))
    def revisit(self): return self.positives[::-1] if PROFILES[self.profile][1] else self.positives

    @property
    def cohorts(self): return 1

    @property
    def rules(self): return RULES

    def edges(self, cohort):
        if cohort != 0: raise ValueError('one declared anchor and predecessor family')
        return (Edge(ANCHOR, self.helper.pcs[0], 1, SHORT_POSITION), *self.helper.edges())

    def state(self):
        return dict(asdict(self), histories=len(self.paths), positive_histories=len(self.positives),
            negative_helpers=len(self.helpers),short_prerequisites=len(self.short_prerequisites),
            selected_errors=len(self.selected))


def main_capacity(path):
    routes = Counter()
    for edge in (*path.edges(), *(Edge(ANCHOR,path.pcs[0],kind,pos)
            for kind,pos in ((1,SHORT_POSITION),(1,POSITION),(3,FALLBACK)))):
        route = mainbtb_route(edge.pc, edge.position)
        routes[route['selected_physical_align'],route['internal_bank'],route['entry_set']] += 1
    return max(routes.values())


class HistoryLearningLedger:
    """Current logical values, advanced only by original semantic outcomes."""
    def __init__(self, program):
        self.program = program
        self.states, self.transitions = {}, Counter()

    def allocate(self, path, *, taken):
        if (not 0 <= path.ordinal < len(self.program.paths) or path != self.program.paths[path.ordinal]
                or path in self.program.helpers or path.ordinal in self.states or type(taken) is not bool):
            raise ValueError('one new logical long identity with an explicit direction')
        self.states[path.ordinal] = ProtectionState(4 if taken else 3, 2)
        self.transitions['allocate'] += 1
        return self.states[path.ordinal]

    def feedback(self, path, *, predicted, base, actual):
        if path.ordinal not in self.states: raise ValueError('feedback needs an admitted original identity')
        before = self.states[path.ordinal]
        after = before.feedback(predicted=predicted, base=base, actual=actual)
        self.states[path.ordinal] = after
        self.transitions['reward' if after.useful>before.useful else
                         'penalty' if after.useful<before.useful else 'hold'] += 1
        return after

    def reversal(self, path, *, taken):
        """Freeze the required real outcomes before driving, without mutation."""
        if (type(taken) is not bool or path.ordinal not in self.states
                or path != self.program.paths[path.ordinal]):
            raise ValueError('direction change needs an admitted original history and explicit outcome')
        state = self.states[path.ordinal]
        if bool(state.taken) == taken:raise ValueError('direction is already the declared result')
        result = []
        # Eight confidence values bound a semantic transition, not elapsed time.
        for _ in range(8):
            state = state.feedback(predicted=state.taken,base=int(taken),actual=int(taken))
            result.append(state)
            if bool(state.taken) == taken:return tuple(result)
        raise AssertionError('bounded direction semantics did not cross its threshold')

    def maintain(self, previous):
        """Global protection comes from one prestate; direction feedback remains."""
        if self.states.keys() != previous.keys():
            raise NotImplementedError('new identity admission overlapping maintenance needs its displaced-owner prestate')
        self.states = {ordinal:ProtectionState(state.counter,previous[ordinal].useful//2)
                       for ordinal,state in self.states.items()}
        self.transitions['maintenance'] += 1

    def state(self):
        return dict(identities=len(self.states), transitions=dict(self.transitions),
                    states={ordinal:asdict(value) for ordinal,value in self.states.items()})
