"""A logical branch program with Ahead contention, not Main capacity pressure."""
from collections import Counter, defaultdict
from dataclasses import dataclass

from bpuverify.bpu.model.ahead_working_set import BASE, STRIDE, Edge, RULES, REPLACEMENT_RULES
from bpuverify.bpu.model.abtb.alias import mainbtb_route, physical_index
from bpuverify.bpu.model.path_history import WIDTH, path_contribution

KINDS = ('conditional', 'mixed')


@dataclass(frozen=True, slots=True)
class Program:
    kinds: str

    def __post_init__(self):
        if self.kinds not in KINDS:
            raise ValueError('unknown logical branch kind profile')

    @property
    def cohorts(self):
        return 5

    @property
    def rules(self):
        return RULES + REPLACEMENT_RULES

    @property
    def label(self):
        return self.kinds + '.new-identity-after-strengthening'

    def edges(self, cohort):
        if type(cohort) is not int or not 0 <= cohort < self.cohorts:
            raise ValueError('cohort must belong to this declared program')
        pcs = tuple(BASE + cohort * 256 + STRIDE * index for index in range(16))
        return tuple(Edge(pc, pcs[(index + 1) % len(pcs)],
                          3 if index == len(pcs) - 1 else
                          2 if self.kinds == 'mixed' and index % 3 == 0 else 1)
                     for index, pc in enumerate(pcs))

    def state(self):
        return dict(kinds=self.kinds, cohorts=self.cohorts, branches_per_cohort=16,
                    semantic_event='a new branch identity must not inherit strengthened old confidence',
                    physical_enumeration=False, full_FTQ_reachability_proved=False)


def logical_histories(program, cohort):
    """Three real program laps discard initial history; no sampled folds."""
    history = 0
    for _ in range(3):
        before = []
        for edge in program.edges(cohort):
            before.append(history)
            history = ((history << 2) ^ path_contribution(edge.cfi_pc, edge.target)) % (1 << WIDTH)
    return tuple(before)


def geometry(program):
    main, ahead = Counter(), defaultdict(list)
    for cohort in range(program.cohorts):
        edges = program.edges(cohort)
        histories = logical_histories(program, cohort)
        for index, edge in enumerate(edges):
            route = mainbtb_route(edge.pc, edge.position)
            main[route['selected_physical_align'], route['internal_bank'], route['entry_set']] += 1
            # An Ahead read uses the history before the preceding branch,
            # not a current request's post-branch history.
            selected = physical_index(edge.pc, histories[(index - 1) % len(edges)] % 16)
            ahead[selected].append(dict(cohort=cohort, branch=index, tag=edge.pc % (1 << 24)))
    return dict(total_identities=sum(main.values()), maximum_Main_residents=max(main.values()),
                Ahead_groups=len(ahead), Ahead_identity_counts=sorted(map(len, ahead.values())),
                Ahead_identities={str(key): value for key, value in sorted(ahead.items())},
                runtime_index_and_replacement_effects_NOT_proved=True)
