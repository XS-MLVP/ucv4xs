"""One conditional self-loop exposes cold disabled-source arbitration."""
from dataclasses import asdict, dataclass

from suites.frontend.bpu.bpu.model.ahead_working_set import BASE, Edge

SOURCES = ('ubtb', 'tage')
MODES = ('disabled-from-reset', 'primed-then-disabled')
RULES = ('isolated-source-disabled', 'original-main-discovery', 'actual-feedback-owned',
         'fresh-main-consumer', 'immutable-original-source')


@dataclass(frozen=True, slots=True)
class ColdSourceProgram:
    source: str
    mode: str
    cohorts: int = 1

    def __post_init__(self):
        if self.source not in SOURCES or self.mode not in MODES or self.cohorts != 1:
            raise ValueError('cold isolation requires one declared source and initialization mode')

    @property
    def rules(self): return RULES

    def edges(self, cohort):
        if cohort != 0: raise ValueError('cold isolation has one branch program')
        return (Edge(BASE, BASE, 1),)

    def state(self): return asdict(self)
