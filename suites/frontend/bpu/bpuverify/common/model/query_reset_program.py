"""Instruction lifetimes and source-qualified response dispositions, not pins."""
from dataclasses import asdict, dataclass

DUTS = ('mbtb', 'ubtb')
MODES = ('reset-after-launch', 'response-before-reset')
RULES = ('warm-originals', 'actual-old-query', 'old-response-disposition',
         'new-epoch-cold', 'new-owned-learning', 'immutable-originals')


@dataclass(frozen=True)
class Branch:
    pc: int
    target: int
    position: int
    kind: int
    action: int = 0


@dataclass(frozen=True)
class Program:
    dut: str
    mode: str

    def __post_init__(self):
        if self.dut not in DUTS or self.mode not in MODES:
            raise ValueError('declared predictor and query/reset relation required')

    @property
    def old(self):
        if self.dut == 'mbtb':
            return (Branch(0x40000800, 0x40001234, 2, 1),
                    Branch(0x40000800, 0x40003456, 10, 3),
                    Branch(0x40000880, 0x40005678, 5, 2))
        return (Branch(0x40001000, 0x40002000, 3, 1),
                Branch(0x40001080, 0x40003000, 5, 3, 2))

    @property
    def new(self):
        original, neighbor = self.old[0], self.old[-1]
        return (Branch(original.pc, 0x40007800, 4, 3),
                Branch(neighbor.pc, 0x40008a00, 9, 2))

    @property
    def disposition(self):
        # This is a protocol hypothesis, not selected from DUT behavior:
        # MainBTB's previous-read response is terminated by the next reset
        # boundary; MicroBTB responds at the accepted semantic lookup itself.
        return 'reset-ended' if self.dut == 'mbtb' and self.mode == 'reset-after-launch' else 'responded'

    def state(self):
        return dict(dut=self.dut, mode=self.mode, disposition=self.disposition,
                    old=[asdict(b) for b in self.old], new=[asdict(b) for b in self.new])
