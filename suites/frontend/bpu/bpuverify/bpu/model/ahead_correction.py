"""Branch-owned direction reversal, not a coordinate-selected workload.

A forward conditional skips the remaining straight-line instructions in its
fetch. Both outcomes enter the next fetch block, but they have different
direction, CFI position, instruction paths and history contributions. Real
indirect branches join the blocks into a closed program. This keeps direction
correction separate from changing target identities or replacing Main tags.
"""
from collections import Counter
from dataclasses import asdict, dataclass

from bpuverify.bpu.model.abtb.alias import mainbtb_route
from bpuverify.bpu.model.ahead_working_set import BASE, Edge, SIZES, expected_branch
from bpuverify.bpu.model.selection import fallthrough

SELECTIONS = ('all', 'alternate')
RULES = ('original-feedback-ownership', 'warm-full-working-set', 'selected-main-reversed',
         'negative-low-saturation', 'unselected-positive-preserved', 'nonconditional-preserved',
         'selected-main-restored', 'positive-high-saturation', 'late-full-reconsumption',
         'immutable-original-sources')


@dataclass(frozen=True, slots=True)
class AheadCorrectionProgram:
    size: str
    selection: str

    def __post_init__(self):
        if self.size not in SIZES or self.selection not in SELECTIONS:
            raise ValueError('unknown direction working-set size or logical selection')
        routes = Counter()
        for edge in self.edges(0):
            route = mainbtb_route(edge.pc, edge.position)
            routes[route['selected_physical_align'], route['internal_bank'], route['entry_set']] += 1
        if max(routes.values()) != 1:
            raise ValueError('direction correction must not depend on Main identity replacement')

    @property
    def cohorts(self): return 1

    @property
    def label(self): return f'{self.size}.{self.selection}'

    @property
    def rules(self): return RULES

    def edges(self, cohort):
        if type(cohort) is not int or cohort != 0:
            raise ValueError('direction working set has one declared branch program')
        pcs = [BASE+0x20000]
        for number in range(SIZES[self.size]-1):
            pc = pcs[-1]
            pcs.append(fallthrough(pc).branch.target if number % 2 == 0 else pc+17)
        return tuple(Edge(pc, pcs[(number+1) % len(pcs)], 1 if number % 2 == 0 else 3)
                     for number, pc in enumerate(pcs))

    @property
    def selected(self):
        conditional = tuple(edge.pc for edge in self.edges(0) if edge.kind == 1)
        return conditional if self.selection == 'all' else conditional[::2]

    def desired_branch(self, edge, *, negative):
        if negative and edge.pc in self.selected:
            branch = fallthrough(edge.pc).branch
            return dict(taken=False, position=branch.position, target=branch.target, kind=0, action=0)
        return expected_branch(edge)

    def desired_counter(self, edge, *, negative):
        if edge.kind != 1: return 2
        return 0 if negative and edge.pc in self.selected else 3

    def state(self):
        return dict(asdict(self), cohorts=1, branches=len(self.edges(0)),
                    corrected_conditional_branches=len(self.selected))
