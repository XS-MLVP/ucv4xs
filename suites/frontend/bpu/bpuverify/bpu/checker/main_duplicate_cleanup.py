"""Compare operations by identity/destination, including first wrong service."""
from copy import deepcopy
from bpuverify.bpu.checker.main_original_order import Checks as OriginalChecks
from bpuverify.bpu.model.main_service import observed_counter
from bpuverify.mbtb.model.semantic import coordinate


class Checks(OriginalChecks):
    def __init__(self,env,program):
        super().__init__(env,program);self.parents=[]

    def _capture_state(self,event,packet):
        row=packet['state'];self.last=(event.tick,deepcopy(row))
        if row['training']['valid'] and row['training']['ready']:self.inputs.append(event.tick)
        if any(v['valid'] for v in packet['parent'].values()):
            self.parents.append(dict(tick=event.tick,**deepcopy(packet['parent'])))
        for owner,port in enumerate(row['incoming']):
            if port['valid']:self.incoming.append(dict(tick=event.tick,owner=owner,bits=deepcopy(port['bits'])))
        if row['direction']['valid']:self.directions.append(dict(tick=event.tick,bits=deepcopy(row['direction']['bits'])))

    def write_accepted(self,owner,transfer):
        # Keep the actual offending event too. No silent rebasing to RTL.
        ordinal=len(self.written[owner]);super().write_accepted(owner,transfer)
        if owner==2:
            self.check(True,self.program.concurrent,'cleanup-only has no fresh direction learning')
            self.check(0,ordinal,'one independently accepted direction update')
            self.check(dict(row=coordinate(self.program.neighbor)[2],mask=1,values={'0':2}),
                observed_counter(transfer.value),'complete direction reset belongs to the independently corrected branch')
            return
        expected=self.program.expected_services[owner]
        self.check(True,ordinal<len(expected),'clear services only the declared duplicate destination')
        self.check(expected[ordinal],transfer.value,'complete service preserves the survivor and independent learned branch')

    def complete(self):
        self.raise_failure()
        return tuple(map(len,self.written))==(int(self.program.concurrent),1,int(self.program.concurrent))

    def summary(self):return dict(super().summary(),parent_operations=deepcopy(self.parents))
