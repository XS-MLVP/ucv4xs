"""Independent parent training given genuine public metadata; retain all previous references."""
from copy import deepcopy
from bpuverify.bpu.model.bypass.policy import TrainingPolicy
from bpuverify.bpu.checker.bypass import index as _v23

class SramChecker(_v23.SramChecker):
    def __init__(self):
        super().__init__()
        self.policy=TrainingPolicy()
        self.parent_policy_checks=0
    def observe(self,phase,observation):
        row,event=observation.value,observation.event
        controls=row["policy_boundary"]
        if self.initialized:
            wanted=dict(low_tick=self.policy.low_tick,fire=int(self.policy.t1 is not None))
            if self.policy.t1 is not None:
                wanted.update(need_alloc=int(self.policy.t1["need_alloc"]),normal_mask=self.policy.t1["normal_mask"])
            self.check_sram(wanted,{key:controls[key] for key in wanted},event,table=None,
                point="independent registered T1 fire/needAlloc/mask and numeric lowTickCounter from reset")
            self.parent_policy_checks+=1
            for table,wanted in enumerate(self.policy.outputs()):
                self.check_sram(wanted,{key:row["tables"][table]["inputs"][key] for key in wanted},event,table=table,
                    point="complete alloc/update/tag/capturedCounter/useful/age derived from genuine public source")
                self.parent_policy_checks+=1
        if phase=="preedge":
            enable=row["index_boundary"]["enable"]
            reads=[dict(hit=0,position=0,useful=0) for _ in range(2)]
            if enable and self.policy.fast is not None and not row["reset"]:
                for table,reference in enumerate(self.references):
                    index=self.policy.fast["meta"]["readIndex"][table]
                    self.check_sram(index,row["tables"][table]["inputs"]["train_index"],event,table=table,
                        point="T0 exact full-index association to earlier source")
                    reads[table]=reference.outputs(dict(row["tables"][table]["inputs"],train_index=index))["train_read"]
            source=None
            if not row["reset"]:
                boundary=self.owner.control_records[-1]
                self.check_sram(event.tick,boundary["tick"],event,table=None,point="exact common preedge observation")
                fast=boundary["abtb"]["fast"]
                if fast["valid"]:
                    coherent=next(value for value in reversed(self.owner.coherent_transactions) if value["meta_tick"]==event.tick-1)
                    self.check_sram(coherent["prediction"]["start_pc"],fast["pc"],event,table=None,
                        point="complete PC of exactly associated real public source")
                    source=dict(pc=fast["pc"],position=fast["position"],taken=fast["taken"],
                        branch_type=fast["branch_type"],meta=deepcopy(coherent["meta"]["resolve"]["utage"]))
            self.policy.advance(reset=row["reset"],enable=enable,fast=source,reads=reads)
        super().observe(phase,observation)
    def finish(self):
        result=super().finish()
        result.update(parent_training_policy_checks=self.parent_policy_checks,
            numeric_aging_counter_compared_from_reset=True,
            parent_training_policy_given_real_public_metadata_checked=True,
            full_public_prediction_reference_claimed=False,
            reset_derived_failed_allocations=self.policy.failed_allocations,
            maximum_low_tick=self.policy.maximum_tick,actual_expected_aging_pulses=self.policy.age_pulses)
        return result
