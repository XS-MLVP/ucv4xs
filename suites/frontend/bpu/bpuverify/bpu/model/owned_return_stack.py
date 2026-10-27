"""Human requirements for source-owned calls, returns, recovery and commit."""
from dataclasses import dataclass

CALL, RETURN, STATIC_TARGET, POSITION = 0x40001000, 0x40002000, 0x40002900, 2
CONTINUATION = CALL + POSITION + 1
MODES = ('natural-return','call-replay','return-replay')
COMMON_RULES = ('learned-instructions-own-their-originals','call-retains-own-return-address',
    'return-consumes-matching-call','live-operations-retire-once',
    'committed-sentinel-restored','original-metadata-preserved')


@dataclass(frozen=True, slots=True)
class OwnedReturnProgram:
    mode: str
    micro: bool

    def __post_init__(self):
        if self.mode not in MODES or type(self.micro) is not bool:
            raise ValueError('declared call/return lifetime and early-predictor choice required')

    @property
    def label(self):
        return self.mode+('.micro-main' if self.micro else '.main')

    @property
    def rules(self):
        return COMMON_RULES + ({
            'natural-return': (),
            'call-replay': ('recovery-replays-only-owned-call','younger-return-is-cancelled'),
            'return-replay': ('recovery-replays-only-owned-return','replayed-return-retires-once'),
        }[self.mode])


PROGRAMS = tuple(OwnedReturnProgram(mode,micro) for mode in MODES for micro in (False,True))
OBLIGATIONS = tuple(p.label+'.'+r for p in PROGRAMS for r in p.rules)
