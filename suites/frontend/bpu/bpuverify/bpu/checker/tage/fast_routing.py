"""Compare all causal repairs, including unexpected same-target/PC overrides."""
from collections import deque

from toffee import CheckContext, ScoreboardMode

from bpuverify.bpu.checker.tage.semantic import TageSemanticComponentChecker
from bpuverify.bpu.checker.tage.selection import selection_for


def observed_phase(frame,bases,actual,positions):
    if frame is None:
        return None
    slots = []
    for position in positions:
        matches = [slot for slot,base in enumerate(bases) if base.valid and frame.positions[slot] == position]
        if len(matches) != 1:
            return None
        slots.append(matches[0])
    first,last = (actual.metas[slot] for slot in slots)
    if not all(meta['hasProvider'] and meta['providerTableIdx']==2 for meta in (first,last)):
        return None
    if (first['providerWayIdx'],last['providerWayIdx'],first['providerTakenCtr_value']) != (0,1,2):
        return None
    if last['hasAlt'] or first['hasAlt']:
        return None
    if last['providerTakenCtr_value']==4 and not last['useProvider'] and not last['altOrBasePred']:
        return 'weak'
    if last['providerTakenCtr_value']==5 and last['useProvider']:
        return 'strong'
    return None


class TageRoutingChecker(TageSemanticComponentChecker):
    def __init__(self,coverage,*,pc,positions,targets):
        super().__init__()
        self.coverage = coverage
        self.pc,self.positions,self.targets = pc,positions,targets
        self.routes = deque(maxlen=128)
        self.neighbor = None
        self.discoveries = []

    def capture_input(self,event,events,*,resolve_slots=()):
        super().capture_input(event,events,resolve_slots=resolve_slots)
        if self.failure is not None or not self.initialized:return
        if events.reset:
            self.discoveries.clear()
            self.routes.clear()
            self.neighbor = None
            return
        feedback = events.feedback
        if not events.ready or feedback is None or feedback.pc!=self.pc:return
        try:
            for branch in feedback.branches:
                # An actual accepted, taken conditional miss discovers a
                # MainBTB record. Observe even while TAGE learning is disabled.
                if (branch.position not in self.positions or branch.kind!=1 or not branch.taken
                        or not branch.mispredict or branch.matched):continue
                context = CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=event.tick,
                    request=dict(point='actual conditional discovery order',feedback=feedback,
                        discovery=self.coverage.discovery,accepted=self.discoveries))
                self.board.check(expected=False,actual=any(p==branch.position for _,p in self.discoveries),context=context)
                self.board.check(expected=True,actual=not self.discoveries or event.tick>self.discoveries[-1][0],context=context)
                expected = self.positions if self.coverage.discovery=='earlier-first' else self.positions[::-1]
                self.board.check(expected=expected[len(self.discoveries)],actual=branch.position,context=context)
                self.discoveries.append((event.tick,branch.position))
        except Exception as error:
            self.failure = error

    def earlier_ready(self,source):
        self.raise_failure()
        try:
            meta = self.source_expected(source,self.positions[0])
            self.board.check(expected=(1,2,0,2),actual=tuple(meta.get(name) for name in
                ('hasProvider','providerTableIdx','providerWayIdx','providerTakenCtr_value')),
                context=CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=source.meta_tick,
                    request=dict(point='earlier branch independently learned before opposed discovery',metadata=meta)))
        except Exception as error:
            self.failure = error
            raise

    def capture_output(self,event,actual,*,bases,enabled,extras):
        frame = self.model.frame
        active = (self.failure is None and self.initialized and self.events is not None
                  and self.events.ready and self.events.advance and self.events.enabled and not self.events.reset and enabled)
        phase = observed_phase(frame,bases,actual,self.positions) if (active and len(self.discoveries)==2
            and frame is not None and frame.read.pc==self.pc) else None
        if phase is not None:
            self.coverage.record('reached','opposed-owned-directions',tick=event.tick,phase=phase)
        super().capture_output(event,actual,bases=bases,enabled=enabled,extras=extras)
        if phase is not None and self.failure is None:
            self.routes.append((event.tick,phase))
            self.coverage.record('checked','opposed-owned-directions',tick=event.tick,phase=phase)

    def consumer(self,source,repairs,*,phase=None):
        self.raise_failure()
        try:
            return self._consumer(source,repairs,expected_phase=phase)
        except Exception as error:
            self.failure = error
            raise

    def _consumer(self,source,repairs,*,expected_phase=None):
        selection = selection_for(self,source,pc=self.pc,positions=self.positions,targets=self.targets)
        meta = selection.metadata
        context = CheckContext(self.board.name,ScoreboardMode.DIRECT,sequence_id=source.meta_tick,
            request=dict(point='raw/qualified direction consumer',source=source,owned_metadata=meta))
        self.board.check(expected=2,actual=len(self.discoveries),context=context)
        self.board.check(expected=True,actual=source.prediction_tick>self.discoveries[-1][0],context=context)
        matches = [phase for tick,phase in self.routes if tick==source.meta_tick-4]
        self.board.check(expected=1,actual=len(matches),context=context)
        phase, = matches
        if expected_phase is not None:self.board.check(expected=expected_phase,actual=phase,context=context)
        rules = []
        if phase=='weak':
            if any(tick==source.prediction_tick+2 and p.start_pc==self.pc and p.s2_override for tick,p in repairs):
                rules.append('weak-raw-middle-selected')
            if any(tick==source.meta_tick and p.start_pc==self.pc and p.s3_override for tick,p in repairs):
                rules.append('weak-qualified-late-repair')
        else:
            if len(repairs)==1 and repairs[0][0]==source.prediction_tick+2 and repairs[0][1].s2_override:
                rules.append('strong-middle-retained')
            if self.neighbor is not None and meta[0]==self.neighbor:
                rules.append('neighbor-unmodified')
        for rule in rules:
            self.coverage.record('reached',rule,tick=source.meta_tick,phase=phase)
        selection.check(self.board,source,repairs)
        if phase=='weak':
            self.neighbor = dict(meta[0])
        else:
            self.board.check(expected=self.neighbor,actual=meta[0],context=context)
        for rule in rules:
            self.coverage.record('checked',rule,tick=source.meta_tick,phase=phase)
        return phase

    def finish(self):
        self.raise_failure()
        self.board.check(expected=2,actual=len(self.discoveries),context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT,request=dict(point='both actual branch discoveries required',accepted=self.discoveries)))
        self.coverage.finish()
