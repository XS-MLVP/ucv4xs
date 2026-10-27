"""Learning belongs to the old request's branch, not today's table or same PC."""
from toffee import CheckContext,Scoreboard,ScoreboardMode

from bpuverify.bpu.model.main_sources import source_entries


class MainLearningChecks:
    def __init__(self,pipeline,pc,target,position,coverage):
        self.pipeline,self.pc,self.target,self.position,self.coverage = pipeline,pc,target,position,coverage
        self.board = Scoreboard('bpu.owned-main-learning')
        self.pending = None
        self.owner = None
        self.transitions = []
        self.failure = None

    def check(self,expected,actual,point):
        if self.failure is not None:raise self.failure
        try:
            self.pipeline.raise_failure()
            self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,ScoreboardMode.DIRECT,
                request=dict(point=point,pending=self.pending,owner=self.owner)))
        except Exception as error:
            self.failure = error
            raise

    def matching(self,token):
        return [(align,way,entry.counter) for align,row in enumerate(source_entries(token.lookup))
            for way,entry in enumerate(row) if entry.hit and entry.position==self.position]

    def accepted(self,event,taken):
        tick,resolution = event
        self.check(None,self.pending,'prior accepted effect consumed before a new update')
        self.check(True,resolution.origin is not None,'exact immutable lookup owner')
        self.check((self.pc,((self.position,self.target,1,taken,True,0),)),
            (resolution.pc,tuple((branch.position,branch.target,int(branch.kind),branch.taken,branch.mispredict,
                int(branch.action)) for branch in resolution.branches if branch is not None)),
            'complete accepted source-qualified outcome')
        hits = self.matching(resolution.origin)
        self.check(0 if not self.transitions else 1,len(hits),'source has exactly the expected logical branch')
        if hits:
            self.check(self.owner,hits[0][:2],'accepted update retains its original physical owner')
        expected = (None,True) if not self.transitions else (2,False) if len(self.transitions)==1 else (1,True)
        self.check(expected,(None if not hits else hits[0][2],taken),'semantic learning sequence, not phase labels')
        self.pending = tick,resolution,expected[0]
        if expected[0] is None:rules=('cold-source-learned','main-result-consumed')
        elif not taken:rules=('same-owner-decremented','main-direction-repairs-micro')
        else:rules=('same-owner-recovered',)
        for rule in rules:self.coverage.record('reached',rule,tick)

    def observed(self,source,counter,corrected):
        self.check(True,self.pending is not None,'real accepted update precedes lookup effect')
        token = self.pipeline.source_token(source)
        hits = self.matching(token)
        self.check(1,len(hits),'one matching owned logical branch')
        align,way,value = hits[0]
        if self.owner is None:self.owner = align,way
        self.check((self.owner,counter,corrected,self.pc,1,self.target,self.position),
            ((align,way),value,token.middle_corrected,source.prediction.start_pc,source.prediction.taken,
                source.prediction.target,source.prediction.position),'owned direction effect and real MicroBTB consumer')
        self.check((not corrected,not corrected),(token.middle.branch.taken,
            token.middle.branch.target==self.target),'independently selected MainBTB corrects or agrees')
        accepted,resolution,before = self.pending
        self.check(True,source.prediction_tick>accepted,'new lookup follows its actual update')
        rules=(('cold-source-learned','main-result-consumed') if before is None else
            ('same-owner-decremented','main-direction-repairs-micro') if not resolution.branches[0].taken else
            ('same-owner-recovered',))
        for rule in rules:self.coverage.record('checked',rule,source.meta_tick)
        self.transitions.append((before,value,corrected))
        self.pending = None

    def finish(self):
        self.check(None,self.pending,'all accepted learning effects observed')
        self.check(((None,2,False),(2,1,True),(1,2,False)),tuple(self.transitions),
            'cold learning, independent correction and same-owner recovery all required')
        self.coverage.finish()
