"""Independent TAGE state plus exact mixed-beat and delayed-consumer checks."""
from toffee import CheckContext,ScoreboardMode

from suites.frontend.bpu.bpu.checker.assertions import mbtb_counter_for_position
from suites.frontend.bpu.bpu.checker.tage.semantic import TageSemanticComponentChecker
from suites.frontend.bpu.bpu.checker.tage.selection import selection_for
from suites.frontend.bpu.bpu.model.tage.interleaved import PC,RESOLVED,TRACKED,UNTRACKED,OWNERS,target
from suites.frontend.bpu.tage.model.semantic import Branch,Feedback,Hint


def hint(meta):
    return Hint(bool(meta['hasProvider']),bool(meta['hasAlt']),bool(meta['useProvider']),
        meta.get('providerTableIdx',0),meta.get('providerWayIdx',0),meta.get('providerTakenCtr_value',0),
        meta.get('providerUsefulCtr_value',0),bool(meta['altOrBasePred']),bool(meta['altConf']))


class InterleavedLearningChecker(TageSemanticComponentChecker):
    def __init__(self,coverage):
        super().__init__()
        self.coverage,self.pending,self.accepted = coverage,None,None
        self.learned = False
        self.discovered = set()
        self.reset_tick = None
        self.main_counters = {}

    def check(self,expected,actual,point,source=None):
        self.raise_failure()
        try:
            self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,
                ScoreboardMode.DIRECT,sequence_id=None if source is None else source.meta_tick,
                request=dict(point=point,pending=self.pending,accepted=self.accepted,
                    source=source,state=self.model.state())))
        except Exception as error:
            self.failure = error
            raise

    def frame(self,source):
        self.raise_failure()
        self.check(True,self.reset_tick is None or source.prediction_tick>self.reset_tick,'source survives current reset epoch',source)
        matches = [(frame,bases,enabled) for tick,frame,_,enabled,bases in self.expected if tick==source.meta_tick-4]
        self.check(1,len(matches),'exact public source frame',source)
        frame,bases,enabled = matches[0]
        self.check(True,enabled and frame is not None,'source is a live enabled request',source)
        self.check((PC,4),(frame.read.pc,source.meta_tick-source.prediction_tick),'source PC and causal window',source)
        return frame,bases

    def prepared(self,source,position,stage):
        self.check(True,position in TRACKED and stage in ('main-only','allocated','strong'),
            'known tracked branch preparation stage',source)
        meta = self.source_expected(source,position)
        if stage=='main-only':
            self.check(0,meta['hasProvider'],'new MainBTB branch has no old TAGE owner',source)
            return
        owner = OWNERS[TRACKED.index(position)]
        self.check((1,*owner,3 if stage=='allocated' else 2,0,0),tuple(meta.get(name) for name in
            ('hasProvider','providerTableIdx','providerWayIdx','providerTakenCtr_value','providerUsefulCtr_value','hasAlt')),
            'independently forecast negative owner before mixed feedback',source)

    def base_counter(self,source,position):
        self.raise_failure()
        try:return mbtb_counter_for_position(source,position)
        except Exception as error:
            self.failure = error
            raise

    def consumer(self,source,repairs):
        frame,bases = self.frame(source)
        positions = tuple(frame.positions[slot] for slot,base in enumerate(bases) if base.valid)
        self.check(True,bool(positions),'real MainBTB consumer required',source)
        known = set(TRACKED)|self.discovered
        if self.pending is not None and self.pending[0]=='discovery':known.add(self.pending[2].branches[-1].position)
        self.check(True,set(positions)<=known,
            'consumer contains only normally learned program branches',source)
        selection = selection_for(self,source,pc=PC,positions=positions,targets=tuple(target(p) for p in positions))
        try:selection.check(self.board,source,repairs)
        except Exception as error:
            self.failure = error
            raise

    def arm_learning(self,source):
        self.check(None,self.pending,'no overlapping unconsumed learning obligation',source)
        self.check(False,self.learned,'mixed beat is accepted only once',source)
        frame,_ = self.frame(source)
        branches = []
        for position in RESOLVED:
            if position in TRACKED:
                meta = self.source_expected(source,position)
                self.prepared(source,position,'strong')
                self.check((2,1,1),(self.base_counter(source,position),meta['useProvider'],meta['altOrBasePred']),
                    'correct NT provider opposes real taken MainBTB base',source)
                branches.append(Branch(position,False,1,False,True,2,hint(meta)))
            else:
                branches.append(Branch(position,False,1,False,False))
        self.pending = ('learning',source,Feedback(PC,frame.read.context,tuple(branches)),RESOLVED)

    def arm_discovery(self,source,position):
        self.check(None,self.pending,'prior result consumed before a new discovery',source)
        self.check(True,self.learned and position in UNTRACKED and position not in self.discovered,
            'new public discovery of a formerly unmatched branch',source)
        frame,bases = self.frame(source)
        residents = {frame.positions[slot] for slot,base in enumerate(bases) if base.valid}
        self.check(True,residents<=self.main_counters.keys(),'only known prior branches can precede a discovery',source)
        self.check(False,position in residents,'new discovery was genuinely not a resident MainBTB branch',source)
        branches = []
        positions = tuple(p for p in RESOLVED if p<=position)
        for resolved in positions:
            matched = resolved in residents
            meta = self.source_expected(source,resolved) if matched else None
            counter = self.main_counters[resolved] if matched else 0
            if matched:self.check(counter,self.base_counter(source,resolved),'previously resolved logical base retained',source)
            branches.append(Branch(resolved,resolved==position,1,resolved==position,matched,counter,
                Hint() if meta is None else hint(meta)))
        self.pending = ('discovery',source,Feedback(PC,frame.read.context,tuple(branches)),
            positions+(None,)*(8-len(positions)))

    def capture_input(self,event,events,*,resolve_slots=()):
        super().capture_input(event,events,resolve_slots=resolve_slots)
        if self.failure is not None:return
        if events.reset:
            self.pending = self.accepted = None
            self.learned = False
            self.discovered.clear()
            self.main_counters.clear()
            self.reset_tick = event.tick
            self.expected.clear()
            self.resolve_slots.clear()
            self.accepted_feedback.clear()
            return
        if self.pending is None or self.model.accepted is None:return
        try:
            kind,source,expected,slots = self.pending
            self.check(None,self.accepted,'one actual acceptance per planned obligation',source)
            self.check((expected,slots),(self.model.accepted.feedback,resolve_slots),
                'complete actual feedback identity, qualification, hints and slot vector',source)
            self.check(True,event.tick>source.meta_tick,'feedback follows its original checked source',source)
            self.accepted = event.tick,kind
            if kind=='discovery':
                for branch in expected.branches:
                    if branch.matched:
                        self.main_counters[branch.position]=max(0,min(3,branch.base_counter+(1 if branch.taken else -1)))
                self.main_counters[expected.branches[-1].position]=2
            rules = ('interleaved-valid-feedback','position-qualified-owners','correct-opposed-learning',
                'all-owned-results-consumed','untracked-feedback-filtered') if kind=='learning' else (
                    'no-accidental-provider-on-discovery',)
            for rule in rules:self.coverage.record('reached',rule,accepted_tick=event.tick)
        except Exception as error:self.failure = error

    def consume_learning(self,source,repairs):
        self.check(True,self.pending is not None and self.pending[0]=='learning' and self.accepted is not None,
            'actual mixed feedback precedes its effect',source)
        self.check(True,source.prediction_tick>self.accepted[0],'new lookup after actual mixed acceptance',source)
        for position,owner in zip(TRACKED,OWNERS,strict=True):
            meta = self.source_expected(source,position)
            self.check((1,*owner,1,1),tuple(meta.get(name) for name in
                ('hasProvider','providerTableIdx','providerWayIdx','providerTakenCtr_value','providerUsefulCtr_value')),
                'all four original owners independently decrement and gain usefulness',source)
            self.check(1,self.base_counter(source,position),'MainBTB consumes the same resolved NT branch',source)
        self.consumer(source,repairs)
        for rule in ('interleaved-valid-feedback','position-qualified-owners','correct-opposed-learning','all-owned-results-consumed'):
            self.coverage.record('checked',rule,metadata_tick=source.meta_tick)
        self.pending,self.accepted,self.learned = None,None,True
        self.main_counters = dict.fromkeys(TRACKED,1)

    def consume_discovery(self,source,position,repairs):
        self.check(True,self.pending is not None and self.pending[0]=='discovery' and self.accepted is not None,
            'real accepted discovery precedes its provider absence check',source)
        self.check(position,self.pending[2].branches[-1].position,'discovery belongs to the accepted taken tail',source)
        self.check(True,source.prediction_tick>self.accepted[0],'new lookup after actual discovery',source)
        meta = self.source_expected(source,position)
        self.check((0,2),(meta['hasProvider'],self.base_counter(source,position)),
            'new MainBTB record must not reveal an accidentally learned TAGE provider',source)
        self.consumer(source,repairs)
        self.discovered.add(position)
        self.pending,self.accepted = None,None
        if self.discovered==set(UNTRACKED):
            for rule in ('untracked-feedback-filtered','no-accidental-provider-on-discovery'):
                self.coverage.record('checked',rule,metadata_tick=source.meta_tick)

    def finish(self):
        self.check((True,set(UNTRACKED),None,None),(self.learned,self.discovered,self.pending,self.accepted),
            'all tracked effects and all originally untracked consumers required')
        self.coverage.finish()
