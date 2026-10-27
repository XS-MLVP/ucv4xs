"""Independent online public-history/source checks, bounded terminal summaries.

No controller answer helpers, LSQ reference model/private state, known-issues or
per-cycle file writes. External source stimuli are assumptions, not native LDU.
"""
from collections import Counter
from dataclasses import asdict


def rob(p):return (160*int(p.flag)+p.value)*2+int(not p.former)
def lq(p):return 120*int(p.flag)+p.value
def sq(p):return 128*int(p.first)+64*int(p.second)+p.value
def sqout(p,prefix="io_sqDeqPtr_"):return 128*p[prefix+"first_flag"]+64*p[prefix+"second_flag"]+p[prefix+"value"]


class PreciseCheck:
    def __init__(self,start_sq,start_lq,start_rob,uid_base=0):
        self.sh=self.st=start_sq;self.lh=self.lt=start_lq;self.anchor=start_rob
        self.sequence=uid_base;self.program=[];self.by_lq={};self.slots={};self.sta_pending=[]
        self.sources=[];self.counts=Counter();self.recovery=None;self.traps=[];self.cache_jobs={}
        self.first_tick=self.last_tick=None

    def background_prefetch(self,mshr):
        assert mshr not in self.cache_jobs
        self.cache_jobs[mshr]=dict(background=True)
        self.counts["declared_external_prefetch_jobs"]+=1

    @staticmethod
    def forward(post,lane,killed):
        prefix=f"io_forward_{lane}_s2Resp_"
        assert post[prefix+"valid"]==int(not killed)
        if not killed:
            assert not any(post[prefix+f"bits_forwardMask_{b}"] for b in range(16))
            assert not any(post[prefix+"bits_"+f] for f in("addrInvalid_valid","dataInvalid_valid","forwardInvalid","matchInvalid"))

    def order(self,p):
        code=rob(p);base=self.anchor//640*640+code
        result=min((base-640,base,base+640),key=lambda n:abs(n-self.anchor))
        assert abs(result-self.anchor)<320
        return result

    def declare(self,load,pattern,lane,tick,feedback,*,tail_pa=None):
        h,t=(asdict(x) for x in pattern)
        assert not h.get("tl_d_corrupt",False) and not t.get("tl_d_corrupt",False)
        va,pa=load.execution.vaddr,load.paddr;tv=va//16*16+16
        tp=tail_pa if tail_pa is not None else 0xB246000 if va%4096==4092 else pa//16*16+16
        assert va%16==12 and load.execution.uop.operation==6
        assert va%4096==pa%4096 and tv%4096==tp%4096
        if va//4096==tv//4096:
            assert h.get("tlb_page_fault",False)==t.get("tlb_page_fault",False)
            assert tp==pa//16*16+16
        self.sources.append(dict(load=load,head=h,tail=t,lane=lane,start=tick,feedback=feedback,
                                 tail_va=tv,tail_pa=tp))

    @staticmethod
    def segment(event):
        exc=(int(event["tag_error"])<<5)|(int(event.get("tlb_page_fault",False))<<13)
        assert not (event["mshr_nack"] and event["miss"])
        assert not exc or not(event["mshr_nack"] or event["miss"])
        return exc,None if exc else 5 if event["mshr_nack"] else 6 if event["miss"] else None

    def source_check(self,i,pre,post,tick):
        for s in self.sources:
            age=(tick-s["start"])//2
            if tick<s["start"] or age>4:continue
            lane=s["lane"];load=s["load"];u=load.execution.uop
            va,pa=load.execution.vaddr,load.paddr;tv,tp=s["tail_va"],s["tail_pa"]
            hx,hc=self.segment(s["head"]);tx,tc=self.segment(s["tail"])
            hr,tr=bool(hx or hc is not None),bool(tx or tc is not None)
            if age in(0,1):
                q=i.queries[lane]
                assert q.valid and q.vaddr==(va if age==0 else tv) and q.size==(3 if age==0 else 4) and q.sq==u.sq
            if age in(1,2):
                segment=s["head"] if age==1 else s["tail"]
                translation=i.translations[lane]
                killed=bool(segment.get("tlb_page_fault",False))
                assert translation.paddr==(pa if age==1 else tp) and translation.kill==killed
                self.forward(post,lane,killed)
            if age in(2,3):
                r,w=i.rar_queries[lane],i.raw_queries[lane]
                event=s["head"] if age==2 else s["tail"]
                assert r.valid and w.valid and r.rob==w.rob==u.rob and r.lq==u.lq and w.sq==u.sq
                assert r.paddr==w.paddr==(pa if age==2 else tp) and w.mask==(61440 if age==2 else 15)
                assert r.data_valid==w.data_valid==bool(not event["miss"]) and not r.nc
                assert pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"] and pre[f"io_ldu_rawNukeQuery_{lane}_req_ready"]
                assert not post[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"]
                self.counts["source_actual_query_pairs"]+=1
                if event["miss"]:
                    identity=3 if age==2 else 9
                    assert identity not in self.cache_jobs
                    self.cache_jobs[identity]=dict(background=False,ROB_absolute=self.order(u.rob),head=age==2)
                    self.counts["declared_original_Cache_jobs"]+=1
            if age in(3,4):
                one,two=(hr,False) if age==3 else (hr or tr,not hr and tr)
                for family in("rar","raw"):
                    assert getattr(i,family+"_revoke_last")==tuple(one if n==lane else False for n in range(3))
                    assert getattr(i,family+"_revoke_older")==tuple(two if n==lane else False for n in range(3))
                if age==3:assert not any(p.execution.valid for p in i.loads)
            if age!=4:continue
            p=i.loads[lane];q=p.execution;selected=hc if hc is not None else tc;exc=hx if hx else tx
            wb=bool(hx or hc is None and(tx or tc is None))
            assert q.valid and q.uop.rob==u.rob and q.uop.lq==u.lq and q.uop.sq==u.sq
            assert p.exceptions==q.uop.exceptions==exc and p.update_address==wb
            assert q.vaddr==va and p.paddr==pa and q.mask==61440 and q.aligned_type==4 and q.last_beat==bool(pa&64)
            assert p.fullva==(load.fullva if hx else tv)
            assert p.gpaddr==((0x201000000+pa) if hx else (0x211000000+tp)) and not p.hyper and not p.nonleaf
            assert q.need_replay==(selected is not None) and q.causes==(0 if selected is None else 1<<selected)
            assert q.unaligned_head==(hc is not None) and q.replay_feedback==s["feedback"]
            assert q.mshr==(3 if hc==6 else 9) and q.handled==(s["head"]["miss"] if hc==6 else s["tail"]["miss"])
            assert q.tlb_id==(2 if hc is not None else 13) and q.tlb_full==(hc is None) and q.special_eligible==(selected in(3,5,6))
            self.counts["source_S4_joins"]+=1
            self.counts["head_fault_beats_other_tail_fault"]+=bool(hx and tx and hx!=tx)
            self.counts["fault_WB_despite_tail_replay"]+=bool(hx and tc is not None)
            self.counts["tail_fault_without_WB_waits_for_head_retry"]+=bool(hc is not None and tx and not wb)

    def observe(self,i,pre,post,tick):
        if self.first_tick is None:self.first_tick=tick
        else:assert self.last_tick+2==tick,"unobserved cycle inside program request window"
        self.last_tick=tick
        self.counts["cycles"]+=1
        self.source_check(i,pre,post,tick)
        for refill in i.refills:
            if not refill.valid:continue
            assert refill.mshr in self.cache_jobs,"refill must repay a declared source job exactly once"
            job=self.cache_jobs.pop(refill.mshr)
            self.counts["actual_background_Cache_refills" if job["background"] else "actual_original_Cache_refills"]+=1
            if refill.mshr==9 and 3 in self.cache_jobs:
                assert not any(post[f"io_replay_{b}_valid"] for b in range(3)),"tail/unrelated refill must not wake original head miss"
                self.counts["wrong_tail_refill_did_not_wake_head"]+=1
        head=self.order(i.pending);self.anchor=max(self.anchor,head)
        assert sqout(pre)==self.sh%256
        for old in self.program:
            if old["order"]>=head or old.get("trapped") or old["cancelled"]:continue
            assert not old.get("fault_wb")
            assert old.get("wb") if old["kind"]=="load" else old.get("s2") and "data" in old
        for d in i.dispatch:
            if not d.valid:continue
            assert self.recovery is None and not i.redirect.valid and not pre["io_toLsqEnqCtrl_lqRecoverStall"] and not pre["io_toLsqEnqCtrl_sqRecoverStall"]
            assert d.flows==1 and d.need_alloc in(1,2)
            order=self.order(d.rob);self.anchor=max(self.anchor,order)
            self.sequence+=1
            s=dict(uid=self.sequence,order=order,kind="load" if d.need_alloc==1 else "store",released=False,cancelled=False,trapped=False,
                   fault_wb=False,wb=False,pending_replay=False,grant=None)
            self.program.append(s)
            if s["kind"]=="load":
                assert lq(d.load_start)==self.lt%240
                s.update(pos=self.lt,sq=self.st);self.by_lq[self.lt%240]=s;self.lt+=1
            else:
                s["pos"]=self.st;self.st+=1
                assert sq(d.store_end)==self.st%256
        for s,lane in self.sta_pending:
            a=i.attributes[lane]
            assert a.last and a.memory and not(a.exception or a.nc or a.mmio)
            s["s2"]=tick
        self.sta_pending=[]
        for lane,a in enumerate(i.addresses):
            if not a.valid:continue
            s=next(s for s in self.program if s["kind"]=="store" and s["pos"]%64==a.slot and not s["released"])
            assert self.order(a.rob)==s["order"] and not(a.tlb_miss or a.cross_word) and a.last and a.size==3
            assert "address" not in s and a.vaddr%4096==a.paddr%4096
            s["address"]=a;self.sta_pending.append((s,lane))
        for data in i.data:
            if not data.valid:continue
            s=next(s for s in self.program if s["kind"]=="store" and s["pos"]%256==sq(data.sq) and not s["released"])
            assert "data" not in s;s["data"]=data.data
        for packet in i.loads:
            q=packet.execution
            if not q.valid:continue
            s=self.by_lq[lq(q.uop.lq)]
            assert s["order"]==self.order(q.uop.rob) and not(s["cancelled"] or s["released"]) and sq(q.uop.sq)==s["sq"]%256
            if q.replay_feedback:
                assert s["grant"]==q.slot and self.slots[q.slot] is s
                del self.slots[q.slot];s["grant"]=None;self.counts["actual_original_slot_feedbacks"]+=1
            s["pending_replay"]=q.need_replay;s["packet"]=packet
            if packet.update_address:
                if packet.exceptions:s["fault_wb"]=True;self.counts["fault_WB_attempts"]+=1
                else:s["wb"]=True
            if not q.need_replay and packet.update_address:s["finish_ready"]=tick
        for bank in range(3):
            p=f"io_replay_{bank}_"
            if not(pre[p+"valid"] and i.replay_ready[bank]):continue
            s=self.by_lq[120*pre[p+"bits_uop_lqIdx_flag"]+pre[p+"bits_uop_lqIdx_value"]]
            assert s["pending_replay"] and not s["cancelled"] and s["grant"] is None
            packet=s["packet"];q=packet.execution
            code=(160*pre[p+"bits_uop_robIdx_flag"]+pre[p+"bits_uop_robIdx_value"])*2+int(not pre[p+"bits_uop_robIdx_isFormer"])
            assert code==s["order"]%640 and pre[p+"bits_vaddr"]==pre[p+"bits_fullva"]==q.vaddr
            assert pre[p+"bits_mask"]==q.mask and pre[p+"bits_uop_fuOpType"]==6
            assert all(pre[p+f"bits_uop_exceptionVec_{b}"]==0 for b in(23,19,15,7,6))
            if q.handled:assert pre[p+"bits_mshrId"]==q.mshr
            slot=pre[p+"bits_replayQueueIdx"];assert slot%3==bank and slot not in self.slots
            self.slots[slot]=s;s["grant"]=slot;self.counts["actual_replay_grants"]+=1
        if i.redirect.valid:
            cut=self.order(i.redirect.rob)
            assert i.redirect.flush_self and cut==head and self.recovery is None
            fault=next(s for s in self.program if s["kind"]=="load" and s["order"]==cut)
            assert fault["fault_wb"] and not fault["trapped"]
            assert all(s.get("wb") if s["kind"]=="load" else s.get("s2") and "data" in s for s in self.program if s["order"]<cut)
            victims=[s for s in self.program if s["order"]>=cut and not s["released"] and not s["cancelled"]]
            assert victims and all(s["kind"]=="load" for s in victims)
            fault["trapped"]=True
            for s in victims:
                s["cancelled"]=True
                self.counts["pending_Replay_owners_cancelled"]+=s["pending_replay"]
                if s["grant"] is not None:self.slots.pop(s["grant"])
            self.recovery=dict(lq=self.lt-len(victims),sq=self.st,LQ=False,SQ=False)
            self.traps.append(dict(ROB_absolute=cut,tick=tick,fault_UID=fault["uid"],fault_LQ_released_before_trap=fault["released"],
                                   cancelled_UIDs=[s["uid"] for s in victims],older_Store_still_unconsumed=not any("consumed" in s for s in self.program if s["kind"]=="store")))
            self.counts["precise_ROB_head_traps"]+=1
        for lane in range(2):
            p=f"io_sbuffer_req_{lane}_"
            if not(pre[p+"valid"] and i.sbuffer_ready[lane]):continue
            s=next(s for s in self.program if s["kind"]=="store" and not s["released"] and "consumed" not in s)
            a=s["address"];assert s.get("s2") and s["order"]<=head and "data" in s
            mask=255<<(a.vaddr%16);value=s["data"]<<(8*(a.vaddr%16));bits=((1<<64)-1)<<(8*(a.vaddr%16))
            assert pre[p+"bits_vaddr"]==a.vaddr//16*16 and pre[p+"bits_addr"]==a.paddr//16*16
            assert pre[p+"bits_mask"]==mask and not ((pre[p+"bits_data"]^value)&bits) and not pre[p+"bits_wline"]
            s["consumed"]=tick;self.counts["actual_original_Sbuffer_fires"]+=1
        delta=(sqout(post)-self.sh)%256
        assert delta in(0,1)
        if delta:
            s=next(s for s in self.program if s["kind"]=="store" and s["pos"]==self.sh)
            assert s["consumed"]+2==tick;s["released"]=True;self.sh+=1;self.counts["actual_original_SQ_releases"]+=1
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            count=post["io_toLsqEnqCtrl_lqDeq_bits"]
            live=[s for s in self.program if s["kind"]=="load" and not(s["released"] or s["cancelled"])]
            assert 0<count<=len(live)
            for s in live[:count]:
                assert s.get("finish_ready",tick)>=0 and s["finish_ready"]<tick
                s["released"]=True;self.lh+=1;self.counts["actual_LQ_structure_releases"]+=1
        if self.recovery is not None:
            r=self.recovery
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                assert 120*post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]==r["lq"]%240
                self.lt=r["lq"];r["LQ"]=True
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                assert sqout(post,"io_toLsqEnqCtrl_sqRedirectPtr_bits_")==r["sq"]%256;r["SQ"]=True
            if r["LQ"] and r["SQ"] and not(post["io_toLsqEnqCtrl_lqRecoverStall"] or post["io_toLsqEnqCtrl_sqRecoverStall"]):
                self.recovery=None;self.counts["both_actual_recoveries_settled"]+=1

    def finish(self):
        assert self.recovery is None and not self.slots and not self.sta_pending and not self.cache_jobs
        reuse=[]
        for s in self.program:
            assert s["released"] or s["cancelled"]
            assert not s["fault_wb"] or s["trapped"]
            if s["cancelled"]:
                found=[n for n in self.program if n["uid"]>s["uid"] and n["kind"]==s["kind"] and n["pos"]%120==s["pos"]%120 and n["released"] and not n["fault_wb"]]
                assert found
                reuse.append(dict(cancelled_UID=s["uid"],new_completed_UID=found[0]["uid"],physical_LQ_slot=s["pos"]%120))
        normal=sum(s["released"] and not s["fault_wb"] for s in self.program)
        fault=sum(s["trapped"] for s in self.program);cancel=sum(s["cancelled"] and not s["trapped"] for s in self.program)
        assert len(self.program)==normal+fault+cancel
        assert self.counts["cycles"]==(self.last_tick-self.first_tick)//2+1
        return dict(counts=dict(self.counts),allocated_UIDs=len(self.program),normal_completed_UIDs=normal,fault_WB_and_head_trap_UIDs=fault,
                    pure_cancelled_UIDs=cancel,structurally_cancelled_UIDs=len(reuse),same_slot_completion_witnesses=reuse,traps=self.traps,
                    request_window=dict(first_tick=self.first_tick,last_tick=self.last_tick,all_requests_plus2=True),
                    queue_tails=dict(SQ=self.st,LQ=self.lt),
                    UID_terminal_states=[dict(uid=s["uid"],ROB_absolute=s["order"],kind=s["kind"],queue_absolute_position=s["pos"],physical_slot=s["pos"]%(64 if s["kind"]=="store" else 120),
                                              structure_released=s["released"],structure_cancelled=s["cancelled"],fault_WB=s["fault_wb"],head_trapped=s["trapped"]) for s in self.program],
                    declared_cache_jobs_remaining=len(self.cache_jobs),
                    scope="Independent online public input/output/source projection and UID checks; compact terminal witnesses, not persisted per-cycle replay or native upstream LDU/TLB/DCache/ROB proof.")
