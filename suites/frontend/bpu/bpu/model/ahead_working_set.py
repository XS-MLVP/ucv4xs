"""Declared branch programs and logical learning, never DUT-selected inputs."""
from suites.frontend.bpu.models.configuration import ALIGN_HALFWORDS, MAIN_WAYS
from collections import Counter
from dataclasses import asdict, dataclass

from suites.frontend.bpu.bpu.model.abtb.alias import mainbtb_route
from suites.frontend.bpu.bpu.model.path_history import WIDTH, path_contribution

BASE, STRIDE, COHORT_STRIDE, POSITION = 0x40040000, 17, 0x10000, 7
SIZES = {'turnover': 16, 'resident': 128}
KINDS = ('conditional', 'mixed')
LIFETIMES = {'coexisting': 1, 'replacing': 5}
RULES = ('original-discoveries', 'actual-feedback-ownership', 'owned-lookahead-ancestry',
         'natural-ahead-consumers', 'conditional-reward-saturation', 'branch-kind-isolation',
         'late-working-set-consumers', 'immutable-original-sources')
REPLACEMENT_RULES = ('real-new-identity-service', 'old-strong-confidence-reinitialized')


@dataclass(frozen=True, slots=True)
class Edge:
    pc: int
    target: int
    kind: int
    position: int = POSITION

    @property
    def cfi_pc(self): return (self.pc // ALIGN_HALFWORDS * ALIGN_HALFWORDS) + self.position


@dataclass(frozen=True, slots=True)
class AheadWorkingSetProgram:
    size: str
    kinds: str
    lifetime: str

    def __post_init__(self):
        if self.size not in SIZES or self.kinds not in KINDS or self.lifetime not in LIFETIMES:
            raise ValueError('unknown branch working set, kind mix or lifetime')
        for cohort in range(self.cohorts):
            entries = self.edges(cohort)
            routes = Counter()
            for edge in entries:
                route = mainbtb_route(edge.pc, edge.position)
                routes[route['selected_physical_align'], route['internal_bank'], route['entry_set']] += 1
            if max(routes.values()) > MAIN_WAYS:
                raise ValueError('one active branch program must fit MainBTB associativity')

    @property
    def cohorts(self): return LIFETIMES[self.lifetime]

    @property
    def rules(self): return RULES + (REPLACEMENT_RULES if self.cohorts > 1 else ())

    @property
    def label(self): return f'{self.size}.{self.kinds}.{self.lifetime}'

    def edges(self, cohort):
        if type(cohort) is not int or not 0 <= cohort < self.cohorts:
            raise ValueError('cohort belongs to this declared lifetime')
        pcs = tuple(BASE + cohort*COHORT_STRIDE + STRIDE*number for number in range(SIZES[self.size]))
        return tuple(Edge(pc, pcs[(number+1) % len(pcs)],
            3 if number == len(pcs)-1 else 2 if self.kinds == 'mixed' and number % 3 == 0 else 1,
            max(POSITION,pc % ALIGN_HALFWORDS))
            for number, pc in enumerate(pcs))

    def state(self): return dict(asdict(self), cohorts=self.cohorts, branches_per_cohort=SIZES[self.size])


def strong_counter(edge):
    """Only conditional direction counters receive ordinary rewards."""
    return 3 if edge.kind == 1 else 2


def expected_branch(edge):
    return dict(taken=True, position=edge.position, target=edge.target, kind=edge.kind, action=0)


def semantic_history(program, cohort, passes=3):
    """Pure input trace; history is not assumed zero or borrowed from an IO."""
    if type(passes) is not int or passes < 1:
        raise ValueError('at least one complete logical pass required')
    history, samples = 0, []
    for _ in range(passes):
        current = []
        for edge in program.edges(cohort):
            current.append(history)
            history = ((history << 2) ^ path_contribution(edge.cfi_pc, edge.target)) % (1 << WIDTH)
        samples.append(tuple(current))
    return tuple(samples)


PREFIX_PROFILES=tuple(selected+'.'+order for selected in ('even-windows','odd-windows')
    for order in ('forward','reverse'))
PREFIX_RULES=('real-two-condition-windows','all-original-late-consumers','selected-early-reversal',
    'unexecuted-later-preserved','selected-whole-window-NT','lower-bound-holds',
    'earlier-restores-from-lower-bound','other-windows-preserved',
    'all-original-evidence-immutable','complete-actual-direction-state')


@dataclass(frozen=True,slots=True)
class PrefixWorkingSetProgram:
    """Six code blocks, each with an early and a later conditional branch.

    Visit order and the logically selected half change; bank/set coordinates
    are never stimulus parameters. A separate real predecessor owns each
    Ahead read, and an aligned recovery anchor has a neutral return edge.
    """
    profile: str
    initial_pc: int=0x40000000
    count: int=6

    def __post_init__(self):
        if self.profile not in PREFIX_PROFILES or self.count!=6:
            raise ValueError('declared two-condition instruction working set required')
        routes=Counter()
        for index in range(self.count):
            for edge in (self.predecessor(index),*self.branches(index)):
                route=mainbtb_route(edge.pc,edge.position)
                routes[route['selected_physical_align'],route['internal_bank'],route['entry_set']]+=1
        if max(routes.values())>MAIN_WAYS:raise ValueError('declared instructions exceed Main associativity')

    @property
    def rules(self):return PREFIX_RULES

    @property
    def label(self):return self.profile

    @property
    def order(self):return tuple(range(self.count))[::(-1 if self.profile.endswith('.reverse') else 1)]

    @property
    def selected(self):return tuple(range(0 if self.profile.startswith('even-') else 1,self.count,2))

    def pc(self,index):
        if type(index) is not int or not 0<=index<self.count:raise ValueError('declared instruction block required')
        return BASE+32*(index+1)

    def predecessor(self,index):return Edge(self.pc(index)+0x200,self.pc(index),2,4)

    def branches(self,index):
        pc=self.pc(index)
        return Edge(pc,pc+0x2000,1,2),Edge(pc,pc+0x4000,1,12)

    def edges(self,cohort):
        if cohort!=0:raise ValueError('one logical working set, not physical cohorts')
        return tuple(self.predecessor(index) for index in self.order)

    def state(self):return dict(profile=self.profile,windows=self.count,conditionals=2*self.count,
        selected=self.selected,order=self.order,physical_enumeration=False,new_predictor_algorithm=False)

    def outcomes(self,index,choice,*,early_taken,later_taken):
        from suites.frontend.bpu.bpu.model.pipeline import Outcome
        from suites.frontend.bpu.bpu.model.selection import Kind
        if type(early_taken) is not bool or type(later_taken) is not bool:
            raise TypeError('instruction outcomes require declared semantic bools')
        result=[]
        for edge,taken in zip(self.branches(index),(early_taken,later_taken),strict=True):
            wrong=((not choice.taken or (choice.position,choice.target,choice.kind)!=(
                edge.position,edge.target,Kind.CONDITIONAL)) if taken else
                bool(choice.taken and choice.position==edge.position))
            result.append(Outcome(edge.position,edge.target,Kind.CONDITIONAL,taken,mispredict=wrong))
            if taken or wrong:break
        return tuple(result)
