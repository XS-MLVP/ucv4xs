"""MicroTAGE training/aging policy given genuine public metadata and reset-derived reads."""
from copy import deepcopy
from bpuverify.bpu.case.bypass.history_plan import full_tags

def derive(fast,reads):
    meta=fast["meta"]
    entries=meta["abtbResult"]
    mispred=[]
    for way,entry in enumerate(entries):
        prediction=entry["predTaken"] if entry["hit"] else entry["baseTaken"]
        wrong=(fast["branch_type"]==1 and fast["position"]==entry["cfiPosition"] and prediction!=fast["taken"]
            or fast["position"]>entry["cfiPosition"] and prediction)
        if entry["valid"] and wrong:
            mispred.append(way)
    # CompareMatrix uses strict '<' above its diagonal and its inverse below:
    # equal positions therefore select the HIGHEST way, unlike PriorityEncoder.
    chosen=min(mispred,key=lambda way:(entries[way]["cfiPosition"],-way)) if mispred else None
    selected=None if chosen is None else entries[chosen]
    provider=(1<<selected["tableId"]) if selected is not None and selected["hit"] else 0
    lower_fill=provider|(provider-1) if provider else 0
    keep=sum(int(bool(read["useful"]))<<table for table,read in enumerate(reads))
    candidates=(~(lower_fill|keep))&3
    mask=candidates&-candidates
    allocate_taken=1-int(selected["predTaken"] if selected["hit"] else selected["baseTaken"]) if selected is not None else 1
    folded=[value["foldedHist"] for value in meta["foldedPathHistForTrain_hist"]]
    tags=full_tags(fast["pc"],folded)
    tables=[]
    for table,read in enumerate(reads):
        eligible=[entry for entry in entries if entry["valid"] and entry["hit"] and entry["tableId"]==table
            and entry["cfiPosition"]<=fast["position"]
            and not(read["hit"] and read["position"]!=entry["cfiPosition"])]
        update=eligible[0] if eligible else None
        result=dict(allocate=int(bool(mispred) and bool(mask&(1<<table))),update=int(update is not None))
        if result["allocate"]:
            result.update(allocate_taken=allocate_taken,allocate_position=selected["cfiPosition"],tag=tags[table]&255)
        if update is not None:
            taken=int(update["cfiPosition"]==fast["position"] and fast["taken"])
            result.update(tag=tags[table]&255,update_taken=taken,update_position=update["cfiPosition"],
                update_counter=update["takenCtr_value"],
                useful_valid=int(update["predTaken"]!=taken or (update["baseTaken"]!=update["predTaken"] and update["predTaken"]==taken)),
                useful_increase=int(update["predTaken"]==taken and update["baseTaken"]!=update["predTaken"]))
        assert not(result["allocate"] and result["update"])
        tables.append(result)
    return dict(need_alloc=bool(mispred),normal_mask=mask,selected_mispredict_way=chosen,
        train_indices=deepcopy(meta["readIndex"]),tables=tables,fast=deepcopy(fast))

class TrainingPolicy:
    def __init__(self):
        self.reset()
    def reset(self):
        self.fast=self.t1=None
        self.low_tick=0
        self.failed_allocations=self.age_pulses=0
        self.maximum_tick=0
    def outputs(self):
        age=int(bool(self.low_tick&128))
        tables=[dict(allocate=0,update=0,age=age) for _ in range(2)]
        if self.t1 is not None:
            tables=[dict(values,age=age) for values in self.t1["tables"]]
        return tables
    def advance(self,*,reset,enable,fast,reads):
        if reset:
            self.reset()
            return
        if self.low_tick&128:
            self.age_pulses+=1
            self.low_tick=0
        elif self.t1 is not None and self.t1["need_alloc"] and not self.t1["normal_mask"]:
            self.low_tick+=1
            self.failed_allocations+=1
        self.maximum_tick=max(self.maximum_tick,self.low_tick)
        self.t1=derive(self.fast,reads) if enable and self.fast is not None else None
        self.fast=deepcopy(fast)
