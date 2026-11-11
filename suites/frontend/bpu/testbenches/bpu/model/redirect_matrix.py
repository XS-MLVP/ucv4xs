"""Guard/sign/outcome/history classes and independent address-domain facts."""
from dataclasses import dataclass
from itertools import product


HISTORY_KINDS = ('empty', 'nonzero')


@dataclass(frozen=True, slots=True)
class RedirectCase:
    guard: int
    sign: int
    taken: int
    history: str

    def __post_init__(self):
        if any(type(v) is not int or v not in (0, 1) for v in (self.guard, self.sign, self.taken)) or self.history not in HISTORY_KINDS:
            raise ValueError('unknown guarded redirect class')

    @property
    def label(self):
        return f'guard{self.guard}.sign{self.sign}.taken{self.taken}.{self.history}'

    @property
    def pc(self):
        return (self.sign << 48) + 0x40000080

    @property
    def boot_pc(self):
        # resetVector is a physical address (PrunedAddr(PAddrBits)), NOT an
        # arbitrary virtual PC. Reach the tested virtual domain by redirect.
        return 0x40000000

    @property
    def cfi(self):
        return (self.guard << 49) + self.pc + 4

    @property
    def target(self):
        # Conditional NT is an explicit two-byte sequential successor, not
        # the taken target. Guard remains an isolated port-boundary pressure.
        return self.pc + (0x180 if self.taken else 5)

    @property
    def boundary(self):
        return dict(valid=1, cfi=self.cfi, common=self.pc + 4, phr=self.cfi)

    def next_history(self, original):
        if not self.taken:
            return original
        contribution = (16 * ((self.pc + 4) % 512)) ^ ((self.target // 2) % 32768)
        return ((original * 4) ^ contribution) % (1 << 532)


REDIRECT_CASES = tuple(RedirectCase(*v) for v in product((0, 1), (0, 1), (0, 1), HISTORY_KINDS))
