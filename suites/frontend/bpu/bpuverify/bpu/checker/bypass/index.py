"""Complete frozen SRAM/PHR checks plus independent index token pipeline and public association."""
from copy import deepcopy
from bpuverify.bpu.model.bypass.index import IndexPipeline
from bpuverify.bpu.checker.bypass import hash as _v15

class SramChecker(_v15.SramChecker):
    def __init__(self):
        super().__init__()
        self.index_pipeline=IndexPipeline()
        self.index_tokens={}
        self.index_register_checks=self.public_index_checks=self.undefined_index_frames=0
    def observe(self,phase,observation):
        was_initialized=self.initialized
        super().observe(phase,observation)
        row,event=observation.value,observation.event
        model=self.index_pipeline
        expected=deepcopy(model.a2)
        self.index_tokens[event.tick]=expected
        if was_initialized and expected is not None:
            self.check_sram(expected["indices"],row["index_boundary"]["meta_indices"],event,table=None,
                point="independent a0/a1/a2/a3 index fire/override/hold registers")
            self.index_register_checks+=1
        else:
            self.undefined_index_frames+=1
        if phase=="rising" and self.owner.coherent_transactions:
            actual=self.owner.coherent_transactions[-1]
            if actual["meta_tick"]==event.tick:
                token=self.index_tokens[actual["prediction_tick"]]
                if token is not None:
                    self.check_sram(token["indices"],tuple(actual["meta"]["resolve"]["utage"]["readIndex"]),
                        event,table=None,point="full public metadata matches EXACT associated index token, no fixed-latency guess")
                    self.public_index_checks+=1
        if phase=="preedge":
            controls=row["index_boundary"]
            values=row["hash_inputs"]
            model.advance(reset=row["reset"],enable=controls["enable"],fire0=controls["fire0"],
                fire2=controls["fire2"],s2=values["s2_override"],s3=values["s3_override"],
                pc=values["pc"],normal_folds=values["normal_folds"],tick=event.tick)
    def finish(self):
        result=super().finish()
        result.update(index_register_checks=self.index_register_checks,public_index_checks=self.public_index_checks,
            undefined_index_frames=self.undefined_index_frames,index_pipeline_has_no_fixed_delay=True)
        return result
