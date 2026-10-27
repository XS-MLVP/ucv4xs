"""Original-source protection events, without clocks, pins or RTL controls."""
from dataclasses import dataclass

from bpuverify.utage.model.semantic import tag


EDGES = {
    'upper-hold': (('upper-hold', 'reward', 3, 3),),
    'upper-release': (('upper-hold', 'reward', 3, 3), ('upper-release', 'penalty', 3, 2)),
    'lower-recover': (('toward-lower', 'penalty', 2, 1), ('reach-lower', 'penalty', 1, 0),
                      ('lower-hold', 'penalty', 0, 0), ('lower-recover', 'reward', 0, 1)),
}
COMMON = ('stable-original', 'other-history-isolation', 'source-qualified-boundary',
          'complete-actual-state-confirmed', 'fresh-original-consumer', 'original-snapshots-immutable')


def rules(mode, *, edges=EDGES):
    return COMMON + tuple(edge[0] for edge in edges[mode])


def next_edge(mode, confirmed, event, *, edges=EDGES):
    """A later recovery cannot be credited before the declared boundary hold."""
    wanted = next((edge for edge in edges[mode] if edge[0] not in confirmed), None)
    if wanted is not None and (event.kind, event.before, event.after) == wanted[1:]:
        return wanted[0]
    return None


@dataclass(frozen=True, slots=True)
class Identity:
    table: int
    index: int
    tag: int
    position: int

    @property
    def key(self):
        return self.table, self.index


def guidance(feedback, identity):
    """The executed original conditional, not a sampled increase/decrease bit."""
    if (feedback.indices[identity.table] != identity.index
            or tag(feedback.pc, feedback.context, identity.table) != identity.tag):
        return None
    for source in feedback.sources:
        if (source.valid and source.hit and source.provider == identity.table
                and source.position == identity.position and source.position <= feedback.position
                and (source.position < feedback.position or feedback.kind == 1)):
            actual = bool(source.position == feedback.position and feedback.taken)
            kind = ('penalty' if source.predicted != actual else
                    'reward' if source.base != source.predicted else 'neutral')
            return actual, kind
    return None


@dataclass(frozen=True, slots=True)
class ProtectionEvent:
    owner: int
    kind: str
    before: int
    after: int
    counter_before: int
    counter_after: int


class ProtectionLedger:
    """Logical strength changes only for distinct, qualified original sources."""
    def __init__(self, *, counter=0, protection=2):
        if (type(counter) is not int or not 0 <= counter <= 7
                or type(protection) is not int or not 0 <= protection <= 3):
            raise ValueError('defined direction/protection strength required')
        self.counter, self.protection = counter, protection
        self.owners = set()

    def apply(self, owner, actual, kind):
        if type(owner) is not int or owner < 0:
            raise ValueError('an original nonnegative source identity is required')
        if owner in self.owners:
            raise ValueError('one original guidance source cannot learn twice')
        if type(actual) is not bool or kind not in ('reward', 'penalty', 'neutral'):
            raise ValueError('qualified semantic guidance required')
        before, counter_before = self.protection, self.counter
        delta = 1 if kind == 'reward' else -1 if kind == 'penalty' else 0
        self.protection = max(0, min(3, before + delta))
        self.counter = max(0, min(7, counter_before + (1 if actual else -1)))
        self.owners.add(owner)
        return ProtectionEvent(owner, kind, before, self.protection, counter_before, self.counter)
