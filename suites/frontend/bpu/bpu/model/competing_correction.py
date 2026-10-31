"""Two real blocks: old late direction versus newly discovered young branch."""
from dataclasses import dataclass
from suites.frontend.bpu.bpu.model.late_correction_learning import Program as LateProgram
from suites.frontend.bpu.bpu.model.path_history import WIDTH,SHIFT,path_contribution
from suites.frontend.bpu.tage.model.semantic import HISTORIES


PHASES=('predecessor','conditional','not-taken','strengthen-negative','fallback','late-surprise','young-discovery')
RULES=('real-old-early-and-late-experience','old-lookup-held-before-young-discovery',
    'young-branch-discovered-from-real-original','exact-old-S1-acceptance','exact-young-S1-acceptance',
    'both-corrections-same-boundary','old-path-wins-distinct-history','young-snapshots-released',
    'next-full-actual-restoration','original-short-learning','next-full-actual-learning',
    'new-restored-history-consumer','all-original-snapshots-immutable')


@dataclass(frozen=True,slots=True)
class Program(LateProgram):
    # A starts at halfword3: a normal conditional occupies3/4, NOP5,
    # then direct6 occupies6/7. These instructions do not overlap.
    @property
    def name(self): return self.entry+'.'+('flowing-competition' if self.flowing else 'held-competition')
    @property
    def predecessor_position(self): return 6
    @property
    def recovery_offset(self): return (self.a//8)*8+self.predecessor_position-self.a
    @property
    def stable_predecessor_history(self):
        edge=(path_contribution((self.a//8)*8+self.predecessor_position,self.b)<<SHIFT)^path_contribution((self.b//8)*8+4,self.a)
        return self._fixed(edge)
    @staticmethod
    def _fixed(edge):
        value=0
        for bit in range(0,max(HISTORIES),2*SHIFT): value^=edge<<bit
        return value%(1<<max(HISTORIES))
    def resolution(self,phase):
        if phase=='predecessor': return self.a,6,self.b,2,True,True
        if phase=='young-discovery': return self.a,3,self.b,1,True,True
        return LateProgram.resolution(self,phase)


PROGRAMS=tuple(Program(entry,flowing) for entry in ('compressed-entry','conditional-entry') for flowing in (False,True))
PROFILES=tuple(p.name for p in PROGRAMS)


def program(name):
    try: return next(p for p in PROGRAMS if p.name==name)
    except StopIteration: raise ValueError('declared competing correction program required') from None


def restored(token,branch):
    if not branch.taken: return token.history.history
    pc=(token.pc//8)*8+branch.position
    return ((token.history.history<<SHIFT)^path_contribution(pc,branch.target))%(1<<WIDTH)
