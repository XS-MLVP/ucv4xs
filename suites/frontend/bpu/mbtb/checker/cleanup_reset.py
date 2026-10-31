"""Semantic branch lifetime and real cleanup qualification, with failure state."""
from toffee import CheckContext,Scoreboard,ScoreboardMode
from suites.frontend.bpu.mbtb.model.semantic import coordinate,tag


class Checks:
    def __init__(self,program):
        self.program,self.phase=program,'preparation'
        self.board=Scoreboard('mbtb.cleanup-reset-lifetime')

    def check(self,expected,actual,point):
        self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT,request=dict(program=self.program.state(),phase=self.phase,point=point)))

    def cold(self,prediction):
        self.check((0,0),(sum(entry.valid for entry in prediction.entries),
            sum(source['rawHit'] for row in prediction.meta_entries for source in row)),
            'no visible or filtered old record in the new reset epoch')

    def resident(self,prediction,branch,*,counter):
        matches=[entry for entry in prediction.entries if entry.valid]
        self.check(1,len(matches),'one complete new instruction, not a retained old duplicate')
        entry=matches[0]
        self.check((branch.target,branch.position,branch.kind,0,int(counter>=2)),
            (entry.target,entry.position,entry.branch_type,entry.ras_action,entry.taken),
            'complete branch payload and independently learned direction')
        sources=[source for row in prediction.meta_entries for source in row if source['rawHit']]
        self.check(1,len(sources),'one new raw-hit owner')
        self.check((branch.position,branch.kind,0,counter),
            (sources[0]['position'],sources[0]['attribute']['branchType'],
             sources[0]['attribute']['rasAction'],sources[0]['counter_value']),
            'new type and counter belong to the new instruction lifetime')

    def duplicate(self,prediction):
        self.check(2,sum(entry.valid for entry in prediction.entries),'real original duplicate visible at the public output')
        values=sorted((entry.target,entry.position,entry.branch_type,entry.ras_action)
            for entry in prediction.entries if entry.valid)
        self.check(sorted((b.target,b.position,b.kind,0) for b in (self.program.old,self.program.changed)),
            values,'two distinct complete targets for the same old logical branch')
        sources=[source for row in prediction.meta_entries for source in row if source['rawHit']]
        self.check(2,len(sources),'real duplicate raw-hit metadata')
        self.check([(self.program.old.position,self.program.old.kind)]*2,
            sorted((source['position'],source['attribute']['branchType']) for source in sources),
            'both old raw sources describe the same instruction')

    def stage(self,receipts,native):
        if self.program.profile=='observed-not-consumed':
            self.check((False,()),(bool(receipts),tuple(native['clears'])),
                'cached duplicate without actual consumption is not a cleanup request')
            return
        self.check(True,bool(receipts),'real S2 consumption before reset')
        self.check(True,bool(native['clears']),'registered invalidation exists, not merely a duplicate observation')
        align,bank,row=coordinate(self.program.old.pc)
        for receipt in receipts:
            self.check((align,bank,row,3,tag(self.program.old.pc),self.program.old.position%16),
                tuple(receipt[name] for name in ('align','bank','row','way','tag','position')),
                'cleanup receipt belongs to the declared original duplicate, not a different instruction')
            self.check(True,0<receipt['tick']<native['tick'],'consumption precedes this fresh registered request')
        owner={(receipt['align'],receipt['bank'],receipt['row'],receipt['way']) for receipt in receipts}
        observed={(clear['align'],clear['bank'],clear['row'],clear['way']) for clear in native['clears']}
        self.check(owner,observed,'registered invalidation belongs to the original cleanup destination')
        for clear in native['clears']:
            self.check((0,0,0,0,0,0),tuple(clear[name] for name in ('tag','position','kind','action','carry','lower')),
                'clear is an explicit invalidation, not a new branch entry')
