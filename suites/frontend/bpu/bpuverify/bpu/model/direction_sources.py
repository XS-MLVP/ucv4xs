"""Autonomous MicroBTB/MainBTB/TAGE composition, with owned history and reads.

No component result or FTQ metadata is an input to these algorithms. The
main lookup remains Token.lookup; TAGE snapshots belong to that exact owned
history checkpoint. S3 uses the decision frozen at S2, not today's selectors.
"""
from bpuverify.common.model.configuration import *

from dataclasses import dataclass

from bpuverify.bpu.model.main_sources import BranchTargetSources,source_entries
from bpuverify.bpu.model.selection import Branch,Kind,StackAction,fallthrough,middle,final
from bpuverify.tage.model.semantic import TageReference,Base,Branch as Resolved,Context,Events,Feedback,Frame,Hint,decide


HISTORY_PORTS = tuple(sorted({PHR_FOLDS.index((n,min(n,w))) for n in TAGE_HISTORIES for w in (9,13,12)}))
META_FIELDS = dict(has_provider='hasProvider',has_alt='hasAlt',use_provider='useProvider',table='providerTableIdx',
    way='providerWayIdx',counter='providerTakenCtr_value',useful='providerUsefulCtr_value',
    alternative='altOrBasePred',alt_conf='altConf')


def context_for(checkpoint):
    folds = checkpoint.folds()
    return Context(tuple(value if index in HISTORY_PORTS else 0 for index,value in enumerate(folds)))


def candidates(token):
    if token.lookup is None:return (None,)*RESULT_SLOTS,(Base(),)*RESULT_SLOTS,(0,)*RESULT_SLOTS
    values = token.lookup.values()
    branches,bases,positions = [],[],[]
    for slot in range(RESULT_SLOTS):
        valid = bool(values[f'{slot}.valid'])
        position = values.get(f'{slot}.meta_position',0)
        positions.append(position)
        if not valid:
            branches.append(None)
            bases.append(Base())
            continue
        branch = Branch(position,values[f'{slot}.target'],Kind(values[f'{slot}.kind']),
            bool(values[f'{slot}.taken']),StackAction(values[f'{slot}.action']))
        branches.append(branch)
        bases.append(Base(True,position,branch.taken,values[f'{slot}.counter'] in (0,3),int(branch.kind)))
    return tuple(branches),tuple(bases),tuple(positions)


@dataclass(frozen=True,slots=True)
class DirectionSnapshot:
    # The checkpoint object's identity prevents a foreign equal encoding
    # from borrowing another source's read or selector-time metadata.
    owner: object
    read: object
    wanted: tuple = ()
    late: object = None


class DirectionSources(BranchTargetSources):
    has_own_tage = True
    unsupported_learning = (1,4,5,6)

    def __init__(self):
        super().__init__()
        self.tage = TageReference()
        self.tage_enabled = False
        self.reads,self.resolved = {},{}

    def reset(self):
        super().reset()
        self.tage.reset()
        self.tage_enabled = False
        self.reads.clear()
        self.resolved.clear()

    def capture(self,pc,checkpoint):
        lookup = super().capture(pc,checkpoint)
        read = self.tage.lookup_snapshot(pc,context_for(checkpoint)) if self.tage_enabled else None
        self.reads[checkpoint.sequence] = DirectionSnapshot(checkpoint,read)
        return lookup

    def snapshot(self,token,*,resolved=False):
        source = (self.resolved if resolved else self.reads).get(token.history.sequence)
        if source is None or source.owner is not token.history:
            raise ValueError('TAGE lookup is absent, retired or belongs to another checkpoint owner')
        return source

    def decision(self,token,enabled):
        source = self.snapshot(token)
        branches,bases,positions = candidates(token)
        if not enabled or source.read is None:
            if enabled and token.lookup is not None:
                raise NotImplementedError('disabled TAGE lookup must be squashed before enabled S2 consumption')
            return branches,{},final(token.pc,branches,(None,)*RESULT_SLOTS,(None,)*RESULT_SLOTS)
        wanted = decide(Frame(source.read,positions),bases,self.tage.selectors)
        directions = tuple(bool(wanted[f'{slot}.taken']) if wanted.get(f'{slot}.valid') else None for slot in range(RESULT_SLOTS))
        return branches,wanted,final(token.pc,branches,directions,(None,)*RESULT_SLOTS)

    def choose(self,token,stage,enabled):
        if stage==1:return super().choose(token,stage,enabled)
        if not enabled[2] or token.lookup is None:return fallthrough(token.pc)
        if stage==3:return self.snapshot(token,resolved=True).late
        branches,wanted,_ = self.decision(token,bool(enabled[2] and enabled[3]))
        directions = tuple(bool(wanted[f'{slot}.fast_taken']) if wanted.get(f'{slot}.fast_valid') else None for slot in range(RESULT_SLOTS))
        return middle(token.pc,branches,directions)

    def defined_metadata(self,token):
        source = self.snapshot(token,resolved=True)
        wanted = dict(source.wanted)
        return {f'{slot}.{field}':wanted[f'{slot}.{key}'] for slot in range(RESULT_SLOTS)
            for key,field in META_FIELDS.items() if f'{slot}.{key}' in wanted}

    def tage_snapshot(self,token,*,resolved=False):
        """Explicit TAGE domain; legacy single-domain callers keep snapshot."""
        return self.snapshot(token,resolved=resolved)

    def defined_tage_metadata(self,token):
        return self.defined_metadata(token)

    def tage_decision(self,token,enabled=True):
        return self.decision(token,enabled)

    def feedback_for(self,resolution):
        token = resolution.origin
        if token is None:raise ValueError('TAGE feedback requires the exact published prediction owner')
        metadata = self.defined_metadata(token)
        entries = tuple(entry for row in source_entries(token.lookup) for entry in row) if token.lookup is not None else ()
        branches = []
        for branch in resolution.branches:
            if branch is None:continue
            matches = [slot for slot,entry in enumerate(entries) if entry.hit and entry.position==branch.position]
            if len(matches)>1:raise ValueError('TAGE feedback requires one logical MainBTB source per position')
            if not matches:
                branches.append(Resolved(branch.position,branch.taken,int(branch.kind),branch.mispredict,False))
                continue
            slot, = matches
            if any(f'{slot}.{field}' not in metadata for field in ('hasProvider','hasAlt','useProvider','altOrBasePred','altConf')):
                raise NotImplementedError('matched learning needs an originally enabled TAGE source')
            fields = {field:metadata[f'{slot}.{field}'] for field in ('hasProvider','hasAlt','useProvider','altOrBasePred','altConf')}
            hint = Hint(bool(fields['hasProvider']),bool(fields['hasAlt']),bool(fields['useProvider']),
                metadata.get(f'{slot}.providerTableIdx',0),metadata.get(f'{slot}.providerWayIdx',0),
                metadata.get(f'{slot}.providerTakenCtr_value',0),metadata.get(f'{slot}.providerUsefulCtr_value',0),
                bool(fields['altOrBasePred']),bool(fields['altConf']))
            branches.append(Resolved(branch.position,branch.taken,int(branch.kind),branch.mispredict,True,entries[slot].counter,hint))
        return Feedback(resolution.pc,context_for(token.history),tuple(branches))

    def validate(self,events,cycle):
        super().validate(events,cycle)
        enabled = bool(cycle.enabled[2] and cycle.enabled[3])
        if enabled!=self.tage_enabled and self.tage.memory and (any(cycle.tokens[1:]) or (
                cycle.tokens[0] is not None and cycle.fires[1] and not cycle.flushes[0])):
            raise NotImplementedError('trained TAGE enable transition requires drained older stages and a held/flushed S1')
        self.tage_enabled = enabled
        if events.feedback is not None and enabled:self.feedback_for(events.feedback)

    def advance(self,events,cycle,issued):
        enabled = bool(cycle.enabled[2] and cycle.enabled[3])
        second = cycle.tokens[1]
        if second is not None and not cycle.flushes[1]:
            _,wanted,late = self.decision(second,enabled)
            source = self.snapshot(second)
            self.resolved[second.history.sequence] = DirectionSnapshot(source.owner,source.read,tuple(wanted.items()),late)
        feedback = self.feedback_for(events.feedback) if events.feedback is not None and enabled else None
        first = cycle.tokens[0]
        positions = (0,)*RESULT_SLOTS if first is None else candidates(first)[2]
        super().advance(events,cycle,issued)
        self.tage.advance(Events(pc=cycle.next_pc,context=Context() if issued is None else context_for(issued.history),
            positions=positions,select=issued is not None,advance=cycle.fires[1],feedback=feedback,enabled=enabled,
            reset=bool(events.consumed_reset)))

    def retain(self,tokens):
        keys = {token.history.sequence for token in tokens}
        self.reads = {key:value for key,value in self.reads.items() if key in keys}
        self.resolved = {key:value for key,value in self.resolved.items() if key in keys}

    def main_pending(self):
        return (super().main_pending() or any(value is not None for value in (self.tage.accepted,self.tage.info,self.tage.mature))
            or bool(self.tage.offers) or bool(self.tage.useful_offers) or bool(self.tage.clear_cursor) or self.tage.aging
            or any(cache.pending for cache in self.tage.cache.values())
            or any(queue.pending for queue in self.tage.useful_queue.values()))
