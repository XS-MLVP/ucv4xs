"""Two real control-flow blocks and two independent source admission conditions."""
from dataclasses import dataclass


@dataclass(frozen=True,slots=True)
class Program:
    entry: str
    flowing: bool
    a: int=0x40000103
    @property
    def b(self): return 0x40000001 if self.entry=='compressed-entry' else 0x40000002
    @property
    def name(self): return self.entry+'.'+('flowing-feedback' if self.flowing else 'held-feedback')
    def resolution(self,phase):
        return {'predecessor':(self.a,4,self.b,2,True),
            'conditional':(self.b,2,self.a,1,True),
            'not-taken':(self.b,2,self.a,1,False),
            'fallback':(self.b,4,self.a,2,True)}[phase]


PROGRAMS=tuple(Program(entry,flowing) for entry in ('compressed-entry','conditional-entry') for flowing in (False,True))
PROFILES=tuple(p.name for p in PROGRAMS)
RULES=('two-cold-originals','both-real-early-edges','original-not-taken-feedback',
    'new-later-direct-discovery','held-or-flowing-acceptance','original-fasttrain-owned',
    'cross-block-short-allocation','next-full-actual-protection',
    'fresh-cross-block-short-consumer','all-originals-immutable')


def program(name):
    try: return next(p for p in PROGRAMS if p.name==name)
    except StopIteration: raise ValueError('declared cross-block program required') from None
