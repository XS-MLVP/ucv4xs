"""Instruction-entry meanings, not a bank/index coverage matrix."""
from dataclasses import dataclass
from suites.frontend.bpu.bpu.coverage.early_direction import RULES


@dataclass(frozen=True, slots=True)
class EntryProgram:
    name: str
    offset: int

    @property
    def pc(self): return 0x40000000+self.offset


PROGRAMS = (EntryProgram('compressed-entry',1), EntryProgram('conditional-entry',2))
PROFILES = tuple(p.name for p in PROGRAMS)


def program(name):
    try: return next(p for p in PROGRAMS if p.name == name)
    except StopIteration: raise ValueError('declared block-entry meaning required') from None
