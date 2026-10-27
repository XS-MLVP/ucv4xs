"""Two recovery outcomes ordered by surviving instruction age, not signals."""
from dataclasses import dataclass

from bpuverify.bpu.model.common_history import Value
from bpuverify.bpu.model.selection import Branch, Kind

PC = 0x40000800
FORWARD, BACKWARD = PC + 0x200, PC - 0x200
PROFILES = ('older-not-taken', 'older-forward-taken', 'older-backward-taken',
            'older-direct-after-prefix')
RULES = ('two-distinct-published-originals', 'older-source-survives-first-cancellation',
         'adjacent-actual-recovery-acceptance', 'complete-original-payloads',
         'both-intermediate-and-final-history-checked', 'older-prefix-and-iteration-win',
         'fresh-winner-consumer', 'originals-remain-immutable')


@dataclass(frozen=True, slots=True)
class SupersedingRecoveryProgram:
    profile: str

    def __post_init__(self):
        if self.profile not in PROFILES:
            raise ValueError('declared superseding recovery outcome required')

    @property
    def younger(self):
        return (Branch(1, FORWARD, Kind.CONDITIONAL) if self.profile == 'older-backward-taken'
                else Branch(1, PC, Kind.CONDITIONAL))

    @property
    def older(self):
        return {
            'older-not-taken': Branch(1, PC + 3, Kind.CONDITIONAL, False),
            'older-forward-taken': Branch(1, FORWARD, Kind.CONDITIONAL),
            'older-backward-taken': Branch(1, BACKWARD, Kind.CONDITIONAL),
            'older-direct-after-prefix': Branch(5, FORWARD, Kind.DIRECT),
        }[self.profile]

    @property
    def consumer_pc(self):
        return BACKWARD if self.profile == 'older-backward-taken' else FORWARD

    @property
    def intermediate(self):
        return Value(False, 255, 14 if self.profile == 'older-backward-taken' else 15)

    @property
    def restored(self):
        return {'older-not-taken': Value(False, 254, 14),
                'older-forward-taken': Value(False, 255, 14),
                'older-backward-taken': Value(False, 255, 15),
                'older-direct-after-prefix': Value(False, 254, 14)}[self.profile]

    def iteration(self, original_count, *, younger=False):
        if type(original_count) is not int or not 0 < original_count < 255:
            raise ValueError('a distinct nonsaturated original iteration is required')
        backward = self.profile != 'older-backward-taken' if younger else self.profile == 'older-backward-taken'
        return original_count + 1 if backward else 0

    def state(self):
        return dict(profile=self.profile, original_common=(255, 15),
                    acceptance_order=('younger', 'older'), physical_enumeration=False,
                    full_FTQ_lifetime_proved=False)
