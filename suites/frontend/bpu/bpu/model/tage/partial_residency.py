"""Resident identity updates differ from reinstallation after identity eviction."""
from dataclasses import dataclass

from suites.frontend.bpu.bpu.model.tage.dual_migration import (
    PC, PATHS, POSITIONS, TABLE, Step, provider, preparation as original_preparation)

A_ONLY = ((0, False, False),)
PAIR = ((0, False, False), (1, True, False))
PARTIAL_LABELS = frozenset((f'{prefix}-a-lowers-to-{n}'
                           for prefix in ('original', 'current') for n in (1, 0)))


@dataclass(frozen=True, slots=True)
class Stage:
    sources: tuple[str, ...]
    outcomes: tuple
    proposals: tuple
    pending_after: tuple
    service: tuple
    pending_replacements: int = 0


@dataclass(frozen=True, slots=True)
class ResidencyProgram:
    name: str
    feature: str
    saturated_source: bool
    stages: tuple[Stage, ...]

    def preparation(self):
        for step in tuple(original_preparation())[:23]:
            yield step
            if step.save and self.saturated_source:
                for n in (1, 0):
                    yield Step(f'original-a-lowers-to-{n}', 'original', A_ONLY,
                               ((0, 3), (provider(0, n), provider(1, 5))))
        if self.saturated_source:
            for n in (1, 0):
                yield Step(f'current-a-lowers-to-{n}', 'original', A_ONLY,
                           ((0, 0), (provider(1, n), None)))

    @property
    def source_names(self):
        return tuple(name for stage in self.stages for name in stage.sources)

    def capture_names(self, step):
        if step.save:
            return tuple(n for n in self.source_names if n.startswith('a-old-'))
        return ('b-old',) if step.name == 'original-a-lowers-to-0' else ()

    def source_profile(self, name):
        if name not in self.source_names:
            raise ValueError('undeclared original residency source')
        return (((0, 3), (provider(0, 0), provider(1, 5))) if name == 'b-old'
                else ((1, 3), (provider(0, 2), provider(1, 5))))

    def profile(self, stage, name, *, serviced):
        if name not in PATHS or type(stage) is not int or not 0 <= stage < len(self.stages):
            raise ValueError('undeclared residency consumer')
        main = (0, 0) if self.name == 'resident-only' else (0, 3)
        # Read competition blocks TAGE SRAM, not the independently checked
        # Main old-counter feedback rule; Main B already reflects its old 3.
        if not serviced and stage == 0:
            pair = ((provider(1, 0 if self.saturated_source else 2), None)
                    if name == 'original' else (provider(0, 1), None))
        elif self.name == 'resident-only':
            pair = (provider(1, 0), None) if name == 'original' else (provider(0, 1), None)
        elif stage == 1 and serviced:
            pair = (provider(0, 1), provider(1, 6)) if name == 'original' else (None, None)
        else:
            pair = (None, provider(1, 6)) if name == 'original' else (provider(0, 1), None)
        return main, pair

    def initial_profile(self, name):
        _, pair = self.profile(0, name, serviced=False)
        return (0, 0), pair


RESIDENT = ResidencyProgram('resident-only', 'BPU-INT-089', False, (
    Stage(('a-old-1', 'a-old-2'), (A_ONLY, A_ONLY),
          ((('a', 1), None), (('a', 1), None)),
          ((None, ('a', 1)), (None, ('a', 0))), (None, ('a', 0))),
    Stage(('a-old-3',), (A_ONLY,), ((('a', 1), None),),
          ((None, ('a', 0)),), (None, ('a', 0))),
))
REINSTALL = Stage(('b-old',), (PAIR,), ((None, ('b', 6)),),
                  ((None, ('b', 6)),), (None, ('b', 6)))
PROGRAMS = (RESIDENT,
    ResidencyProgram('evicted-clean-reinstall', 'BPU-INT-098', True, (REINSTALL,)),
    ResidencyProgram('evicted-pending-replace', 'BPU-INT-098', True, (
        Stage(('a-old-1', 'b-old'), (A_ONLY, PAIR),
              ((('a', 1), None), (None, ('b', 6))),
              ((None, ('a', 0)), (None, ('b', 6))), (None, ('b', 6)), 1),)),
    ResidencyProgram('sequential-old-reinstalls', 'BPU-INT-098', True, (
        REINSTALL, Stage(('a-old-1',), (A_ONLY,), ((('a', 1), None),),
                         ((('a', 1), None),), (('a', 1), None)),)),
)
