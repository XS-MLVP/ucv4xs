"""Read-priority service obligations from owned logical learning versions."""
from dataclasses import dataclass,field
from bpuverify.bpu.model.tage.forwarding import PC

STREAM_PC=PC+0x300
STREAM_POSITION=4
VIA_PC=PC+0x80
RETAINED_CAPACITY=4


@dataclass(frozen=True,slots=True)
class ServiceProgram:
    paths:tuple
    feedback_order:tuple

    def __post_init__(self):
        if type(self.paths) is not tuple or not 1<=len(self.paths)<=RETAINED_CAPACITY:
            raise ValueError('service program needs immutable histories within retained capacity')
        if any(path is not None and (
                type(path) is not int or not 0<=path<1<<49 or path%4!=PC%4) for path in self.paths) or len(set(self.paths))!=len(self.paths):
            raise ValueError('service paths must be distinct semantic PCs in the same read bank')
        if type(self.feedback_order) is not tuple or not self.feedback_order or any(
                type(index) is not int or not 0<=index<len(self.paths) for index in self.feedback_order):
            raise ValueError('feedback order must name immutable prepared history identities')
        if set(self.feedback_order)!=set(range(len(self.paths))):
            raise ValueError('every prepared history needs an accepted learning outcome')

    @property
    def history_count(self):return len(self.paths)

    @property
    def retained_histories(self):return tuple(range(self.history_count))

    @property
    def retained_count(self):return len(self.retained_histories)

    @property
    def initial_base(self):return (1,2)

    def initial_counters(self,history):return (2,5)

    def expected_counters(self,history):
        updates=self.feedback_order.count(history)
        return max(0,2-updates),min(7,5+updates)


READ_PRIORITY_PAIR=ServiceProgram((None,VIA_PC),(0,1,0,1))
# Four genuine paths, not four raw PC labels: +0x180 folds to A's history,
# whereas +0x200 supplies the fourth independently derived T3 row.
FULL_RETAINED_RETOUCH=ServiceProgram((None,VIA_PC,PC+0x100,PC+0x200),(0,1,2,3,0))


@dataclass(frozen=True,slots=True)
class FullReplacementProgram:
    """One capacity+1 boundary. The old saturated victim is not a new seed.

    A/B/C/D occupy all four retained ranks in insertion order. E is a new
    row/tag in that bank; the specified tree replacement chooses A. A's
    submitted 0/7 update is superseded, not backpressured or committed. E's
    own old 2/5 snapshot must start 1/6, never inherit A's retained counter.
    """
    paths:tuple=field(default=FULL_RETAINED_RETOUCH.paths+(PC+0x400,),init=False)
    feedback_order:tuple=field(default=(0,1,2,3,4),init=False)

    @property
    def history_count(self):return len(self.paths)

    @property
    def retained_histories(self):return (1,2,3,4)

    @property
    def retained_count(self):return RETAINED_CAPACITY

    @property
    def initial_base(self):return (0,3)

    def initial_counters(self,history):return (1,6) if history==0 else (2,5)

    def expected_counters(self,history):return (1,6)


FULL_RETAINED_REPLACEMENT=FullReplacementProgram()


def learning_inflight(model):
    return (any(value is not None for value in (model.accepted,model.info,model.mature))
        or bool(model.offers) or bool(model.useful_offers))


def pending_fronts(model,table,bank):
    """Per-owner oldest service rank; no actual dirty/selector input."""
    cache=model.cache[table,bank]
    result=[]
    for owner in range(2):
        pending=sorted((version for version in cache.records.values()
            if version.write.way==owner and version.sequence in cache.pending),key=lambda version:version.rank)
        if not pending:result.append(None)
        else:
            write=pending[0].write
            result.append(dict(row=write.row,valid=int(write.entry.valid),tag=write.entry.tag,counter=write.entry.counter))
    return tuple(result)


def pending_plan(model,table,bank):
    """All logical obligations, ordered by the specified per-owner service policy."""
    cache=model.cache[table,bank]
    return tuple(tuple(dict(row=version.write.row,valid=int(version.write.entry.valid),
        tag=version.write.entry.tag,counter=version.write.entry.counter) for version in sorted(
            (item for item in cache.records.values() if item.write.way==owner and item.sequence in cache.pending),
            key=lambda item:item.rank)) for owner in range(2))


def secondary_program():
    """Same branch PC, new genuine history; Main records are already resident."""
    yield 'disable',(),None,None
    yield 'resolve',((0,False,False),(1,False,True)),None,((0,1),(None,None))
    yield 'resolve',((0,False,False),(1,False,False)),None,((0,0),(None,None))
    yield 'resolve',((0,True,True),),None,((1,0),(None,None))
    yield 'resolve',((0,True,True),),None,((2,0),(None,None))
    yield 'enable',(),None,None
    yield 'allocate',((0,False,True),(1,False,False)),(3,0),((1,0),(3,None))
    yield 'allocate',((0,False,False),(1,True,True)),(3,1),((0,1),(2,4))
    # The first history already reduced the shared weak-base selector below
    # its threshold. B's weak taken provider now wins, so strengthening it is
    # a correct outcome, not another invented misprediction/reread.
    yield 'resolve',((0,False,False),(1,True,False)),None,((0,2),(1,5))
    yield 'resolve',((0,True,True),),None,((1,2),(2,5))
