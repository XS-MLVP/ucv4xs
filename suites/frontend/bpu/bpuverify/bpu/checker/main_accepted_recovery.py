"""A source may die after acceptance; its complete learning must not disappear."""
from bpuverify.common.model.configuration import *
from copy import deepcopy
from bpuverify.bpu.checker.main_original_order import Checks as OriginalChecks
from bpuverify.bpu.model.main_service import observed_counter


class Checks(OriginalChecks):
    def __init__(self,env,program):
        super().__init__(env,program)
        self.recovery_requested_at=None;self.recovery_owner=None;self.original_sequence=None
        self.recovery=None;self.first_retained=None

    def request_recovery(self,owner,original):
        self.check(None,self.recovery_requested_at,'one declared post-acceptance recovery')
        self.recovery_requested_at=self.env.checker.last_tick
        self.recovery_owner,self.original_sequence=owner.sequence,original.sequence

    def _capture_state(self,event,row):
        self.last=(event.tick,deepcopy(row))
        if row['training']['valid'] and row['training']['ready']:self.inputs.append(event.tick)
        for owner,port in enumerate(row['incoming']):
            if port['valid']:
                self.check((self.program.owner,self.program.effect),(owner,port['bits']),'complete original entry proposal keeps its logical owner')
                self.incoming.append(dict(tick=event.tick,owner=owner,bits=deepcopy(port['bits'])))
                self.check(1,len(self.incoming),'one accepted original produces one complete entry proposal')
        if row['direction']['valid']:
            self.check((1,self.program.direction),(row['direction']['ready'],observed_counter(row['direction']['bits'])),
                'one original direction affects only the corrected branch')
            self.directions.append(dict(tick=event.tick,bits=deepcopy(row['direction']['bits'])))
            self.check(1,len(self.directions),'one accepted original produces one direction obligation')
        owner=self.program.owner;port=row['writes'][owner]
        retained=(len(self.incoming)==len(self.directions)==1 and row['read']['valid'] and port['valid']
            and not port['ready'] and port['bits']==self.program.effect)
        if retained:
            self.check(1,sum(sum(v) for v in row['dirty']),'one complete retained entry, not a cancelled or duplicated copy')
            d=row['writes'][MAIN_WAYS]
            self.check((1,0,self.program.direction),(d['valid'],d['ready'],observed_counter(d['bits'])),
                'independent direction remains read-blocked beside the complete entry')
            if self.first_retained is None:self.first_retained=dict(tick=event.tick,entry=deepcopy(port['bits']))
        if self.recovery_requested_at is not None and self.recovery is None:
            records=[r for r in self.env.checker.windows.redirects if r['kind']=='external'
                and r['tick']>self.recovery_requested_at]
            if records:
                self.check(1,len(records),'one actual recovery follows the accepted original')
                record=records[0]
                self.check(self.recovery_owner,record['owner'],'recovery uses its declared actual original')
                simultaneous=getattr(self.program,'simultaneous',False)
                self.check(True,len(self.inputs)==1 and (self.inputs[0]==record['tick'] if simultaneous else self.inputs[0]<record['tick']),
                    'input was accepted at the exact declared same-boundary or strictly-earlier recovery scope')
                self.check(self.program.cancelled,self.original_sequence in record['discarded'],
                    'prediction source fate follows real recovery age, not a deleted Python receipt')
                self.recovery=deepcopy(record)
        future=self.close_when_retained
        if retained and self.recovery is not None and future is not None and not future.done():
            self.check([[] for _ in range(MAIN_WAYS+1)],self.written,'accepted effects remain pending until the compared post-recovery boundary')
            publication=self.first_retained['tick'];recovery=self.recovery['tick']
            self.check(getattr(self.program,'simultaneous',False) or self.program.moment=='publication-overlap',recovery<=publication,
                'actual recovery crosses the declared publication or already-retained boundary')
            self.retained_witness=dict(tick=event.tick,first_retained_tick=publication,
                recovery_tick=recovery,latest=deepcopy(port['bits']),all_services_blocked=True)
            future.set_result(event)

    def write_accepted(self,owner,transfer):
        self.check(True,self.retained_witness is not None,'actual service follows compared retained copy after recovery')
        self.check(True,transfer.accepted_tick>self.recovery['tick'],'accepted copy services after its source fate was checked')
        expected=self.program.direction if owner==MAIN_WAYS else self.program.effect
        actual=observed_counter(transfer.value) if owner==MAIN_WAYS else transfer.value
        self.check(True,owner in (self.program.owner,MAIN_WAYS),'unexecuted sibling receives no entry service')
        self.check(expected,actual,'full SDK-confirmed service belongs to the accepted learning')
        self.check(0,len(self.written[owner]),'one actual entry and one actual direction service only')
        super().write_accepted(owner,transfer)

    def complete(self):
        self.raise_failure()
        return tuple(map(len,self.written))==tuple(1 if i in (self.program.owner,MAIN_WAYS) else 0 for i in range(MAIN_WAYS+1))

    def summary(self):
        return dict(super().summary(),recovery=deepcopy(self.recovery),first_retained=deepcopy(self.first_retained))
