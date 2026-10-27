"""Real two-block paths and late teaching of one earlier conditional original."""
from dataclasses import dataclass
from bpuverify.bpu.model.path_history import SHIFT,path_contribution
from bpuverify.tage.model.semantic import HISTORIES
from bpuverify.bpu.model.direction_sources import candidates


@dataclass(frozen=True,slots=True)
class Program:
    entry: str
    flowing: bool
    a: int=0x40000103
    @property
    def b(self): return 0x40000001 if self.entry=='compressed-entry' else 0x40000002
    @property
    def name(self): return self.entry+'.'+('flowing-repair' if self.flowing else 'held-repair')
    @property
    def recovery_offset(self): return (self.a//8)*8+4-self.a
    @property
    def stable_predecessor_history(self):
        edge=(path_contribution((self.a//8)*8+4,self.b)<<SHIFT)^path_contribution((self.b//8)*8+4,self.a)
        value=0
        for bit in range(0,max(HISTORIES),2*SHIFT): value^=edge<<bit
        return value%(1<<max(HISTORIES))
    def resolution(self,phase):
        return {'predecessor':(self.a,4,self.b,2,True,True),
            'conditional':(self.b,2,self.a,1,True,True),
            'not-taken':(self.b,2,self.a,1,False,True),
            'strengthen-negative':(self.b,2,self.a,1,False,False),
            'fallback':(self.b,4,self.a,2,True,True),
            'late-surprise':(self.b,2,self.a,1,True,True)}[phase]


PROGRAMS=tuple(Program(entry,flowing) for entry in ('compressed-entry','conditional-entry') for flowing in (False,True))
PROFILES=tuple(p.name for p in PROGRAMS)
RULES=('two-real-cold-edges','owned-early-taken-source','stable-later-path-original',
    'independent-weak-late-provider','exact-original-S3-correction',
    'held-or-flowing-original-teaching','younger-squash-cannot-teach',
    'named-short-learning-effect','next-full-actual-confirmation',
    'fresh-original-negative-consumer','all-snapshot-domains-immutable')


def program(name):
    try: return next(p for p in PROGRAMS if p.name==name)
    except StopIteration: raise ValueError('declared late-correction original program required') from None


def conditional_slot(token):
    return next((slot for slot,branch in enumerate(candidates(token)[0])
        if branch is not None and branch.position==2 and int(branch.kind)==1),None)


def weak_late_alternate(sources,token):
    slot=conditional_slot(token)
    if slot is None: return False
    _,wanted,late=sources.tage_decision(token)
    return (bool(wanted.get(f'{slot}.has_provider')) and wanted.get(f'{slot}.counter')==4
        and not wanted.get(f'{slot}.use_provider') and bool(wanted.get(f'{slot}.fast_taken'))
        and not wanted.get(f'{slot}.taken') and late.branch.position==4)
