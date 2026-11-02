"""No ready/valid, reset or invented hardware identity on this combinational DUT."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DecodeRequest:
    word: int
    fs_is_off: bool = False

    def __post_init__(self):
        if not isinstance(self.word, int) or not 0 <= self.word < (1 << 32):
            raise ValueError('instruction word must be an unsigned 32-bit value')
        if not isinstance(self.fs_is_off, int) or self.fs_is_off not in (0, 1):
            raise ValueError('fs_is_off must be boolean')


@dataclass(frozen=True)
class Decoded:
    bits: int
    ill: bool

    def __post_init__(self):
        if not isinstance(self.bits, int) or not 0 <= self.bits < (1 << 32):
            raise ValueError('decoded bits must be an unsigned 32-bit value')
        if not isinstance(self.ill, int) or self.ill not in (0, 1):
            raise ValueError('decoded ill must be boolean')


@dataclass(frozen=True)
class CheckedDecode:
    sequence: int  # Local evaluation slot, not a DUT response tag.
    sample_tick: int
    result: Decoded


IDLE = DecodeRequest(0x00000013)  # A defined, full-width architectural NOP.
