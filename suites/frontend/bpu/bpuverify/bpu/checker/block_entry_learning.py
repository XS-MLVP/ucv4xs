"""An interior entry retains its full address and exact original source."""
from dataclasses import asdict
from bpuverify.bpu.checker.early_direction_learning import EarlyDirectionChecks
from bpuverify.bpu.model.block_entry_learning import program
from bpuverify.bpu.model.early_opposition import provider


class Checks(EarlyDirectionChecks):
    def __init__(self,coverage,profile):
        self.program=program(profile); super().__init__(coverage,self.program.pc)
        self.witness=None

    def negative_consumer(self,source):
        token=self.pipeline.source_token(source)
        self.check(self.pc,token.pc,'full block-interior entry, never aligned down')
        self.check(True,self.pipeline.model.published.get(token.sequence) is token,'actual published original, not an equal copied token')
        value=provider(self.pipeline.model.sources,token)
        self.check(True,value is not None and value.table==0 and value.position==2 and value.counter<4,
            'new actual short-provider consumer of the declared interior conditional')
        branch=token.middle.branch
        self.complete_final(branch)
        super().negative_consumer(source)
        self.witness=dict(profile=self.program.name,pc=token.pc,owner=token.sequence,
            prediction_tick=source.prediction_tick,meta_tick=source.meta_tick,provider=asdict(value),
            early=asdict(token.early.branch),exact=asdict(branch),allocations=sorted(self.allocations),
            original_owner=self.pipeline.source_token(self.original).sequence,
            original_metadata_tick=self.original.meta_tick)

    def complete_final(self,branch):
        self.check((4,self.pc,2,True),(branch.position,branch.target,int(branch.kind),branch.taken),
            'complete exact-level later direct branch returns to the original interior entry')

    def snapshot(self):
        return dict(profile=self.program.name,closed=self.closed,consumer=self.witness,
            accepted_ticks=list(self.accepted_ticks),completed=sorted(self.reached_rules),
            full_FTQ_source_eligibility_proved=False)
