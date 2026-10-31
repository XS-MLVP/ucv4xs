"""An old completion cannot discharge a newer semantic learning version."""
from dataclasses import dataclass
from suites.frontend.bpu.bpu.model.tage.forwarding import PC, resolved_path
from suites.frontend.bpu.bpu.model.tage.service import ServiceProgram, VIA_PC


@dataclass(frozen=True, slots=True)
class Program:
    relation: str
    extent: str

    def __post_init__(self):
        if self.relation not in ('same-identity', 'other-identity'):
            raise ValueError('declared old-service identity relation required')
        if self.extent not in ('both-branches', 'executed-prefix-only'):
            raise ValueError('declared actually executed feedback prefix required')

    @property
    def name(self): return self.relation + '.' + self.extent

    @property
    def first_order(self): return (0, 1) if self.relation == 'same-identity' else (1, 0)

    @property
    def service_program(self): return ServiceProgram((None, VIA_PC), (*self.first_order, 0))

    @property
    def late_path(self): return resolved_path() if self.extent == 'both-branches' else ((0, False, False),)

    @property
    def target(self): return (0, 7) if self.extent == 'both-branches' else (0, 6)

    @property
    def remaining(self):
        if self.relation == 'other-identity': return (1, 1)
        return (2, 2) if self.extent == 'both-branches' else (2, 1)

    @property
    def late_flags(self): return (1, int(self.extent == 'both-branches'))

    def counters(self, history, *, final=False, mixed=False):
        if final: return self.target if history == 0 else (1, 6)
        if mixed and history == self.first_order[0]: return (1, 6)
        return (2, 5)


PROGRAMS = tuple(Program(relation, extent)
    for relation in ('same-identity', 'other-identity')
    for extent in ('both-branches', 'executed-prefix-only'))
