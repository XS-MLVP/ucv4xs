"""No MainBTB/history cut point: all inputs and repair records have own tokens."""
from toffee import CheckContext,ScoreboardMode

from suites.frontend.bpu.bpu.model.main_sources import source_entries


STAGES = ('main','short','short-strong','promotion','base','strong')
OUTCOMES = ((True,True),(False,True),(False,False),(True,True),(True,True),(True,True))
RULES = {'main':(), 'short':('source-qualified-short-learning',),'short-strong':(),
    'promotion':('promotion-retains-short-alternate',),
    'base':('base-only-update-preserves-tage','owned-raw-middle-consumer','owned-alternate-late-repair'),
    'strong':('owned-strong-provider-retained',)}


class DirectionLearningChecks:
    def __init__(self,pipeline,pc,position,target,coverage):
        self.pipeline,self.pc,self.position,self.target,self.coverage = pipeline,pc,position,target,coverage
        self.pending,self.steps = None,[]
        self.failure = None

    def check(self,expected,actual,point):
        if self.failure is not None:raise self.failure
        try:
            self.pipeline.raise_failure()
            self.pipeline.board.check(expected=expected,actual=actual,context=CheckContext(self.pipeline.board.name,
                ScoreboardMode.DIRECT,request=dict(point=point,pending=self.pending,completed=self.steps)))
        except Exception as error:
            self.failure = error
            raise

    def owner(self,token):
        matches = [(align*5+way,entry) for align,row in enumerate(source_entries(token.lookup))
            for way,entry in enumerate(row) if entry.hit and entry.position==self.position]
        self.check(1,len(matches),'exact owned conditional MainBTB branch')
        return matches[0]

    def accepted(self,event,stage):
        self.check(None,self.pending,'prior effect consumed before new learning')
        self.check(STAGES[len(self.steps)],stage,'all semantic learning transitions required in order')
        tick,resolution = event
        self.check(True,resolution.origin is not None,'actual feedback belongs to exact published token')
        taken,wrong = OUTCOMES[len(self.steps)]
        self.check((self.pc,((self.position,self.target,1,taken,wrong,0),)),
            (resolution.pc,tuple((branch.position,branch.target,int(branch.kind),branch.taken,branch.mispredict,
                int(branch.action)) for branch in resolution.branches if branch is not None)),
            'complete accepted source-qualified outcome')
        controls = self.pipeline.last_resolution_controls
        self.check((tick,stage!='base'),(controls[0],bool(controls[1][2] and controls[1][3])),
            'base-only feedback must actually disable TAGE learning')
        receipts = [at for at,token in self.pipeline.source_receipts.items() if token is resolution.origin]
        self.check(1,len(receipts),'one exact actual public source receipt')
        self.pending = tick,resolution,stage,receipts[0]
        for rule in RULES[stage]:self.coverage.record('reached',rule,tick)

    def observed(self,source,stage):
        self.check(True,self.pending is not None,'accepted update precedes its consumer')
        tick,resolution,actual_stage,old_receipt = self.pending
        self.check(actual_stage,stage,'consumer closes its own accepted transition')
        token = self.pipeline.source_token(source)
        self.check(True,source.prediction_tick>tick,'new lookup follows actual acceptance')
        slot,entry = self.owner(token)
        metadata = self.pipeline.model.sources.defined_metadata(token)
        wanted = {
            'main':(2,0,None,None,0,None,None),
            'short':(1,1,2,3,0,0,0),
            'short-strong':(0,1,2,2,0,1,0),
            'promotion':(1,1,3,4,1,0,0),
            'base':(2,1,3,4,1,0,0),
            'strong':(3,1,3,5,1,1,1),
        }[stage]
        names = ('hasProvider','providerTableIdx','providerTakenCtr_value','hasAlt','useProvider','altOrBasePred')
        actual = (entry.counter,)+tuple(metadata.get(f'{slot}.{field}') for field in names)
        # Provider-less payload is undefined, except hasProvider/hasAlt/use
        # and alternative/base direction, all of which are defined.
        if stage=='main':
            actual=(entry.counter,metadata[f'{slot}.hasProvider'],None,None,metadata[f'{slot}.hasAlt'],None,None)
        self.check(wanted,actual,'independent MainBTB and TAGE effects for this exact source')
        expected_stages = (2,) if stage in ('main','strong') else (2,3) if stage in ('promotion','base') else ()
        self.check(tuple((source.prediction_tick+2*(value-1),value) for value in expected_stages),
            self.pipeline.corrections_for_source(source),'all compared corrections of this source, including unexpected ones')
        if stage=='base':
            self.check((True,False),(entry.counter>=2,self.pipeline.model.sources.snapshot(token,resolved=True).late.branch.taken),
                'owned alternate defeats an opposing independently learned MainBTB base')
        if stage=='strong':
            self.check((1,0),(metadata[f'{slot}.providerUsefulCtr_value'],metadata[f'{slot}.altConf']),
                'strong provider gains useful while updated positive alternate remains weak')
        closed = RULES[stage] if stage!='short' else ()
        if stage=='short-strong':closed=('source-qualified-short-learning',)
        for rule in closed:self.coverage.record('checked',rule,source.meta_tick)
        self.steps.append(stage)
        self.pending = None
        self.pipeline.retire_source(old_receipt)

    def finish(self):
        self.check((STAGES,None),(tuple(self.steps),self.pending),'all six accepted transitions and consumers required')
        self.coverage.finish()
