"""One capacity-safe usefulness lifecycle, independent of signal observation."""
from dataclasses import dataclass

from suites.frontend.bpu.bpu.model.tage.service import READ_PRIORITY_PAIR


@dataclass(frozen=True,slots=True)
class UsefulProgram:
    feedback_order:tuple=READ_PRIORITY_PAIR.feedback_order
    initial_base:tuple=(3,2)
    initial_counters:tuple=(2,5)
    # Main feedback uses each captured 3/2 snapshot: every proposal is 2/3.
    # Unlike the TAGE retained-counter cache it does not compound to 0/3.
    final_base:tuple=(2,3)
    final_counters:tuple=(0,7)
    # The taken tail already earned useful one during normal preparation;
    # keep that nonzero neighbour as an isolation sentinel.
    initial_useful:tuple=(0,1)
    final_useful:tuple=(1,1)


PROGRAM=UsefulProgram()


def main_preparation():
    # Existing Main counter1: two ordinary taken outcomes reach strong3.
    # Only the first is wrong; the second source already predicts taken.
    yield ((0,True,True),),((2,2),(None,None))
    yield ((0,True,False),),((3,2),(None,None))


def pending_useful(model,table,bank):
    return tuple(tuple(dict(row=write.row,value=write.value)
        for write in model.useful_queue[table,bank,way].pending) for way in range(2))


def occupancy(queue):
    """Read-only representation check, never a golden-state initializer."""
    enqueue,dequeue,full=(queue[key] for key in ('enqueue','dequeue','full'))
    if enqueue not in range(4) or dequeue not in range(4) or full not in (0,1):
        raise ValueError('malformed useful service pointer observation')
    return (enqueue-dequeue)%4+(4 if enqueue==dequeue and full else 0)
