"""A recovery declaration and closed-form execution-history expectation."""
from dataclasses import dataclass

from suites.frontend.bpu.bpu.model.path_history import WIDTH,path_contribution


@dataclass(frozen=True)
class RecoveryProgram:
    taken: int
    mode: str
    pc: int = 0x40000800

    def __post_init__(self):
        if type(self.taken) is not int or self.taken not in (0,1):raise ValueError('explicit actual direction required')
        if self.mode not in ('collision','after-repair'):raise ValueError('unknown actual arbitration window')

    @property
    def profile(self):return self.mode+('.taken' if self.taken else '.not-taken')

    @property
    def micro_target(self):return self.pc+0x200

    @property
    def backend_pc(self):return self.pc+16

    @property
    def entry_pc(self):return self.pc+32

    @property
    def target(self):return self.pc+0x900 if self.taken else self.backend_pc+16

    @property
    def cfi_pc(self):return self.backend_pc+4

    @property
    def winning_history(self):
        # The retained cold source independently belongs to reset history0.
        return path_contribution(self.cfi_pc,self.target) if self.taken else 0

    @property
    def expected_metadata(self):
        return dict(phrPtr=dict(flag=int(bool(self.taken)),value=WIDTH-2 if self.taken else 0),
                    phrLowBits=self.winning_history%8192)
