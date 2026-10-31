"""Declared logical protection programs; no DUT data or native dependencies."""
from dataclasses import asdict, dataclass

RULES = ('reward', 'penalty', 'upper-hold', 'lower-hold',
         'reverse-from-upper', 'reverse-from-lower',
         'base-agreement-interior', 'base-agreement-upper', 'base-agreement-lower')
MODES = ('serial', 'adjacent')
PC, POSITION, HISTORY = 0x40000000, 5, 0xA6B
NEIGHBOR_HISTORY = HISTORY ^ 0x15
SHORT_CONSUMER_HISTORY = HISTORY ^ 0x40


@dataclass(frozen=True, slots=True)
class ProtectionState:
    counter: int
    useful: int

    def __post_init__(self):
        if type(self.counter) is not int or not 0 <= self.counter <= 7:
            raise ValueError('direction confidence must be in 0..7')
        if type(self.useful) is not int or not 0 <= self.useful <= 3:
            raise ValueError('replacement protection must be in 0..3')

    @property
    def taken(self):
        return int(self.counter >= 4)

    def feedback(self, *, predicted, base, actual):
        if any(type(bit) is not int or bit not in (0, 1) for bit in (predicted, base, actual)):
            raise ValueError('logical feedback directions must be integer bits')
        delta = 0 if predicted == base == actual else 1 if predicted == actual else -1
        return ProtectionState(max(0, min(7, self.counter + (1 if actual else -1))),
                               max(0, min(3, self.useful + delta)))


@dataclass(frozen=True, slots=True)
class UsefulnessProgram:
    table: int
    rule: str
    mode: str = 'serial'

    def __post_init__(self):
        if type(self.table) is not int or self.table not in (0, 1):
            raise ValueError('provider must be the short or long table')
        if self.rule not in (*RULES, 'initial-protection') or self.mode not in MODES:
            raise ValueError('unknown protection event or communication mode')
        if self.rule == 'initial-protection' and self.mode != 'serial':
            raise ValueError('one allocation cannot demonstrate adjacent feedback')

    @property
    def initial(self):
        return ProtectionState(3 if self.table == 0 else 4, self.table + 1)

    @property
    def preparation(self):
        if self.rule in ('upper-hold', 'reverse-from-upper', 'base-agreement-upper'):
            return 3 - self.initial.useful, self.initial.taken
        if self.rule in ('lower-hold', 'reverse-from-lower', 'base-agreement-lower'):
            return self.initial.useful, 1 - self.initial.taken
        return 0, self.initial.taken

    @property
    def prepared(self):
        count, actual = self.preparation
        state = self.initial
        for _ in range(count):
            state = state.feedback(predicted=self.initial.taken, base=1-self.initial.taken, actual=actual)
        return state

    @property
    def source(self):
        # Lower hold deliberately reuses a real older wrong-prediction source.
        # Its counter may have crossed the prediction threshold since capture.
        return self.initial if self.rule == 'lower-hold' else self.prepared

    @property
    def base(self):
        return self.source.taken if self.rule.startswith('base-agreement') else 1-self.source.taken

    @property
    def actual(self):
        return 1-self.source.taken if self.rule in ('penalty', 'lower-hold', 'reverse-from-upper') else self.source.taken

    @property
    def expected(self):
        if self.rule == 'initial-protection':
            return ()
        first = self.prepared.feedback(predicted=self.source.taken, base=self.base, actual=self.actual)
        second = first.feedback(predicted=self.source.taken, base=self.base, actual=self.actual)
        return first, second

    def state(self):
        return dict(program=asdict(self), initial=asdict(self.initial), prepared=asdict(self.prepared),
                    source=asdict(self.source), base=self.base, actual=self.actual,
                    expected=tuple(asdict(state) for state in self.expected))
