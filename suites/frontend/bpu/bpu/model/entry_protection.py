"""Original contribution and original contradiction at real instruction entries."""
from dataclasses import dataclass
from suites.frontend.bpu.bpu.model.early_opposition import FALLBACK
from suites.frontend.bpu.bpu.model.block_entry_learning import PROGRAMS as ENTRIES
from suites.frontend.bpu.bpu.coverage.early_opposition import RULES as BASE_RULES

# At each round a real recovery discards the stale held lookup. A single
# redirect-bubble request warms the real lookup, then one valid original is
# accepted and fully drained. Five rounds allocate NT3, apply the three normal
# decrements and deliver fresh NT0 without letting an older no-hit snapshot
# allocate the longer table. Do not switch to continuous flow at transient NT3.
INITIALIZATION_ROUNDS = 5
INITIALIZATION_REQUESTS_PER_ROUND = 2


@dataclass(frozen=True,slots=True)
class Program:
    entry: object
    mode: str
    @property
    def name(self): return self.entry.name+'.'+self.mode
    @property
    def pc(self): return self.entry.pc
    @property
    def fallback_pc(self): return (self.pc//16)*16+FALLBACK
    @property
    def recovery_offset(self): return self.fallback_pc-self.pc


PROGRAMS=tuple(Program(entry,mode) for entry in ENTRIES for mode in ('contribution','contradiction'))
PROFILES=tuple(p.name for p in PROGRAMS)
COMMON=('interior-short-original','complete-actual-reward-owner','later-public-source-and-original-preservation')
LOSS=('original-consistent-but-wrong','complete-actual-loss-owner','complete-new-actual-state-after-loss')


def program(name):
    try: return next(p for p in PROGRAMS if p.name==name)
    except StopIteration: raise ValueError('declared interior protection profile required') from None


def rules(name): return (*BASE_RULES,*COMMON,*(LOSS if program(name).mode=='contradiction' else ()))
