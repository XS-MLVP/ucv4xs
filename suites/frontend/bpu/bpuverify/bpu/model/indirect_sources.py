"""Owned MainBTB/ITTAGE/history composition, not a sampled-component oracle."""
from dataclasses import dataclass,replace

from bpuverify.bpu.model.main_sources import BranchTargetSources
from bpuverify.bpu.model.selection import Branch,Kind,StackAction,final,fallthrough
from bpuverify.ittage.model.semantic import IttageReference,Context,Metadata,Outcome,Events
from bpuverify.tage.model.semantic import lfsr_next


def context_for(checkpoint):return Context.from_recent(checkpoint.history% (1<<31))


def allocation(prediction,random):
    preferred=tuple(table for table in prediction.candidates if random&(1<<table))
    return min(preferred or prediction.candidates) if prediction.candidates else None


@dataclass(frozen=True,slots=True)
class IndirectSnapshot:
    owner:object
    enabled:bool=False
    read:object=None
    prediction:object=None
    allocation:int|None=None
    late:object=None
    published_enabled:bool|None=None


class IndirectSources(BranchTargetSources):
    has_own_ittage=True
    unsupported_learning=(1,3,4,6)

    def __init__(self):
        super().__init__();self.indirect=IttageReference();self.indirect_enabled=False
        self.random=1;self.reads={};self.resolved={}

    def reset(self):
        super().reset();self.indirect.reset();self.indirect_enabled=False;self.random=1
        self.reads.clear();self.resolved.clear()

    def capture(self,pc,checkpoint):
        frame=super().capture(pc,checkpoint)
        # ITTAGE accesses the SRAM when S1 accepts, one stage after Main.
        self.reads[checkpoint.sequence]=IndirectSnapshot(checkpoint)
        return frame

    def snapshot(self,token,*,resolved=False):
        result=(self.resolved if resolved else self.reads).get(token.history.sequence)
        if result is None or result.owner is not token.history:
            raise ValueError('ITTAGE source is absent, retired or belongs to another checkpoint owner')
        return result

    def random_at_sample(self,events):
        # Unlike handshake-owned pipeline tokens, the free-running PRNG has
        # already consumed this boundary's physical reset/clock at sampling.
        # Keep the prior boundary's state and predict this sample purely.
        return 1 if events.consumed_reset else lfsr_next(self.random)

    def choose(self,token,stage,enabled):
        if stage!=3:return super().choose(token,stage,enabled)
        if not enabled[2] or token.lookup is None:return fallthrough(token.pc)
        return self.snapshot(token,resolved=True).late

    def defined_ittage_metadata(self,token,*,service_enabled=None):
        source=self.snapshot(token,resolved=True);value=source.prediction
        enabled=source.enabled if source.published_enabled is None else source.published_enabled
        if service_enabled is not None:
            if type(service_enabled) is not bool:
                raise ValueError('ITTAGE publication service enable must be semantic bool')
            enabled=service_enabled
        if not enabled or value is None:return dict(valid=int(enabled))
        fields=dict(valid=1,provider=dict(valid=int(value.provider is not None)),
            altProvider=dict(valid=int(value.alternate is not None)),
            allocate=dict(valid=int(source.allocation is not None)),
            altDiffers=int(value.alternate is not None and value.provider_target!=value.alternate_target))
        if value.provider is not None:
            fields['provider']['bits']=value.provider
            fields.update(providerCnt_value=value.confidence,providerUsefulCnt_value=value.useful,
                providerTarget_addr=value.provider_target//2)
        if value.alternate is not None:
            fields['altProvider']['bits']=value.alternate
            fields.update(altProviderCnt_value=value.alternate_confidence,altProviderTarget_addr=value.alternate_target//2)
        if source.allocation is not None:fields['allocate']['bits']=source.allocation
        return fields

    def feedback_for(self,resolution):
        token=resolution.origin
        if token is None:raise ValueError('ITTAGE feedback requires the exact published origin')
        source=self.snapshot(token,resolved=True);prediction=source.prediction
        branches=tuple(branch for branch in resolution.branches if branch is not None and branch.taken
            and branch.kind==Kind.INDIRECT and not branch.action&StackAction.RETURN)
        if len(branches)>1:raise ValueError('ITTAGE can learn at most one taken indirect per resolved fetch')
        if not branches:return None
        # The original query must have published this component's snapshot.
        # An unpublished snapshot carries only unrelated register residue; it
        # cannot supply a provider, allocation candidate or target. Main and
        # other components with their own legal snapshots still learn.
        if prediction is None or source.published_enabled is not True:return None
        branch,=branches
        meta=Metadata(prediction.provider,prediction.confidence,prediction.useful,prediction.provider_target,
            prediction.alternate,prediction.alternate_confidence,prediction.alternate_target,
            prediction.alternate is not None and prediction.provider_target!=prediction.alternate_target,source.allocation)
        return Outcome(token.pc*2,context_for(token.history),meta,branch.target*2,mispredict=branch.mispredict)

    def validate(self,events,cycle):
        super().validate(events,cycle)
        enabled=bool(cycle.enabled[2] and cycle.enabled[5])
        trained=any(memory for banks in self.indirect.memories for memory in banks)
        if enabled!=self.indirect_enabled and trained and (any(cycle.tokens[1:]) or (
                cycle.tokens[0] is not None and cycle.fires[1] and not cycle.flushes[0])):
            raise NotImplementedError('trained ITTAGE enable transition needs drained older stages and a squashed old S1')
        self.indirect_enabled=enabled
        if events.feedback is not None and enabled:self.feedback_for(events.feedback)

    def advance(self,events,cycle,issued):
        enabled=bool(cycle.enabled[2] and cycle.enabled[5]);first,second,_=cycle.tokens
        third=cycle.tokens[2]
        if third is not None and events.redirect is None:
            source=self.snapshot(third,resolved=True)
            self.resolved[third.history.sequence]=replace(source,published_enabled=enabled)
        random=self.random_at_sample(events)
        if first is not None and cycle.fires[1] and enabled:
            source=self.snapshot(first)
            self.reads[first.history.sequence]=replace(source,read=self.indirect.lookup_snapshot(first.pc*2,context_for(first.history)))
        if second is not None and not cycle.flushes[1]:
            source=self.snapshot(second);prediction=None
            if enabled and source.read is not None:
                prediction=self.indirect.predict_snapshot(source.read)
            elif enabled and second.lookup is not None:
                raise ValueError('enabled ITTAGE S2 has no independently owned S1 read')
            values={} if second.lookup is None else second.lookup.values()
            branches=tuple(None if not values.get(f'{slot}.valid') else Branch(values[f'{slot}.position'],
                values[f'{slot}.target'],Kind(values[f'{slot}.kind']),bool(values[f'{slot}.taken']),StackAction(values[f'{slot}.action']))
                for slot in range(4))
            target=None if prediction is None or prediction.provider is None else prediction.target//2
            late=final(second.pc,branches,(None,)*4,(None,)*4,indirect_target=target)
            self.resolved[second.history.sequence]=replace(source,enabled=enabled,prediction=prediction,
                allocation=None if prediction is None else allocation(prediction,random),late=late)
        feedback=self.feedback_for(events.feedback) if events.feedback is not None and enabled else None
        self.indirect.advance(Events(pc=None if issued is None else issued.pc*2,
            context=Context() if first is None else context_for(first.history),access=cycle.fires[1],select=cycle.fires[2],
            feedback=feedback,enabled=enabled,reset=bool(events.consumed_reset)))
        self.random=random
        super().advance(events,cycle,issued)

    def retain(self,tokens):
        keys={token.history.sequence for token in tokens}
        self.reads={key:value for key,value in self.reads.items() if key in keys}
        self.resolved={key:value for key,value in self.resolved.items() if key in keys}

    def main_pending(self):
        model=self.indirect
        return (super().main_pending() or model.learning is not None or bool(model.normal) or model.clear_start
            or any(busy for busy,_ in model.maintenance)
            or any(slot is not None and slot.dirty for banks in model.caches for cache in banks for slot in cache.slots))
