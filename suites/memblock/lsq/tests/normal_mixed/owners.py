"""Original eight-kind/random domain with explicit normal source obligations.

All target RTL/shared references/legacy results remain unchanged. This actor
inherits real effect checking, not an internal DUT/reference oracle.
"""
from dataclasses import asdict,replace
import json
from pathlib import Path
import random

from lsqverify.replay.types import Cause,Refill,TlbHint
from tests.lsq_wrapper.ldu_s4_mixed_owners import LduS4MixedOwners
from .sources import SourceJobs
from .check import NormalMixedCheck,CheckedEnv


class NormalProducerMixedOwners(LduS4MixedOwners):
    def __init__(self,env,seed):
        self.source_rng=random.Random(seed^0xCAC17B)
        self.cache_sources=SourceJobs("cache");self.tlb_sources=SourceJobs("tlb")
        self.source_check=NormalMixedCheck(seed)
        super().__init__(CheckedEnv(env,self.source_check),seed)
        self.random_steps=0;self.redirect_source=None

    def redirect(self,order,source):
        packet=super().redirect(order,source)
        if packet is not None:self.redirect_source=source
        return packet

    def make(self,kind,*,unique=False):
        s=super().make(kind,unique=unique)
        if s["kind"]=="load":
            p=s["load"];q=p.execution
            base={"nc_load":0x30000000,"mmio_load":0x40000000,"io_load":0x50000000}.get(kind)
            va=q.vaddr if base is None else base+q.vaddr%0x100000
            pa=0xE0000000+p.paddr%0x100000 if kind=="io_load" else p.paddr
            s["load"]=replace(p,execution=replace(q,vaddr=va),fullva=va,paddr=pa,hyper=False,nonleaf=False)
            s["cache_intent_exercised"]=s["tlb_intent_exercised"]=False
        else:
            p=s["owner"];base={"nc_store":0x30000000,"io_store":0x40000000}.get(kind)
            s["owner"]=replace(p,hyper=False,vaddr=p.vaddr if base is None else base+p.vaddr%0x100000)
        self.source_check.declare_instruction(s["uid"],s["order"],s["subtype"],s["position"],
                                              asdict(s["load"] if s["kind"]=="load" else s["owner"]))
        return s

    def ticket(self,s,*,tail=False,uncache=False):
        item=super().ticket(s,tail=tail,uncache=uncache)
        item["sampled_extra"]=item["extra"]
        if not tail and not s.get("cache_intent_exercised",True) and s["extra"] in(Cause.CACHE_MISS,Cause.CACHE_REPLAY,Cause.BANK_CONFLICT):
            item["sampled_extra"]=item["extra"]=s["extra"]
        item.update(source_mshr=0,source_handled=False,source_tlb_id=0,source_tlb_full=False,source_tlb_job=None,cause_vector=0)
        return item

    def cause(self,item,*,rar_denied=False,raw_denied=False,current_nuke=False):
        s=item["s"];f=item["flags"];unc=s["subtype"]!="cached"
        # NewLoadUnit1170-1171 samples the filter in S2, not at S0. A
        # completed PTW job matching this still-miss request is full as well
        # (Repeater291); retaining stale full=0 would lose its earlier hint.
        job_id=item["source_tlb_job"]
        if item["extra"]==Cause.TLB_MISS and job_id is not None:
            job=self.tlb_sources.history[job_id-1];hint=self._packet.slow_tlb
            returned_now=bool(hint.valid and self.tlb_sources.live.get(hint.identity) is job)
            if job["returned_edge"] is not None or returned_now:item["source_tlb_full"]=True
        mmio=item["uncache_replay"] and s["subtype"]!="nc_load"
        if item["exceptions"] or mmio:
            item["cause_vector"]=0;return None
        reasons=[]
        if unc and(not item["uncache_replay"] or f["data"] or rar_denied or raw_denied or current_nuke or f["forward"]):reasons.append(0)
        if f["forward"]:reasons.append(1)
        if s["load"].execution.uop.store_set_hit and f["address"]:reasons.append(2)
        if item["extra"]==Cause.TLB_MISS or item.get("special"):reasons.append(3)
        if f["data"]:reasons.append(4)
        need=not item["full_forward"] and not unc and not item["uncache_replay"]
        if need and item["extra"] in(Cause.CACHE_REPLAY,Cause.CACHE_MISS,Cause.BANK_CONFLICT):reasons.append(int(item["extra"]))
        if rar_denied:reasons.append(9)
        if raw_denied:reasons.append(10)
        if current_nuke:reasons.append(11)
        item["cause_vector"]=sum(1<<n for n in set(reasons))
        return Cause(min(reasons)) if reasons else None

    def service(self,pool):
        if not pool.live or not(self.fair or self.source_rng.random()<.4):return None
        jobs=list(pool.live.values())
        return min(jobs,key=lambda j:j["job"])["identity"] if self.fair else self.source_rng.choice(jobs)["identity"]

    def plan(self,**options):
        packet,intent=super().plan(**options)
        loads=list(packet.loads)
        for lane,item in enumerate(intent["ldu_s3"]):
            if item is None or not loads[lane].execution.valid:continue
            head=item["s"]["head_s3"] if item["tail"] else None
            chosen=head if head is not None and head["cause_vector"] else item
            bits=chosen["cause_vector"]
            mshr_source=head if head is not None and head["cause_vector"]&(1<<6) else item
            q=loads[lane].execution
            loads[lane]=replace(loads[lane],execution=replace(q,
                need_replay=bool(bits or item["cause_vector"]),causes=bits&-bits,
                mshr=mshr_source["source_mshr"],handled=mshr_source["source_handled"],
                tlb_id=chosen["source_tlb_id"],tlb_full=chosen["source_tlb_full"]))
        execute=options.get("execute",True)
        cache_id=self.service(self.cache_sources) if execute else None
        tlb_id=self.service(self.tlb_sources) if execute else None
        refills=[Refill(),Refill()]
        if cache_id is not None:refills[self.edge%2]=Refill(True,cache_id)
        packet=replace(packet,loads=tuple(loads),refills=tuple(refills),slow_tlb=TlbHint(tlb_id is not None,tlb_id or 0))
        self._packet=packet
        intent["redirect_source"]=self.redirect_source if packet.redirect.valid else None
        self.source_check.declare_cycle(self.edge,packet,intent)
        return packet,intent

    async def step(self,**options):
        prior_jobs=len(self.jobs);prior_edge=self.edge
        await super().step(**options)
        p=self._packet
        # Each public return repays one already selected external source job.
        for refill in p.refills:
            if refill.valid:self.cache_sources.return_actual(refill.mshr,prior_edge)
        if p.slow_tlb.valid:self.tlb_sources.return_actual(p.slow_tlb.identity,prior_edge)
        for j in self.jobs[prior_jobs:]:
            j["sampled_error"],j["sampled_nderr"]=j["error"],j["nderr"]
            j["error"]=bool(j["error"] and not j["nderr"])
        # Actual S0 selects a TLB event before S1; not a DUT answer.
        for lane,item in enumerate(self.p0):
            if item is None or item["uncache_replay"]:continue
            s=item["s"];wanted=bool(s["extra"]==Cause.TLB_MISS and not s["tlb_intent_exercised"] and not item["tail"])
            source=self.tlb_sources.request(item["VA"]//4096,s["uid"],prior_edge,wanted=wanted)
            if source["miss"]:item["extra"]=Cause.TLB_MISS
            item["source_tlb_id"],item["source_tlb_full"]=source["identity"],source["full"]
            item["source_tlb_job"]=source["job"]
            if wanted:s["tlb_intent_exercised"]=True
            self.source_check.declare_external("tlb",lane,s["uid"],source,item["VA"]//4096)
        # Actual S1, including fullForward, can still leave an accepted Cache
        # miss. Higher-priority replay and cancellation do not erase the job.
        for lane,item in enumerate(self.p1):
            if item is None or p.translations[lane].kill or item["s"]["subtype"]!="cached" or item["uncache_replay"]:continue
            s=item["s"];want=item["sampled_extra"]
            source=self.cache_sources.request(item["PA"]//64,s["uid"],prior_edge,wanted=want==Cause.CACHE_MISS)
            if source["miss"]:
                item["extra"]=Cause.CACHE_REPLAY if source["full"] else Cause.CACHE_MISS
            elif want in(Cause.CACHE_REPLAY,Cause.BANK_CONFLICT):item["extra"]=want
            else:item["extra"]=None
            item["source_mshr"],item["source_handled"]=source["identity"],bool(source["miss"] and not source["full"])
            if want in(Cause.CACHE_REPLAY,Cause.CACHE_MISS,Cause.BANK_CONFLICT):s["cache_intent_exercised"]=True
            self.source_check.declare_external("cache",lane,s["uid"],source,item["PA"]//64,selected_extra=item["extra"])
        if not self.fair and options.get("forced") is None:self.random_steps+=1

    async def drain(self):
        await super().drain()
        for _ in range(256):
            if not(self.cache_sources.live or self.tlb_sources.live):break
            await self.step(admit=False)
        else:raise AssertionError("normal mixed external Cache/TLB obligations did not actually return")
        await super().drain()

    async def restore_cancelled_slots(self):
        await super().restore_cancelled_slots()
        # Legacy cleanup counted any structural release, including a new
        # faulting Load. Normal reuse needs a genuinely normally completed
        # new UID. Keep the original random/failure domain and extend only
        # the already separate post-random replacement phase.
        for kind,size,forced in(("load",120,"cached"),("store",64,"store")):
            victims=[s for s in self.history if s["kind"]==kind and s["aborted"] is not None]
            def missing():
                return [s for s in victims if not any(n["uid"]>s["uid"] and n["kind"]==kind and
                    n["position"]%size==s["position"]%size and n["complete"] and not n["fault"] for n in self.history)]
            for _ in range(3*size):
                if not missing():break
                await self.step(forced=forced)
                await self.drain()
            assert not missing(),("cancelled slots lack normally completed new UID",kind,[s["uid"] for s in missing()])
        self.counts["normal_same_slot_replacement_gate_completed"]+=1

    async def run(self,cycles=600):
        await super().run(cycles=cycles)
        assert not(self.cache_sources.live or self.tlb_sources.live)
        self.source_check.finish()

    def write_report(self,passed,error=None):
        states=[dict(uid=s["uid"],order=s["order"],kind=s["kind"],subtype=s["subtype"],position=s["position"],
                     structure_complete=s["complete"],local_abort=s["aborted"],fault=s["fault"],retired=s["retired"],rob_cancelled=s["rob_cancelled"]) for s in self.history]
        data=dict(nodeid=self.env.nodeid,seed=self.seed,passed=passed,error=error,random_steps_completed=self.random_steps,
                  original_types=self.KINDS,original_weights=self.WEIGHTS,counts=dict(self.counts),kinds=dict(self.kinds),causes=dict(self.causes),
                  public_UIDs=states,cache_sources=self.cache_sources.summary(),tlb_sources=self.tlb_sources.summary(),
                  source_job_edge_convention="accepted_edge and returned_edge both identify the actual zero-based program request, not its incremented post-step counter",
                  independent_source_checks=self.source_check.summary(),diagnostics="default compact summaries and one failure edge, no per-cycle JSON or waveforms",
                  limits="declared external producer profile and actual native LSQ effects only; no native upstream proof or whole-goal signoff")
        if not passed:
            data["failure_state"]=dict(edge=self.edge,pending=self.pending(),redirect_due=self.redirect_due,
                stages=[[None if x is None else {k:x[k] for k in("VA","PA","tail","cross","extra","exceptions","cause","source_mshr","source_tlb_id","cause_vector")} | dict(uid=x["s"]["uid"]) for x in stage]
                        for stage in(self.p0,self.p1,self.p2)],
                active=[{k:s.get(k) for k in("uid","order","position","phase","initial","extra","last_cause","mshr","tlb_id","grant","executed","sent","head_s3") if k!="head_s3"}
                        | dict(source=asdict(s["load"] if s["kind"]=="load" else s["owner"])) for s in self.active()],
                last_public_input=asdict(self._packet),last_public_before=self.env.pre_observed,last_public_after=self.env.observed)
        with Path(self.env.journal.name).with_name("normal-mixed-summary.json").open("x") as f:f.write(json.dumps(data,indent=2)+"\n")
