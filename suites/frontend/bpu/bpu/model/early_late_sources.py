"""One Main/Micro/Ahead/MicroTAGE pipeline plus an owned TAGE direction facet.

Both direction predictors use their existing independent algorithms. The
facet has no duplicate base predictor, no sampled inputs and no inherited
Ahead snapshot names. Main/Micro advance exactly once per pipeline boundary.
"""
from suites.frontend.bpu.bpu.model.direction_sources import DirectionSources,DirectionSnapshot,candidates,context_for
from suites.frontend.bpu.bpu.model.early_direction_sources import EarlyDirectionSources
from suites.frontend.bpu.tage.model.semantic import TageReference,Context,Events


class _DirectionState:
    def __init__(self):
        self.tage=TageReference(); self.reset()
    def reset(self):
        self.tage.reset(); self.tage_enabled=False; self.reads,self.resolved={},{}
    def capture(self,pc,checkpoint):
        read=self.tage.lookup_snapshot(pc,context_for(checkpoint)) if self.tage_enabled else None
        self.reads[checkpoint.sequence]=DirectionSnapshot(checkpoint,read)
    def snapshot(self,token,*,resolved=False):
        return DirectionSources.snapshot(self,token,resolved=resolved)
    def decision(self,token,enabled):
        return DirectionSources.decision(self,token,enabled)
    def choose(self,token,stage,enabled):
        if stage not in (2,3): raise ValueError('TAGE facet only owns middle/final direction')
        return DirectionSources.choose(self,token,stage,enabled)
    def defined_metadata(self,token):
        return DirectionSources.defined_metadata(self,token)
    def feedback_for(self,resolution):
        return DirectionSources.feedback_for(self,resolution)
    def validate(self,events,cycle):
        enabled=bool(cycle.enabled[2] and cycle.enabled[3])
        if enabled!=self.tage_enabled and self.tage.memory and (any(cycle.tokens[1:]) or (
                cycle.tokens[0] is not None and cycle.fires[1] and not cycle.flushes[0])):
            raise NotImplementedError('trained TAGE transition needs drained older stages and held/flushed S1')
        self.tage_enabled=enabled
        if events.feedback is not None and enabled: self.feedback_for(events.feedback)
    def prepare(self,events,cycle):
        enabled=bool(cycle.enabled[2] and cycle.enabled[3]); second=cycle.tokens[1]
        if second is not None and not cycle.flushes[1]:
            _,wanted,late=self.decision(second,enabled); source=self.snapshot(second)
            self.resolved[second.history.sequence]=DirectionSnapshot(source.owner,source.read,tuple(wanted.items()),late)
        return self.feedback_for(events.feedback) if events.feedback is not None and enabled else None
    def advance(self,events,cycle,issued,feedback):
        first=cycle.tokens[0]
        self.tage.advance(Events(pc=cycle.next_pc,context=Context() if issued is None else context_for(issued.history),
            positions=(0,)*4 if first is None else candidates(first)[2],select=issued is not None,
            advance=cycle.fires[1],feedback=feedback,enabled=bool(cycle.enabled[2] and cycle.enabled[3]),
            reset=bool(events.consumed_reset)))
    def retain(self,keys):
        self.reads={k:v for k,v in self.reads.items() if k in keys}
        self.resolved={k:v for k,v in self.resolved.items() if k in keys}
    def pending(self):
        tage=self.tage
        return (any(value is not None for value in (tage.accepted,tage.info,tage.mature))
            or bool(tage.offers) or bool(tage.useful_offers) or bool(tage.clear_cursor) or tage.aging
            or any(cache.pending for cache in tage.cache.values())
            or any(queue.pending for queue in tage.useful_queue.values()))


class EarlyLateSources(EarlyDirectionSources):
    has_own_tage=True
    unsupported_learning=(4,5,6)

    def __init__(self):
        super().__init__(); self.directions=_DirectionState()
    @property
    def tage(self): return self.directions.tage
    @property
    def tage_enabled(self): return self.directions.tage_enabled
    def reset(self):
        super().reset(); self.directions.reset()
    def capture(self,pc,checkpoint):
        frame=super().capture(pc,checkpoint)
        self.directions.capture(pc,checkpoint); return frame
    def tage_snapshot(self,token,*,resolved=False):
        return self.directions.snapshot(token,resolved=resolved)
    def defined_tage_metadata(self,token):
        return self.directions.defined_metadata(token)
    def tage_decision(self,token,enabled=True):
        return self.directions.decision(token,enabled)
    def feedback_for(self,resolution):
        return self.directions.feedback_for(resolution)
    def choose(self,token,stage,enabled):
        if stage==1: return super().choose(token,stage,enabled)
        return self.directions.choose(token,stage,enabled)
    def validate(self,events,cycle):
        super().validate(events,cycle); self.directions.validate(events,cycle)
    def advance(self,events,cycle,issued):
        feedback=self.directions.prepare(events,cycle)
        super().advance(events,cycle,issued)
        self.directions.advance(events,cycle,issued,feedback)
    def retain(self,tokens):
        tokens=tuple(tokens); super().retain(tokens)
        self.directions.retain({t.history.sequence for t in tokens})
    def main_pending(self):
        return super().main_pending() or self.directions.pending()
