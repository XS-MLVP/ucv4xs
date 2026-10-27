"""Different older branches followed by the same recent fallback path."""
from dataclasses import dataclass
from bpuverify.bpu.model.early_opposition import FALLBACK
from bpuverify.bpu.model.block_entry_learning import PROGRAMS as ENTRIES
from bpuverify.bpu.model.entry_protection import rules as protection_rules
from bpuverify.bpu.model.path_history import SHIFT
from bpuverify.utage.model.semantic import HISTORIES


@dataclass(frozen=True,slots=True)
class Program:
    entry: object
    older: int
    @property
    def name(self): return self.entry.name+'.older-'+('conditional' if self.older==2 else 'fallback')
    @property
    def base_name(self): return self.entry.name+'.contradiction'
    @property
    def pc(self): return self.entry.pc
    @property
    def positions(self): return (self.older,)+(FALLBACK,)*((HISTORIES[0]+SHIFT-1)//SHIFT)


PROGRAMS=tuple(Program(entry,older) for entry in ENTRIES for older in (2,FALLBACK))
PROFILES=tuple(p.name for p in PROGRAMS)
EXTRA=('exact-recovery-read-ancestor','wrong-short-and-long-allocation-same-original',
    'long-allocation-next-actual-confirmed','fresh-long-consumer-and-priority',
    'short-state-preserved-during-long-learning','owned-path-prefix-and-recent-suffix',
    'same-short-distinct-older-history','fresh-short-counter-after-error','both-consumer-snapshots-immutable')


def program(name):
    try: return next(p for p in PROGRAMS if p.name==name)
    except StopIteration: raise ValueError('declared short revisit path required') from None


def rules(name): return (*protection_rules(program(name).base_name),*EXTRA)
