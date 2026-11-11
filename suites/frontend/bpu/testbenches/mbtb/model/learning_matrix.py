"""Input-owned branch facts for payload and delayed-victim experiments.

This is a small property oracle alongside MbtbReference, not another timed
predictor. A resolved conditional NT carries its sequential successor, whereas
a prediction record owns a taken target. An incorrect prediction may also have
the wrong instruction type (IFU PredChecker / BranchUnit producer contracts).
"""
from dataclasses import dataclass
from itertools import product


PAYLOAD_KINDS = ('cold-nt', 'conditional-nt', 'reclassified-nt', 'false-hit')
TARGET_REGIONS = ('lower', 'same', 'upper')
RESIDENCY_KINDS = ('resident', 'evicted')


@dataclass(frozen=True, slots=True)
class PayloadCase:
    mode: str
    alignment: int
    position: int
    region: str

    def __post_init__(self):
        if self.mode not in PAYLOAD_KINDS or type(self.alignment) is not int or self.alignment not in (0, 1) or type(self.position) is not int or self.position not in (1, 15) or self.region not in TARGET_REGIONS:
            raise ValueError('unknown payload matrix class')

    @property
    def label(self):
        return f'{self.mode}.align{self.alignment}.pos{self.position}.{self.region}'

    @property
    def coverage_label(self):
        # Preserve collected nodeids, but do NOT inflate semantic bins with a
        # non-existent old target. Cold region aliases are redundant controls.
        if self.mode == 'cold-nt':
            return f'{self.mode}.align{self.alignment}.pos{self.position}.no-original-target'
        return self.label

    @property
    def pc(self):
        return 0x40000800 + 16 * self.alignment

    @property
    def target(self):
        return (self.pc // (1 << 20) + TARGET_REGIONS.index(self.region) - 1) * (1 << 20) + 0x1234

    @property
    def initial_kind(self):
        return {'cold-nt': None, 'conditional-nt': 1, 'reclassified-nt': 3, 'false-hit': 3}[self.mode]

    @property
    def resolved_kind(self):
        return 0 if self.mode == 'false-hit' else 1

    @property
    def successor(self):
        # An explicitly compressed instruction ends at this halfword position.
        return self.pc + self.position + 1

    @property
    def wanted(self):
        if self.mode in ('cold-nt', 'false-hit'):
            return ()
        # Actual conditional NT is authoritative about direction, not the
        # stale prediction type. Its owned counter weakens 2->1 in BOTH warm
        # modes, while reclassified NT still retains its indirect payload.
        return ((self.position, self.initial_kind, 0, self.target, 0, 1),)


PAYLOAD_CASES = tuple(PayloadCase(*values) for values in product(PAYLOAD_KINDS, (0, 1), (1, 15), TARGET_REGIONS))


@dataclass(frozen=True, slots=True)
class ResidencyCase:
    mode: str
    alignment: int

    def __post_init__(self):
        if self.mode not in RESIDENCY_KINDS or type(self.alignment) is not int or self.alignment not in (0, 1):
            raise ValueError('unknown victim residency class')

    @property
    def label(self):
        return f'{self.mode}.align{self.alignment}'

    @property
    def pc(self):
        return 0x40000800 + self.alignment * 16

    @property
    def target(self):
        return self.pc + 0x456

    @property
    def pressure(self):
        # Different rows, same physical alignment/bank, avoid replacing Main
        # residents of the source window. Six normal discoveries insert two
        # victim records per row, exceeding the 16-record victim capacity.
        return tuple(self.pc + row * 0x80 for row in range(1, 17)) if self.mode == 'evicted' else ()

    @property
    def destination(self):
        return 'victim' if self.mode == 'resident' else 'main'


RESIDENCY_CASES = tuple(ResidencyCase(*values) for values in product(RESIDENCY_KINDS, (0, 1)))
