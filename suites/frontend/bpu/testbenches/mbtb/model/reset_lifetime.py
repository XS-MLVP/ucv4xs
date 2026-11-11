"""Logical old/new instruction lifetimes; no physical coordinates or DUT state."""
from dataclasses import asdict, dataclass

PROFILES = ('committed', 'registered-feedback', 'registered-direction', 'registered-retarget')
RULES = ('distinct-old-residents', 'old-learning-stage-proved', 'post-reset-cold',
         'no-delayed-old-replay', 'new-owned-learning', 'immutable-old-sources')


@dataclass(frozen=True)
class Branch:
    name: str
    pc: int
    target: int
    position: int
    kind: int


@dataclass(frozen=True)
class Program:
    profile: str

    def __post_init__(self):
        if self.profile not in PROFILES:
            raise ValueError('unknown reset lifetime profile')

    @property
    def old(self):
        pc = 0x40000800
        return (Branch('old-conditional', pc, 0x40001234, 2, 1),
                Branch('old-indirect', pc, 0x40003456, 10, 3),
                Branch('old-neighbor', pc + 0x80, 0x40005678, 9, 2))

    @property
    def pending(self):
        return Branch('old-unfinished', self.old[0].pc + 0x200, 0x4000789a, 5, 2)

    @property
    def new(self):
        return (Branch('new-conditional', self.old[0].pc, 0x40002340, 2, 1),
                Branch('new-neighbor', self.old[2].pc, 0x40006780, 9, 2))

    @property
    def old_pcs(self):
        return tuple(dict.fromkeys(branch.pc for branch in (*self.old, self.pending)))

    def state(self):
        return dict(profile=self.profile, old=[asdict(b) for b in self.old],
                    pending=asdict(self.pending), new=[asdict(b) for b in self.new])
