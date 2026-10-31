"""Autonomous Ahead/MicroTAGE/Main direction composition and source ownership.

Read-index ancestry, tag ancestry, raw match positions and presented source
positions remain separate immutable contexts. The S3 outcome trains only
conditional branches which actually belonged to the original S1 path. No
sampled provider, folded history, table state or parent-policy result enters
the model. Full 15-bit tags are preserved even where RTL storage is narrower.
"""
from dataclasses import dataclass,replace

from suites.frontend.bpu.bpu.model.ahead_sources import AheadSources,old_history
from suites.frontend.bpu.bpu.model.selection import Kind
from suites.frontend.bpu.utage.model.semantic import UtageReference,Context,Base,Source,Feedback,Events,Prediction


def context(checkpoint):return Context() if checkpoint is None else Context(checkpoint.folds())


def bases(frame,enabled):
    if frame is None:return (Base(),)*4
    return tuple(Base(bool(enabled and frame.valid and hit),entry.position,bool(counter>=2),entry.kind,counter in (0,3))
        for entry,hit,counter in zip(frame.read.entries,frame.hits,frame.counters,strict=True))


@dataclass(frozen=True,slots=True)
class EarlySnapshot:
    owner: object
    prediction: Prediction
    end_position: int


class EarlyDirectionSources(AheadSources):
    has_own_utage=True

    def __init__(self):
        super().__init__()
        self.short=UtageReference()
        self.short_reads={}
        self.last_short_events=None

    def reset(self):
        super().reset()
        self.short.reset()
        self.short_reads.clear()
        self.last_short_events=None

    def current_short(self,enabled):
        return Prediction(self.short.frame,bases(self.ahead.frame,enabled),self.short.redirect_bubble,
            self.short.prediction is not None and self.short.prediction.qualified)

    def short_snapshot(self,token):
        saved=self.short_reads.get(token.history.sequence)
        if saved is None or saved.owner is not token.history:
            raise ValueError('MicroTAGE source is absent, retired or belongs to another checkpoint')
        return saved

    def early_directions(self,token,candidates,enabled):
        prediction=self.current_short(enabled[1]);values=prediction.values()
        return tuple(bool(values[f'{way}.taken']) if branch is not None and branch.kind==Kind.CONDITIONAL
            and values.get(f'{way}.hit') else None for way,branch in enumerate(candidates))

    def choose(self,token,stage,enabled):
        decision=super().choose(token,stage,enabled)
        if stage==1 and decision.source=='ahead':
            frame=self.short.frame
            if frame is not None and any(provider is not None for provider in frame.providers()):
                decision=replace(decision,source='ahead-direction')
        return decision

    def validate_early(self,events,cycle):
        # Main's exact-public-origin checks remain in the superclass. Short
        # history learning consumes the independently frozen S1 source below.
        if cycle.tokens[2] is not None:self.short_snapshot(cycle.tokens[2])

    def defined_short_metadata(self,token,*,qualified=True):
        saved=self.short_snapshot(token)
        values=saved.prediction.values()
        if qualified:
            values=dict(values)
            for way in range(4):
                if values.get(f'{way}.position',0)>saved.end_position:values[f'{way}.valid']=0
        return values

    def short_feedback(self,token,decision):
        saved=self.short_snapshot(token);prediction=saved.prediction
        frame=prediction.frame
        if frame is None:return None
        values=self.defined_short_metadata(token)
        sources=[]
        providers=frame.providers()
        for way,base in enumerate(prediction.bases):
            provider=providers[way]
            sources.append(Source(bool(values[f'{way}.valid']),frame.positions[way],
                bool(base.valid and provider is not None),0 if provider is None else provider,
                0 if provider is None else frame.read.entries[provider].counter,
                False if provider is None else frame.read.entries[provider].counter>=4,base.taken))
        branch=decision.branch
        return Feedback(token.pc,frame.context,frame.read.indices,tuple(sources),branch.position,branch.taken,int(branch.kind))

    def advance(self,events,cycle,issued):
        first,second,third=cycle.tokens
        if first is not None and cycle.fires[1] and not cycle.flushes[0]:
            self.short_reads[first.history.sequence]=EarlySnapshot(first.history,self.current_short(cycle.enabled[1]),
                cycle.decisions[0].branch.position)
        # FastTrain is registered unconditionally; the CURRENT enable gates
        # that registered offer one cycle later inside UtageReference.
        feedback=self.short_feedback(third,cycle.decisions[2]) if third is not None else None
        read_context=context(old_history(events,cycle,issued))
        match_context=context(first.history if first is not None else None if issued is None else issued.history)
        override=third if cycle.final_repair else second if cycle.middle_repair else None
        override_context=context(None if override is None else override.history)
        first_choice=cycle.decisions[0]
        super().advance(events,cycle,issued)
        frame=self.ahead.frame
        positions=(0,)*4 if frame is None else tuple(entry.position for entry in frame.read.entries)
        short_events=Events(read_pc=cycle.next_pc,read_context=read_context,select=cycle.fires[0],
            pc=cycle.next_pc if first_choice is None else first_choice.branch.target,context=match_context,
            positions=positions,bases=bases(frame,cycle.enabled[1]),advance=cycle.fires[2],
            override='s3' if cycle.final_repair else 's2' if cycle.middle_repair else None,
            override_pc=0 if override is None else cycle.decisions[2 if cycle.final_repair else 1].branch.target,
            override_context=override_context,feedback=feedback,redirect=events.redirect is not None,
            enabled=cycle.enabled[1],ready=events.initialization_complete)
        self.short.advance(short_events)
        self.last_short_events=short_events

    def retain(self,tokens):
        super().retain(tokens)
        keys={token.history.sequence for token in tokens}
        self.short_reads={key:value for key,value in self.short_reads.items() if key in keys}

    def main_pending(self):
        # MicroTAGE reads are continuous even while BPU issue is held. A dirty
        # shadow may legally wait for bank service indefinitely; mature logical
        # learning and SRAM retirement must not be conflated.
        return super().main_pending() or self.short.offered is not None or self.short.learning is not None
