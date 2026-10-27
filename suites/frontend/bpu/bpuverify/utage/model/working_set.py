"""History-owned learning across cache turnover, independent of DUT signals.

The capacity workload intentionally fills the promised long-history capacity.
It is one linear logical lifetime, not a bank/set/scenario cross-product.
"""
from dataclasses import asdict, dataclass

from bpuverify.utage.model.semantic import Context, SETS, indices
from bpuverify.utage.model.usefulness_events import ProtectionState

PC, SHORT_POSITION, POSITION = 0x40000000, 5, 6
MODES = ('serial', 'adjacent')
SIZES = {'turnover': 32, 'capacity': SETS}
PHASES = ('admit-distinct-histories', 'reward-after-turnover', 'reward-at-boundary',
          'base-agreement', 'selective-penalty', 'selective-recovery')
RULES = (*PHASES, 'actual-query-overlap', 'actual-feedback-cadence',
         'late-retained-consumers', 'immutable-original-sources')


@dataclass(frozen=True, slots=True)
class WorkingSetProgram:
    size: str
    mode: str

    def __post_init__(self):
        if self.size not in SIZES or self.mode not in MODES:
            raise ValueError('unknown logical working set or communication mode')

    @property
    def histories(self):
        # Gray order describes a changing branch history, not native row gaps.
        return tuple(number ^ (number >> 1) for number in range(SIZES[self.size]))

    @property
    def short_histories(self):
        return tuple(sorted({history & 31 for history in self.histories}))

    @property
    def selected(self):
        # Bound allocation failures below the separate global-aging contract.
        return self.histories[::4][:96]

    def order(self, phase):
        if phase not in PHASES:
            raise ValueError('unknown working-set phase')
        histories = self.selected if phase.startswith('selective-') else self.histories
        return tuple(reversed(histories)) if PHASES.index(phase) % 2 else histories

    @staticmethod
    def base(phase):
        return int(phase == 'base-agreement')

    @staticmethod
    def actual(phase):
        return int(phase != 'selective-penalty')


def address(history):
    return indices(PC, Context.from_recent(history))


def expected(history, base, state=None, *, table=1, position=POSITION):
    fields = dict(indices=address(history), folds=Context.from_recent(history).folds,
        valid=(1, 0, 0, 0), positions=tuple(position + offset for offset in range(4)),
        base=base, strong=0, hit=int(state is not None))
    if state is not None:
        fields.update(provider=table, counter=state.counter, taken=state.taken, predicted=state.taken)
    return fields


@dataclass(frozen=True, slots=True)
class Source:
    owner: int
    phase: str
    history: int
    base: int
    state: ProtectionState | None


class WorkingSetReference:
    """Only declared source identities and outcomes advance semantic state.

    Short prerequisites (counter4, protection1) are established through actual
    public feedback before the first long admission, never from an actual read.
    """
    def __init__(self, program):
        self.program = program
        self.states, self.sources, self.consumed = {}, {}, set()
        self.phase = 0

    def capture(self, owner, phase, history):
        if type(owner) is not int or owner < 0 or owner in self.sources:
            raise ValueError('each original query must have a unique actual acceptance')
        if self.phase >= len(PHASES) or phase != PHASES[self.phase] or history not in self.program.order(phase):
            raise ValueError('source must belong to the next declared logical phase')
        source = Source(owner, phase, history, self.program.base(phase), self.states.get(history))
        self.sources[owner] = source
        return source

    def preview(self, phase, owners):
        owners = tuple(owners)
        if self.phase >= len(PHASES) or phase != PHASES[self.phase]:
            raise ValueError('working-set phases cannot be skipped or replayed')
        if len(set(owners)) != len(owners) or any(owner not in self.sources or owner in self.consumed for owner in owners):
            raise ValueError('feedback needs distinct original unconsumed sources')
        sources = tuple(self.sources[owner] for owner in owners)
        if tuple(source.history for source in sources) != self.program.order(phase) or any(
                source.phase != phase for source in sources):
            raise ValueError('every declared history must receive exactly its ordered feedback')
        states = dict(self.states)
        for source in sources:
            if phase == PHASES[0]:
                if source.state is not None:
                    raise ValueError('new long identity must be cold')
                states[source.history] = ProtectionState(4, 2)
            else:
                if source.state != states[source.history]:
                    raise ValueError('each phase requires fresh owned learning metadata')
                states[source.history] = source.state.feedback(predicted=source.state.taken,
                    base=source.base, actual=self.program.actual(phase))
        return states

    def commit(self, phase, owners):
        owners = tuple(owners)
        states = self.preview(phase, owners)
        self.states = states
        self.consumed.update(owners)
        self.phase += 1

    def values(self, states=None):
        values = [0] * (2 * SETS)
        for history in self.program.short_histories:
            values[address(history)[0]] = 1
        for history, state in (self.states if states is None else states).items():
            values[SETS + address(history)[1]] = state.useful
        return tuple(values)

    def state(self):
        return dict(program=asdict(self.program), phase=self.phase,
                    states={history: asdict(state) for history, state in self.states.items()},
                    sources=len(self.sources), consumed=sorted(self.consumed))
