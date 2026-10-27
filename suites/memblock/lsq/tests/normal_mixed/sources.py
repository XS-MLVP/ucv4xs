"""Declared external Cache/TLB jobs, not native LSQ or private-state answers."""
from collections import Counter


class SourceJobs:
    def __init__(self,kind):
        assert kind in("cache","tlb")
        self.kind=kind;self.live={};self.history=[];self.cold=set();self.cursor=0;self.counts=Counter()

    def request(self,key,uid,edge,*,wanted=False):
        if wanted:self.cold.add(key)
        wanted=bool(wanted or key in self.cold)
        job=next((j for j in self.live.values() if j["key"]==key),None)
        if job is not None:
            if uid not in job["UIDs"]:job["UIDs"].append(uid)
            self.counts["merged_source_requests"]+=1
            return dict(miss=True,full=False,identity=job["identity"],job=job["job"])
        if not wanted:return dict(miss=False,full=False,identity=0,job=None)
        if len(self.live)==16:
            self.counts["full_source_rejections"]+=1
            return dict(miss=True,full=True,identity=0,job=None)
        identity=next((self.cursor+n)%16 for n in range(16) if (self.cursor+n)%16 not in self.live)
        self.cursor=(identity+1)%16
        job=dict(job=len(self.history)+1,key=key,identity=identity,UIDs=[uid],accepted_edge=edge,returned_edge=None)
        self.history.append(job);self.live[identity]=job;self.counts["accepted_external_jobs"]+=1
        self.counts["peak_live"]=max(self.counts["peak_live"],len(self.live))
        return dict(miss=True,full=False,identity=identity,job=job["job"])

    def return_actual(self,identity,edge):
        job=self.live.pop(identity)
        assert job["returned_edge"] is None and job["accepted_edge"]<edge
        job["returned_edge"]=edge;self.cold.discard(job["key"])
        self.counts["actual_interface_returns"]+=1

    def summary(self):
        return dict(kind=self.kind,counts=dict(self.counts),pending_job_IDs=[j["job"] for j in self.live.values()],jobs=self.history)
