"""Compare complete logical requests and services, not just the final target."""
from copy import deepcopy
from toffee import CheckContext,Scoreboard,ScoreboardMode
from suites.frontend.bpu.mbtb.driver.feedback import expected_mbtb_feedback,observed_mbtb_feedback
from suites.frontend.bpu.mbtb.monitor.entry import ENTRY_FIELDS
from suites.frontend.bpu.mbtb.model.cleanup import mbtb_entry_slot,expected_mbtb_cleanup_states
from suites.frontend.bpu.mbtb.case.resident_scenario import snapshot


def activities(trace,direction):
    result=[]
    for frame in trace.frames:
        for align,row in enumerate(frame.value['banks']):
            for bank,ports in enumerate(row):
                for owner,port in enumerate(ports):
                    if port[direction+'_valid'] and (direction=='write' or port['read_ready']):
                        result.append(dict(tick=frame.event.tick,align=align,bank=bank,owner=owner,
                            bits={key:port[direction+'_'+key] for key,_ in ENTRY_FIELDS}))
    return result


class Checks:
    def __init__(self,agent,program,prepared,evidence):
        self.agent,self.program,self.prepared,self.evidence=agent,program,prepared,evidence
        self.board=Scoreboard('mbtb.shared-service-no-loss')
    def check(self,expected,actual,point):
        self.board.check(expected=expected,actual=actual,context=CheckContext(self.board.name,
            ScoreboardMode.DIRECT,request=dict(point=point,program=self.program.state(),evidence=self.evidence)))
    def effects(self,trace,shadows,coverage):
        p=self.prepared;requests=activities(trace,'write');services=activities(trace,'read')
        actual_feedback=[observed_mbtb_feedback(f.value) for f in trace.feedback]
        self.evidence.update(requests=requests,services=services,accepted_ticks=[f.event.tick for f in trace.feedback],
            actual_feedback=actual_feedback,retained_before=p['retained_before'],capacity_before=p['capacity_before'])
        expected_feedback=expected_mbtb_feedback(p['transaction'],branch_count=len(self.agent.ports.training.bits.branches))
        self.check([expected_feedback],actual_feedback,'exactly one immutable complete normal feedback accepted')
        coverage.reach('complete-feedback-accepted')
        normal={key:value for key,value in mbtb_entry_slot(p['updated']).items() if key not in ('valid','dirty')}
        clear=dict(set_idx=(p['first'].pc>>5)&63,tag=0,branch_type=0,ras_action=0,position=0,carry=0,lower=0)
        wanted=[dict(align=0,bank=0,owner=0,bits=normal),dict(align=0,bank=0,owner=1,bits=clear)]
        self.check(wanted,[{k:v for k,v in r.items() if k!='tick'} for r in requests],
            'first clear and complete correction use distinct request sources')
        self.check(1,len({r['tick'] for r in requests}),'first ever clear actually meets normal correction at one boundary')
        matching=[s.value['banks'][0][0] for s in shadows if s.event.tick==requests[0]['tick']]
        self.check(1,len(matching),'one passive pre-collision retained-state snapshot')
        self.evidence['pre_collision_shadow']=deepcopy(matching[0])
        if self.program.shared:
            prior=p['retained_before']
            self.check(mbtb_entry_slot(p['neighbor']),matching[0][prior['owner']][prior['rank']],
                'the genuine neighbor still occupies its already-served retained record before collision')
            self.check([0,0],[slot['dirty'] for slot in matching[0][1]],
                'both service positions are available before the two accepted obligations')
        coverage.reach('first-clear-meets-correction')
        wanted[0]['owner']=1 if self.program.shared else 0
        self.evidence['expected_services']=deepcopy(wanted)
        key=lambda r:(r['align'],r['bank'],r['owner'],r['bits']['set_idx'])
        self.check(sorted(wanted,key=key),sorted([{k:v for k,v in r.items() if k!='tick'} for r in services],key=key),
            'capacity-safe distinct target correction and invalidation both service exactly once')
        coverage.reach('both-destination-services')
    def wanted_consumers(self):
        p=self.prepared
        return expected_mbtb_cleanup_states(snapshot(p['duplicate']),snapshot(p['before_neighbor']),
            p['first'].pc,0,1 if self.program.shared else 0,p['updated'].target)
    def originals(self):
        self.check(self.prepared['originals'],tuple(s.meta_entries for s in self.prepared['sources']),
            'all old original snapshots preserved')

    async def diagnose_consumer(self):
        """Read after a primary service failure; never turn it into a PASS.

        The normal prediction Scoreboard and default independent reference
        remain active. Retain its concrete expected/actual public fields as
        secondary evidence without replacing the first lost-service failure.
        """
        pc=self.prepared['neighbor'].pc
        try:
            await self.agent.predict(pc)
        except Exception as error:
            actual=getattr(error,'actual',None);expected=getattr(error,'expected',None)
            self.evidence['fresh_consumer_failure']=dict(pc=pc,error_type=type(error).__name__,
                expected=expected if isinstance(expected,dict) else repr(expected),
                actual=actual if isinstance(actual,dict) else repr(actual))
        else:
            self.evidence['fresh_consumer_failure']=dict(pc=pc,error_type=None)
