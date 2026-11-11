"""Expected SRAM bits whose values are justified by declared write history."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnownWord:
    value: int
    mask: int

    def checked_pair(self, actual):
        return self.value & self.mask, actual & self.mask
