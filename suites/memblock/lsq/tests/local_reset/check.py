"""Independent online public-UID/effect checks, not controller/model state."""
from collections import Counter


def rob(p):return (int(p.flag)*160+p.value)*2+int(not p.former)
def lq(p):return int(p.flag)*120+p.value


class LocalResetCheck:
    def __init__(self):
        self.loads=[];self.active={};self.jobs=[];self.events=[];self.counts=Counter()
        self.generation=0;self.in_reset=False;self.tail=0;self.bypass_pending=[]
        self.first_tick=self.last_tick=None
        self.history=[]

    def event(self,kind,tick,**fields):
        assert len(self.events)<512
        self.events.append(dict(event=kind,tick=tick,**fields))

    def observe(self,i,pre,post,tick):
        if self.first_tick is None:self.first_tick=tick
        else:assert self.last_tick+2==tick
        self.last_tick=tick;self.counts["checked_program_requests"]+=1
        if i.reset:
            assert not(any(d.valid for d in i.dispatch) or i.bus.ack or i.bus.response)
            if not self.in_reset:
                victims=[s for s in self.loads if s["terminal"] is None]
                assert victims and all(a["sid"] is not None for a in self.jobs if not a["returned"])
                for s in victims:s["terminal"]="local-reset-aborted"
                self.event("local_reset_external_jobs_retained",tick,UIDs=[s["uid"] for s in victims],external_live_jobs=[a["job"] for a in self.jobs if not a["returned"]])
                self.active={};self.tail=0;self.generation+=1;self.bypass_pending=[]
                self.history=[]
                self.counts["local_reset_events"]+=1
            self.in_reset=True;self.counts["local_reset_edges"]+=1
            return
        self.in_reset=False
        for d in i.dispatch:
            if not d.valid:continue
            assert d.need_alloc==1 and d.flows==1 and lq(d.load_start)==self.tail
            s=dict(uid=len(self.loads)+1,generation=self.generation,LQ=self.tail,ROB=rob(d.rob),terminal=None,
                   packet=None,job=None,slot=None,feedback=None,bypass=None)
            self.loads.append(s);self.active[self.tail]=s;self.tail+=1
            self.event("dispatch",tick,uid=s["uid"],LQ=s["LQ"],generation=s["generation"])
        for lane,packet in enumerate(i.loads):
            q=packet.execution
            if not q.valid:continue
            s=self.active[lq(q.uop.lq)]
            assert s["terminal"] is None and s["ROB"]==rob(q.uop.rob)
            assert q.uop.operation==6 and q.nc and not packet.mmio and packet.memory_backed and not packet.hyper and not packet.nonleaf
            assert q.aligned_type==3 and q.last_beat==bool(packet.paddr&64) and not packet.exceptions and not q.uop.exceptions
            assert len(self.history)>=3
            s0,s1,s2=self.history[-3:]
            assert s0.queries[lane].valid and s0.queries[lane].vaddr==q.vaddr and s0.queries[lane].sq==q.uop.sq and s0.queries[lane].size==3
            assert s1.translations[lane].paddr==packet.paddr and not s1.translations[lane].kill
            r,w=s2.rar_queries[lane],s2.raw_queries[lane]
            assert r.valid and w.valid and r.rob==w.rob==q.uop.rob and r.lq==q.uop.lq and w.sq==q.uop.sq
            assert r.paddr==w.paddr==packet.paddr and w.mask==255
            assert r.nc==r.data_valid==w.data_valid==q.replay_feedback
            assert i.rar_revoke_last==i.raw_revoke_last==tuple(not q.replay_feedback if n==lane else False for n in range(3))
            self.counts["actual_source_pipeline_S3s"]+=1
            if q.replay_feedback:
                assert not q.need_replay and q.causes==0 and packet.update_address
                assert s["slot"]==q.slot and s["bypass"] is not None and tick==s["bypass"]+6
                assert s["job"]["returned"] and s["terminal"] is None
                s["feedback"]=tick;self.counts["original_slot_S3_feedbacks"]+=1
            else:
                assert s["packet"] is None and q.need_replay and q.causes==1 and not packet.update_address
            s["packet"]=packet
        if pre["io_uncache_req_valid"] and i.bus.ready:
            code=(160*pre["io_uncache_req_bits_robIdx_flag"]+pre["io_uncache_req_bits_robIdx_value"])*2+int(not pre["io_uncache_req_bits_robIdx_isFormer"])
            s=next(s for s in self.loads if s["terminal"] is None and s["ROB"]==code)
            p=s["packet"];assert p is not None and s["job"] is None
            assert pre["io_uncache_req_bits_cmd"]==0 and pre["io_uncache_req_bits_nc"] and pre["io_uncache_req_bits_memBackTypeMM"]
            assert pre["io_uncache_req_bits_addr"]==p.paddr and pre["io_uncache_req_bits_vaddr"]==p.execution.vaddr and pre["io_uncache_req_bits_mask"]==255
            a=dict(job=len(self.jobs)+1,owner_UID=s["uid"],mid=pre["io_uncache_req_bits_id"],sid=None,accepted=tick,returned=None,consumed=False,discarded=False)
            self.jobs.append(a);s["job"]=a;self.counts["actual_external_requests"]+=1
            self.event("external_request",tick,job=a["job"],uid=s["uid"],mid=a["mid"])
        if i.bus.ack:
            assert i.bus.ack_to_load
            matches=[a for a in self.jobs if a["mid"]==i.bus.mid and a["sid"] is None]
            assert len(matches)==1 and not any(a["sid"]==i.bus.sid and not a["returned"] for a in self.jobs)
            matches[0]["sid"]=i.bus.sid;self.counts["actual_external_acks"]+=1
            self.event("external_ack",tick,job=matches[0]["job"],sid=i.bus.sid)
        if i.bus.response:
            assert i.bus.response_to_load and not(i.bus.error and i.bus.nderr)
            matches=[a for a in self.jobs if a["sid"]==i.bus.response_id and not a["returned"]]
            assert len(matches)==1
            a=matches[0];a["returned"]=tick;a.update(data=i.bus.data,error=i.bus.error,nderr=i.bus.nderr)
            owner=self.loads[a["owner_UID"]-1]
            a["discarded"]=owner["terminal"]=="local-reset-aborted"
            self.counts["actual_old_discarded_responses" if a["discarded"] else "actual_new_responses"]+=1
            self.event("actual_response",tick,job=a["job"],uid=a["owner_UID"],discarded=a["discarded"],sid=a["sid"],data=a["data"],error=a["error"],nderr=a["nderr"])
        for bank in range(3):
            p=f"io_replay_{bank}_"
            if not(pre[p+"valid"] and i.replay_ready[bank]):continue
            key=120*pre[p+"bits_uop_lqIdx_flag"]+pre[p+"bits_uop_lqIdx_value"]
            s=self.active[key];a=s["job"]
            assert s["terminal"] is None and a["returned"] and not a["discarded"] and s["slot"] is None
            assert pre[p+"bits_ncReplay"] and pre[p+"bits_uncacheReplay"]
            slot=pre[p+"bits_replayQueueIdx"];assert slot%3==bank
            s["slot"]=slot;self.counts["actual_original_grants"]+=1
            self.event("grant",tick,uid=s["uid"],slot=slot)
        pending=[]
        for due,lane,s in self.bypass_pending:
            if due!=tick:pending.append((due,lane,s));continue
            a=s["job"];p=f"io_bypass_{lane}_s2Resp_"
            assert post[p+"valid"] and post[p+"bits_data"]==a["data"]*((1<<64)+1)
            assert post[p+"bits_derr"]==a["error"] and post[p+"bits_nderr"]==a["nderr"]
            a["consumed"]=True;self.counts["actual_original_bypass_data"]+=1
            self.event("bypass_data",tick,uid=s["uid"],data=post[p+"bits_data"],error=post[p+"bits_derr"],nderr=post[p+"bits_nderr"])
        self.bypass_pending=pending
        for lane,b in enumerate(i.bypass):
            if not b.valid:continue
            s=self.active[lq(b.lq)];a=s["job"];packet=s["packet"]
            assert b.nc and not b.mmio and s["slot"] is not None and a["returned"] and not a["consumed"] and not a["discarded"]
            p=f"io_bypass_{lane}_s1Resp_"
            assert post[p+"valid"] and post[p+"bits_paddr"]==packet.paddr
            assert post["io_ldExceptionInfo_valid"] and post["io_ldExceptionInfo_bits_vaddr"]==packet.fullva
            assert post["io_ldExceptionInfo_bits_exceptionVec_19"]==a["error"] and post["io_ldExceptionInfo_bits_exceptionVec_5"]==a["nderr"]
            s["bypass"]=tick;self.bypass_pending.append((tick+2,lane,s))
            self.event("bypass_metadata",tick,uid=s["uid"],lane=lane,paddr=packet.paddr)
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            live=[s for s in self.loads if s["terminal"] is None]
            n=post["io_toLsqEnqCtrl_lqDeq_bits"];assert 0<n<=len(live)
            for s in live[:n]:
                assert s["feedback"] and s["feedback"]<tick and s["job"]["consumed"]
                s["terminal"]="normal-completed";self.counts["actual_new_LQ_dequeues"]+=1
                self.event("normal_completed",tick,uid=s["uid"],LQ=s["LQ"])
        # A retained old response never constitutes a current owner's wakeup.
        for bank in range(3):
            p=f"io_replay_{bank}_"
            if not post[p+"valid"]:continue
            key=120*post[p+"bits_uop_lqIdx_flag"]+post[p+"bits_uop_lqIdx_value"]
            s=self.active[key]
            assert s["job"] and s["job"]["returned"] and not s["job"]["discarded"] and s["terminal"] is None
        self.history=(self.history+[i])[-3:]

    def finish(self):
        assert not self.bypass_pending and all(s["terminal"] for s in self.loads)
        assert all(a["returned"] and a["consumed"]!=a["discarded"] for a in self.jobs)
        reuse=[]
        for s in self.loads:
            if s["terminal"]!="local-reset-aborted":continue
            new=next(n for n in self.loads if n["uid"]>s["uid"] and n["LQ"]%120==s["LQ"]%120 and n["terminal"]=="normal-completed")
            reuse.append(dict(old_UID=s["uid"],new_completed_UID=new["uid"],physical_LQ_slot=s["LQ"]%120))
        return dict(counts=dict(self.counts),UIDs=[{k:s[k] for k in("uid","generation","LQ","ROB","terminal")} for s in self.loads],
                    external_jobs=self.jobs,events=self.events,same_slot_completion_witnesses=reuse,
                    request_window=dict(first_tick=self.first_tick,last_tick=self.last_tick,continuous=True),
                    limits="online actual public effects; external retained Uncache/reset profile assumption, not native SoC reset or offline per-cycle replay")
