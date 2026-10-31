"""Independent promoted-provider and shorter-alternate selection checks."""
from collections import deque

from toffee import CheckContext, ScoreboardMode

from suites.frontend.bpu.bpu.checker.assertions import mbtb_counter_for_position
from suites.frontend.bpu.bpu.checker.tage.semantic import TageSemanticComponentChecker
from suites.frontend.bpu.bpu.checker.tage.selection import selection_for


def observed_alternate(frame,bases,actual,position):
    if frame is None:
        return None
    slots = [slot for slot,base in enumerate(bases) if base.valid and frame.positions[slot]==position]
    if len(slots)!=1:
        return None
    slot, = slots
    meta = actual.metas[slot]
    if not (meta['hasProvider'] and meta['hasAlt'] and meta['providerTableIdx']==3
            and not meta['altOrBasePred'] and bases[slot].taken):
        return None
    if meta['providerTakenCtr_value']==4 and not meta['useProvider'] and meta['altConf']:
        return 'weak'
    if meta['providerTakenCtr_value']==5 and meta['useProvider']:
        return 'strong'
    return None


class TageAlternateChecker(TageSemanticComponentChecker):
    def __init__(self,coverage,*,pc,positions,targets):
        super().__init__()
        self.coverage,self.pc,self.positions,self.targets = coverage,pc,positions,targets
        self.routes = deque(maxlen=128)
        self.sentinel_seen = False

    def capture_output(self,event,actual,*,bases,enabled,extras):
        frame = self.model.frame
        active = (self.failure is None and self.initialized and self.events is not None
                  and self.events.ready and self.events.advance and self.events.enabled and not self.events.reset and enabled)
        phase = observed_alternate(frame,bases,actual,self.positions[-1]) if active and frame is not None and frame.read.pc==self.pc else None
        rules = [] if phase is None else ['promoted-provider-keeps-alternate']
        if phase=='weak':
            rules.append('alternate-over-opposing-base')
        for rule in rules:
            self.coverage.record('reached',rule,tick=event.tick,phase=phase)
        super().capture_output(event,actual,bases=bases,enabled=enabled,extras=extras)
        if phase is not None and self.failure is None:
            try:
                matches = frame.read.matches(self.positions[-1])
                self.board.check(expected=(2,3),actual=tuple(match[0] for match in matches),
                    context=CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=event.tick,
                        request=dict(point='promotion retained history levels',state=self.model.state()),observed_event=event))
                self.routes.append((event.tick,phase))
                for rule in rules:
                    self.coverage.record('checked',rule,tick=event.tick,phase=phase)
            except Exception as error:
                self.failure = error

    def consumer(self,source,repairs):
        self.raise_failure()
        try:
            return self._consumer(source,repairs)
        except Exception as error:
            self.failure = error
            raise

    def _consumer(self,source,repairs):
        selection = selection_for(self,source,pc=self.pc,positions=self.positions,targets=self.targets)
        context = selection.context
        matches = [phase for tick,phase in self.routes if tick==source.meta_tick-4]
        self.board.check(expected=1,actual=len(matches),context=context)
        phase, = matches
        rules = []
        if phase=='weak':
            if any(tick==source.prediction_tick+2 and p.start_pc==self.pc and p.s2_override for tick,p in repairs):
                rules.append('raw-middle-redirect')
            if any(tick==source.meta_tick and p.start_pc==self.pc and p.s3_override for tick,p in repairs):
                rules.append('alternate-final-redirect')
        elif len(repairs)==1 and repairs[0][0]==source.prediction_tick+2 and repairs[0][1].s2_override:
            rules.append('strong-provider-reclaims')
        sentinel_counter = mbtb_counter_for_position(source,self.positions[0])
        if phase=='strong' and self.sentinel_seen and sentinel_counter==0:
            rules.append('sentinel-unmodified')
        for rule in rules:
            self.coverage.record('reached',rule,tick=source.meta_tick,phase=phase)
        selection.check(self.board,source,repairs)
        self.board.check(expected=0,actual=sentinel_counter,context=context)
        self.board.check(expected=0,actual=selection.metadata[0]['hasProvider'],context=context)
        if phase=='weak':
            self.sentinel_seen = True
        for rule in rules:
            self.coverage.record('checked',rule,tick=source.meta_tick,phase=phase)
        return phase

    def finish(self):
        self.raise_failure()
        self.coverage.finish()
