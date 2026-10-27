"""Independently learned MicroBTB + MainBTB, never DUT branch candidates.

Requests own immutable MainBTB read frames. Feedback must name that exact
published token, not merely an equivalent PC/history encoding. Other learned
predictors and return stacks still require additional composition adapters.
"""
from bpuverify.common.model.configuration import *

from bpuverify.bpu.model.micro_sources import MicroSources
from bpuverify.bpu.model.selection import Branch,Kind,StackAction,fallthrough,middle,final
from bpuverify.mbtb.model.semantic import MbtbReference,Events,Feedback,Source,Branch as Outcome,Frame


def source_entries(frame):
    if type(frame) is not Frame:
        raise ValueError('MainBTB feedback needs an owned request frame')
    values = frame.values()
    return tuple(tuple(Source(bool(values[f'{slot}.raw_hit']),
        values.get(f'{slot}.meta_position',0),values.get(f'{slot}.meta_kind',0),
        values.get(f'{slot}.meta_action',0),values.get(f'{slot}.counter',0))
        for slot in range(alignment*(MAIN_WAYS+1),(alignment+1)*(MAIN_WAYS+1))) for alignment in range(2))


class BranchTargetSources(MicroSources):
    requires_explicit_origin = True
    unsupported_learning = (1,3,4,5,6)

    def __init__(self):
        super().__init__()
        self.main = MbtbReference()
        self.main_enabled = False

    def reset(self):
        super().reset()
        self.main.reset()
        self.main_enabled = False

    def capture(self,pc,checkpoint):
        return self.main.lookup_snapshot(pc) if self.main_enabled else None

    def choose(self,token,stage,enabled):
        if stage==1:
            return super().choose(token,stage,enabled)
        if not enabled[2] or token.lookup is None:
            return fallthrough(token.pc)
        frame = token.lookup
        if type(frame) is not Frame or frame.pc!=token.pc:
            raise AssertionError('MainBTB read is not this owned pipeline request')
        values = frame.values()
        entries = tuple(None if not values[f'{slot}.valid'] else Branch(values[f'{slot}.position'],
            values[f'{slot}.target'],Kind(values[f'{slot}.kind']),bool(values[f'{slot}.taken']),
            StackAction(values[f'{slot}.action'])) for slot in range(RESULT_SLOTS))
        directions = (None,)*RESULT_SLOTS
        return middle(token.pc,entries,directions) if stage==2 else final(token.pc,entries,directions,directions)

    def validate(self,events,cycle):
        if events.feedback is not None:
            if any(cycle.enabled[index] for index in self.unsupported_learning):
                raise NotImplementedError('other enabled learning needs further source-bank composition')
            super().validate(events,cycle)
            if cycle.enabled[2] and (events.feedback.origin is None or type(events.feedback.origin.lookup) is not Frame):
                raise ValueError('MainBTB learning requires the exact published lookup owner')
        if (cycle.enabled[2]!=self.main_enabled and self.main.memory and any(cycle.tokens)):
            raise NotImplementedError('live MainBTB enable transition is not yet a qualified composition profile')
        self.main_enabled = cycle.enabled[2]

    def advance(self,events,cycle,issued):
        # This also learns MicroBTB from the independently chosen final result.
        super().advance(events,cycle,issued)
        feedback = None
        if events.feedback is not None and cycle.enabled[2]:
            source = events.feedback
            frame = source.origin.lookup
            feedback = Feedback((source.pc,((source.pc//ALIGN_HALFWORDS+1)*ALIGN_HALFWORDS)%(1<<49)),source_entries(frame),
                tuple(Outcome(branch.target,branch.taken,branch.position,int(branch.kind),int(branch.action),
                    branch.mispredict) for branch in source.branches if branch is not None))
        self.main.advance(Events(pc=cycle.next_pc,select=issued is not None,advance=cycle.fires[1],
            consume=cycle.fires[2],feedback=feedback,enabled=cycle.enabled[2]))

    def main_pending(self):
        return (self.main.offered is not None or any(self.main.entry_offers.values())
            or any(cache.outstanding for cache in self.main.entries.values())
            or any(queue.pending for queue in self.main.directions.values()) or bool(self.main.cleanup) or bool(self.main.snapshots))
