"""Learning belongs to logical history paths and distinct original queries."""
from dataclasses import asdict, dataclass

from bpuverify.utage.model.semantic import Context, indices, tag
from bpuverify.utage.model.usefulness_events import ProtectionState

PC, POSITION = 0x40000000, 5
HISTORIES = dict(a=0x20, b=0xA0, fallback=0x60, cold=0x28)
MODES = ('serial', 'adjacent')
RULES = ('prepared-distinct-long-paths', 'actual-overlapping-sources', 'unique-feedback-once',
         'actual-feedback-cadence', 'independent-cumulative-learning', 'opposed-boundary-holds',
         'reverse-from-boundaries', 'shared-short-fallback', 'cold-neighbor-isolation',
         'immutable-original-sources')
SATURATION = tuple((path, int(path=='b')) for _ in range(3) for path in ('a','b'))
RECOVERY = (('b',1),('a',0),('a',1),('b',0))
PHASES = {'independent-cumulative-learning':SATURATION,
          'opposed-boundary-holds':RECOVERY[:2], 'reverse-from-boundaries':RECOVERY[2:]}


def address(path):
    return indices(PC, Context.from_recent(HISTORIES[path]))


def expected(path, base, *, table=1, counter=None):
    fields = dict(indices=address(path), folds=Context.from_recent(HISTORIES[path]).folds,
                  valid=(1,0,0,0), positions=(5,6,7,8), base=base, strong=0, hit=int(counter is not None))
    if counter is not None:
        fields.update(provider=table,counter=counter,taken=int(counter>=4),predicted=int(counter>=4))
    return fields


@dataclass(frozen=True, slots=True)
class Source:
    owner: int
    path: str
    counter: int
    base: int


@dataclass(frozen=True, slots=True)
class Learning:
    source: Source
    actual: int
    before: ProtectionState
    after: ProtectionState


class LongHistoryLearning:
    """The declared seed is established separately through normal public input."""
    def __init__(self):
        self.states = dict(a=ProtectionState(3,2), b=ProtectionState(4,2))
        self.sources, self.consumed = {}, set()
        shared = {address(p)[0] for p in ('a','b','fallback')}
        if len(shared)!=1 or len({address(p)[1] for p in HISTORIES})!=4:
            raise ValueError('shared short path and distinct long/cold paths required')
        if address('cold')[0] in shared:
            raise ValueError('cold neighbor must have its own short identity')
        if any(tag(PC,Context.from_recent(h),t)>=256 for h in HISTORIES.values() for t in (0,1)):
            raise ValueError('this program must not depend on the known high-tag defect')

    def capture(self, owner, path, base):
        if type(owner) is not int or owner<0 or owner in self.sources:
            raise ValueError('each actual prediction acceptance is a distinct source')
        if path not in self.states or type(base) is not int or base not in (0,1):
            raise ValueError('owned long path and semantic base direction required')
        source = Source(owner,path,self.states[path].counter,base)
        self.sources[owner] = source
        return source

    def preview(self, batch):
        batch = tuple(batch); owners = [owner for owner,_ in batch]
        if not batch or len(set(owners))!=len(owners) or any(
                owner not in self.sources or owner in self.consumed for owner in owners):
            raise ValueError('feedback needs distinct, original, unconsumed predictions')
        states, events = dict(self.states), []
        for owner,actual in batch:
            if type(actual) is not int or actual not in (0,1):
                raise ValueError('semantic feedback direction must be a bit')
            source = self.sources[owner]; before = states[source.path]
            after = before.feedback(predicted=int(source.counter>=4),base=source.base,actual=actual)
            events.append(Learning(source,actual,before,after)); states[source.path] = after
        return tuple(events),states

    def commit(self, batch):
        batch = tuple(batch)
        events,states = self.preview(batch)
        self.states = states
        self.consumed.update(owner for owner,_ in batch)
        return events

    def state(self):
        return dict(histories=dict(HISTORIES),states={p:asdict(s) for p,s in self.states.items()},
                    sources=[asdict(s) for s in self.sources.values()],consumed=sorted(self.consumed))
