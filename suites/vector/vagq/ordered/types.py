"""Domain transactions for the eight-entry ordered-load permit protocol."""
from dataclasses import dataclass

NUM_ENTRIES = 8
UOP_MAX = 8
ROB_MAX = 1 << 9


@dataclass(frozen=True, slots=True)
class Entry:
    valid: bool = False
    uop_type: int = 0
    rob_flag: int = 0
    rob_value: int = 0
    uop_idx: int = 0
    last_uop: bool = False
    exception: bool = False
    state: int = 0

    def __post_init__(self):
        if self.uop_type < 0 or self.uop_type >= 8:
            raise ValueError('uop_type must fit the three-bit VAGQ encoding')
        if self.rob_flag not in (0, 1) or not 0 <= self.rob_value < ROB_MAX:
            raise ValueError('ROB pointer outside the 10-bit circular encoding')
        if not 0 <= self.uop_idx < UOP_MAX or not 0 <= self.state < 8:
            raise ValueError('entry uop/state outside the RTL encoding')

    @property
    def is_load(self):
        return not (self.uop_type & 1)

    @property
    def is_ordered(self):
        return bool(self.uop_type & 2)

    @property
    def is_ordered_load(self):
        return self.is_ordered and self.is_load


@dataclass(frozen=True, slots=True)
class SplitDone:
    valid: bool = False
    entry_idx: int = 0

    def __post_init__(self):
        if not 0 <= self.entry_idx < NUM_ENTRIES:
            raise ValueError('split-done entry index outside the eight-entry table')


@dataclass(frozen=True, slots=True)
class Redirect:
    valid: bool = False
    level: int = 0
    rob_flag: int = 0
    rob_value: int = 0

    def __post_init__(self):
        if self.level not in (0, 1) or self.rob_flag not in (0, 1):
            raise ValueError('redirect flags must be one-bit values')
        if not 0 <= self.rob_value < ROB_MAX:
            raise ValueError('redirect ROB value outside the nine-bit encoding')


@dataclass(frozen=True, slots=True)
class Beat:
    entries: tuple[Entry, ...] = (Entry(),) * NUM_ENTRIES
    split_done: SplitDone = SplitDone()
    redirect: Redirect = Redirect()

    def __post_init__(self):
        if not isinstance(self.entries, tuple) or len(self.entries) != NUM_ENTRIES:
            raise ValueError('a beat must describe all eight physical entries')
        if any(not isinstance(entry, Entry) for entry in self.entries):
            raise TypeError('entries must contain Entry domain values')


@dataclass(frozen=True, slots=True)
class Permit:
    rob_flag: int
    rob_value: int
    uop_idx: int

    def __post_init__(self):
        if self.rob_flag not in (0, 1) or not 0 <= self.rob_value < ROB_MAX:
            raise ValueError('permit ROB pointer outside encoding')
        if not 0 <= self.uop_idx < UOP_MAX:
            raise ValueError('permit uop index outside encoding')


@dataclass(frozen=True, slots=True)
class Observation:
    ordered_can_proceed: tuple[bool, ...]

    def __post_init__(self):
        if len(self.ordered_can_proceed) != NUM_ENTRIES:
            raise ValueError('observation must contain eight proceed bits')
