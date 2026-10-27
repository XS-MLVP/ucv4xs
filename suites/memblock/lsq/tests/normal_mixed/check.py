"""Independent source projection and public-UID/effect history.

No controller cause/writeback helpers, reference-model state, private DUT
registers or per-cycle file writes. External events are explicit assumptions.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import traceback


def rob(p):return (160*int(p.flag)+p.value)*2+int(not p.former)
def lq(p):return 120*int(p.flag)+p.value
def sq(p):return 128*int(p.first)+64*int(p.second)+p.value
def code(p):return (160*int(p["flag"])+p["value"])*2+int(not p["former"])


class CheckedEnv:
    """Retain the original full-output fixture, including original exceptions."""
    def __init__(self,env,checker):self.inner,self.checker=env,checker
    def __getattr__(self,name):return getattr(self.inner,name)
    async def cycle(self,packet):
        previous=self.inner.last_tick
        try:result=await self.inner.cycle(packet)
        except BaseException as exc:
            self.checker.core_error=repr(exc)
            if self.inner.last_tick>previous:
                try:self.checker.observe(packet,self.inner.pre_observed,self.inner.observed,self.inner.last_tick)
                except BaseException:pass  # Recorded separately; preserve the original full-output FAIL.
            raise
        if self.inner.last_tick>previous:self.checker.observe(packet,self.inner.pre_observed,self.inner.observed,self.inner.last_tick)
        return result


class NormalMixedCheck:
    def __init__(self,seed):
        self.seed=seed;self.instructions={};self.program=[];self.lq_owners={};self.sq_owners={}
        self.lt=self.lh=self.st=self.sh=0;self.anchor=0;self.counts=Counter();self.recovery=None
        self.source0=[None]*3;self.p0=[None]*3;self.p1=[None]*3;self.p2=[None]*3;self.heads={}
        self.external={"cache":{},"tlb":{}};self.external_returned={"cache":set(),"tlb":set()}
        self.jobs=[];self.bypass=[None]*3;self.sta=[None]*2;self.first_tick=self.last_tick=None
        self.last_source_error=None;self.core_error=None;self.traps=[];self.elastic=None;self.redirect_source=None
        self.cmo_jobs=[];self.cmo_job=None

    def order(self,p):
        value=rob(p);base=self.anchor//640*640+value
        result=min((base-640,base,base+640),key=lambda n:abs(n-self.anchor))
        assert abs(result-self.anchor)<320
        return result

    def declare_instruction(self,uid,order,kind,position,payload):
        assert uid not in self.instructions
        self.instructions[uid]=dict(uid=uid,order=order,kind=kind,pos=position,source=deepcopy(payload),dispatched=False,
                                    cancelled=False,released=False,retired=False,wb=None,fault_WB=False,sta=False,std=False,
                                    s2=False,consumed=0,grant=None,bus=None,cache_response=None)

    def declare_cycle(self,edge,packet,intent):
        self.redirect_source=intent.get("redirect_source")
        self.source0=[]
        for item in intent["ldu_s0"]:
            if item is None:self.source0.append(None);continue
            # Only declared source facts, NOT cause/flags/WB/full_forward.
            self.source0.append(dict(uid=item["s"]["uid"],VA=item["VA"],PA=item["PA"],mask=item["mask"],size=item["size"],
                                     cross=item["cross"],tail=item["tail"],uncache=item["uncache_replay"],
                                     fullva=item["source_fullva"],gpaddr=item["source_gpaddr"],
                                      extra=item["sampled_extra"],tlb_id=0,tlb_full=False,tlb_job=None,mshr=0,handled=False))

    def declare_external(self,kind,lane,uid,event,key,selected_extra=None):
        item=(self.p0 if kind=="tlb" else self.p1)[lane]
        assert item is not None and item["uid"]==uid
        active=self.external[kind];identity=event["identity"]
        if event["miss"] and not event["full"]:
            if identity in active:assert active[identity]["key"]==key and active[identity]["job"]==event["job"]
            else:
                assert len(active)<16 and not any(j["key"]==key for j in active.values())
                assert event["job"] not in self.external_returned[kind]
                active[identity]=dict(key=key,job=event["job"]);self.counts[kind+"_declared_jobs"]+=1
        elif event["full"]:assert len(active)==16
        else:assert not any(j["key"]==key for j in active.values()),"unreturned same-key job cannot become an unexplained hit"
        if kind=="tlb":
            if event["miss"]:item["extra"]=3
            item["tlb_id"],item["tlb_full"]=identity,event["full"]
            item["tlb_job"]=event["job"]
        else:
            item["extra"]=selected_extra;item["mshr"]=identity;item["handled"]=event["miss"] and not event["full"]

    @staticmethod
    def sta_nuke(item,addresses,owner):
        for a in addresses:
            if not a.valid or a.tlb_miss:continue
            if not 0<(owner["order"]-rob(a.rob))%640<320:continue
            if item["PA"]>>(6 if a.fu_op&1 else 4)==a.paddr>>(6 if a.fu_op&1 else 4) and item["mask"]&a.mask:return True
        return False

    @staticmethod
    def project(item,s,rar_denied,raw_denied,nuke):
        if item["exception"] or item["uncache"] and s["kind"]!="nc_load":return 0
        f=item["flags"];u=s["source"]["execution"]["uop"]
        conditions={0:s["kind"]!="cached" and(not item["uncache"] or f["data"] or rar_denied or raw_denied or nuke or f["forward"]),
                    1:f["forward"],2:u["store_set_hit"] and f["addr"],3:item["extra"]==3 or item["special"],4:f["data"],
                    9:rar_denied,10:raw_denied,11:nuke}
        if not item["full_forward"] and s["kind"]=="cached" and not item["uncache"] and item["extra"] in(5,6,8):conditions[int(item["extra"])]=True
        return sum(1<<n for n,value in conditions.items() if value)

    def observe(self,i,pre,post,tick):
        try:self._observe(i,pre,post,tick)
        except BaseException as exc:
            self.last_source_error=dict(tick=tick,error=repr(exc),location=traceback.extract_tb(exc.__traceback__)[-1].lineno,
                                        input=asdict(i),before=pre,after=post,
                                        stages=dict(S1=self.p0,S2=self.p1,S3=self.p2),redirect_source=self.redirect_source,
                                        active_ROB=[{k:s[k] for k in("uid","order","kind","pos","wb","fault_WB","sta","std","s2","released")}
                                                    for s in self.program if self.in_rob(s)])
            raise

    @staticmethod
    def in_rob(s):return not(s["cancelled"] or s["retired"] or s.get("rob_cancelled_after_release"))

    def _observe(self,i,pre,post,tick):
        if self.first_tick is None:self.first_tick=tick
        else:assert self.last_tick+2==tick,"gap in source-checked program requests"
        self.last_tick=tick;self.counts["program_requests"]+=1
        head=self.order(i.pending);self.anchor=max(self.anchor,head)
        for s in self.program:
            if s["cancelled"] or s.get("rob_cancelled_after_release") or s["retired"] or s["order"]>=head:continue
            assert not s["fault_WB"],"fault cannot retire as normal prefix"
            assert s["wb"] is not None if "load" in s["kind"] or s["kind"]=="cached" else s["sta"] and s["std"] and s["s2"]
            if s["kind"] in("cbo","io_store"):assert s["wb"] is not None
            if s["kind"]=="nc_store":assert s["bus"] and s["bus"]["sid"] is not None
            s["retired"]=True;self.counts["actual_executed_ROB_prefix_advance"]+=1
        for d in i.dispatch:
            if not d.valid:continue
            assert not i.redirect.valid and self.recovery is None
            order=self.order(d.rob);self.anchor=max(self.anchor,order)
            matches=[s for s in self.instructions.values() if s["order"]==order and not s["dispatched"]]
            assert len(matches)==1;s=matches[0]
            barrier=[o for o in self.program if o["kind"]=="cbo" and not(o["retired"] or o["cancelled"] or o.get("rob_cancelled_after_release"))]
            assert not barrier,"CBO BlockBack must cover younger admission"
            if s["kind"]=="cbo":assert not any(not(o["retired"] or o["cancelled"] or o.get("rob_cancelled_after_release")) for o in self.program),"CBO NoSpec requires empty ROB"
            s["dispatched"]=True;self.program.append(s)
            if d.need_alloc==1:
                assert lq(d.load_start)==self.lt%240 and s["pos"]==self.lt
                assert s["source"]["execution"]["uop"]["sq"]==dict(first=bool(self.st//128%2),second=bool(self.st//64%2),value=self.st%64)
                self.lq_owners[self.lt]=s;self.lt+=1
            else:
                assert d.need_alloc==2 and sq(d.store_end)==(self.st+1)%256 and s["pos"]==self.st
                self.sq_owners[self.st]=s;self.st+=1
        for lane,previous in enumerate(self.sta):
            if previous is None:continue
            s,last=previous;attr=i.attributes[lane];memory=s["source"]["memory"]
            assert (attr.nc,attr.mmio,attr.memory,attr.last)==(memory==1,memory in(2,7),memory<4,last)
            if last:s["s2"]=True
        self.sta=[None]*2
        for lane,a in enumerate(i.addresses):
            if not a.valid:continue
            s=next(s for p,s in self.sq_owners.items() if self.sh<=p<self.sh+64 and p%64==a.slot and not(s["cancelled"] or s["released"]))
            assert self.order(a.rob)==s["order"] and not a.hyper
            if not a.tlb_miss:s["sta"]=True;self.sta[lane]=(s,a.last)
            if s["kind"]=="cbo":assert a.size==4 and a.mask==65535 and a.wline and a.paddr%16==a.vaddr%16==0
        for d in i.data:
            if not d.valid:continue
            s=next(s for p,s in self.sq_owners.items() if self.sh<=p<self.sh+64 and p%256==sq(d.sq) and not s["cancelled"])
            assert not s["std"] and d.data==s["source"]["value"];s["std"]=True
        for r in i.refills:
            if r.valid:
                job=self.external["cache"].pop(r.mshr);self.external_returned["cache"].add(job["job"]);self.counts["cache_actual_returns"]+=1
        if i.slow_tlb.valid:
            assert not i.slow_tlb.replay_all
            job=self.external["tlb"].pop(i.slow_tlb.identity);self.external_returned["tlb"].add(job["job"]);self.counts["tlb_actual_returns"]+=1
        # S3/S4 source projection is reconstructed from prior actual S0/S1/S2.
        for lane,item in enumerate(self.p2):
            if item is None:assert not i.loads[lane].execution.valid;continue
            s=self.instructions[item["uid"]];bits=item["bits"]
            if item["cross"] and not item["tail"]:
                assert not i.loads[lane].execution.valid
                self.heads[s["uid"]]=item;expected_one=bool(bits or item["exception"]);expected_two=False
            else:
                head_item=self.heads.pop(s["uid"],None) if item["tail"] else None
                assert not item["tail"] or head_item is not None
                selected=head_item if head_item is not None and head_item["bits"] else item
                mb=head_item if head_item is not None and head_item["bits"]&(1<<6) else item
                exception_item=head_item if head_item is not None and head_item["exception"] else item
                packet=i.loads[lane];q=packet.execution
                assert q.valid and rob(q.uop.rob)==s["order"]%640 and lq(q.uop.lq)==s["pos"]%240
                assert not packet.hyper and not packet.nonleaf and packet.exceptions==q.uop.exceptions==exception_item["exception"]
                assert q.causes==selected["bits"]&-selected["bits"] and q.need_replay==bool(selected["bits"] or bits)
                assert q.mshr==mb["mshr"] and q.handled==mb["handled"] and q.tlb_id==selected["tlb_id"] and q.tlb_full==selected["tlb_full"]
                assert q.aligned_type==item["size"] and q.last_beat==bool(packet.paddr&64)
                assert packet.fullva==exception_item["fullva"] and packet.gpaddr==exception_item["gpaddr"]
                scalar_wb=bool(item["exception"] or item["match"] or not bits and not(s["kind"]!="cached" and not item["uncache"]))
                if head_item is not None:
                    hwb=bool(head_item["exception"] or head_item["match"] or not head_item["bits"])
                    scalar_wb=bool(head_item["exception"] or head_item["match"] or hwb and scalar_wb)
                assert packet.update_address==scalar_wb
                hrev=bool(head_item is not None and(head_item["bits"] or head_item["exception"]))
                trev=bool(bits or item["exception"])
                expected_one,expected_two=trev or hrev,head_item is not None and not hrev and trev
                if not s["cancelled"]:
                    if q.replay_feedback:
                        assert s["grant"]==q.slot;s["grant"]=None;self.counts["actual_original_slot_feedback"]+=1
                    if scalar_wb:s["wb"]=tick;s["fault_WB"]=bool(packet.exceptions)
                    if not q.need_replay and scalar_wb:s["finish_ready"]=tick
                self.counts["source_S4_joins" if head_item is not None else "source_S3_packets"]+=1
                if s["source"]["execution"]["vector"] and not q.replay_feedback:
                    self.counts["initial_vector_QB_current_upstream_route_UNPROVEN"]+=1
            assert i.rar_revoke_last[lane]==i.raw_revoke_last[lane]==expected_one
            assert i.rar_revoke_older[lane]==i.raw_revoke_older[lane]==expected_two
        next2=[None]*3
        for lane,item in enumerate(self.p1):
            if item is None:continue
            s=self.instructions[item["uid"]];r,w=i.rar_queries[lane],i.raw_queries[lane]
            query=not(item["uncache"] and s["kind"]!="nc_load") and not item["nuke1"]
            assert r.valid==w.valid==query
            if query:
                data=item["full_forward"] or item["uncache"] and s["kind"]=="nc_load" or s["kind"]=="cached" and not item["full_forward"] and item["extra"] not in(6,8)
                assert r.paddr==w.paddr==item["PA"] and w.mask==item["mask"]
                assert rob(r.rob)==rob(w.rob)==s["order"]%640 and lq(r.lq)==s["pos"]%240
                assert r.data_valid==w.data_valid==bool(data) and r.nc==(item["uncache"] and s["kind"]=="nc_load")
            copied=deepcopy(item)
            if item["extra"]==3 and item["tlb_job"] in self.external_returned["tlb"]:
                copied["tlb_full"]=True;self.counts["actual_S2_TLB_completed_job_races"]+=1
            copied["nuke"]=bool(query and post[f"io_ldu_rarNukeQuery_{lane}_resp_bits_nuke"])
            copied["bits"]=self.project(item,s,query and not pre[f"io_ldu_rarNukeQuery_{lane}_req_ready"],
                                         query and not pre[f"io_ldu_rawNukeQuery_{lane}_req_ready"],item["nuke1"] or self.sta_nuke(item,i.addresses,s))
            if not s["cancelled"]:next2[lane]=copied
        next1=[None]*3
        for lane,item in enumerate(self.p0):
            if item is None:continue
            s=self.instructions[item["uid"]];p=f"io_forward_{lane}_s2Resp_";t=i.translations[lane]
            assert t.paddr==item["PA"]
            assert post[p+"valid"]==int(not t.kill)
            copied=deepcopy(item);f=dict(addr=False,data=False,forward=False)
            if not t.kill:
                f=dict(addr=bool(post[p+"bits_addrInvalid_valid"]),data=bool(post[p+"bits_dataInvalid_valid"]),forward=bool(post[p+"bits_forwardInvalid"]))
                mask=sum(post[p+f"bits_forwardMask_{b}"]<<b for b in range(16))
                copied["full_forward"]=not f["data"] and mask&item["mask"]==item["mask"]
                copied["match"]=bool(post[p+"bits_matchInvalid"])
            else:copied["full_forward"],copied["match"]=False,False
            copied["flags"]=f;copied["nuke1"]=item["extra"]!=3 and self.sta_nuke(item,i.addresses,s)
            copied["special"]=bool(pre["io_specialMode"] and s["order"]!=head)
            copied["exception"]=0
            if item["uncache"]:
                a=s["bus"];assert a is not None and a["response"] is not None
                bp=f"io_bypass_{lane}_s2Resp_";assert post[bp+"valid"]
                assert post[bp+"bits_data"]==a["data"]*((1<<64)+1) and post[bp+"bits_derr"]==a["error"] and post[bp+"bits_nderr"]==a["nderr"]
                a["consumed"]=True;copied["exception"]=int(a["nderr"])<<5|int(a["error"])<<19
                self.counts["actual_original_bypass_consumptions"]+=1
            if not s["cancelled"]:next1[lane]=copied
        for lane,item in enumerate(self.source0):
            assert i.queries[lane].valid==(item is not None)
            if item is None:continue
            s=self.instructions[item["uid"]];q=i.queries[lane]
            assert q.vaddr==item["VA"] and q.size==item["size"] and sq(q.sq)==sq_dict(s["source"]["execution"]["uop"]["sq"])
            if item["uncache"]:assert i.bypass[lane].valid and s["grant"] is not None
            self.counts["source_S0_tickets"]+=1
        self.p0,self.p1,self.p2=deepcopy(self.source0),next1,next2
        # Independent original external SID ledger. No response-to-consumption
        # lifetime extension: a real response immediately releases its SID.
        if pre["io_uncache_req_valid"]:
            code_value=(160*pre["io_uncache_req_bits_robIdx_flag"]+pre["io_uncache_req_bits_robIdx_value"])*2+int(not pre["io_uncache_req_bits_robIdx_isFormer"])
            key=(code_value,pre["io_uncache_req_bits_id"],pre["io_uncache_req_bits_addr"],pre["io_uncache_req_bits_cmd"])
            if self.elastic is None or self.elastic[0]!=key:
                matches=[s for s in self.program if s["order"]%640==code_value and self.in_rob(s)
                         and s["source"]["paddr"]==pre["io_uncache_req_bits_addr"]]
                assert len(matches)==1;self.elastic=(key,matches[0]["uid"])
            if i.bus.ready:
                s=self.instructions[self.elastic[1]]
                a=dict(uid=s["uid"],mid=pre["io_uncache_req_bits_id"],sid=None,response=None,consumed=False)
                self.jobs.append(a);s["bus"]=a;self.counts["actual_external_bus_requests"]+=1;self.elastic=None
        else:self.elastic=None
        if i.bus.ack:
            hits=[a for a in self.jobs if a["mid"]==i.bus.mid and a["sid"] is None and is_load_kind(self.instructions[a["uid"]]["kind"])==i.bus.ack_to_load]
            assert len(hits)==1 and not any(a["sid"]==i.bus.sid and a["response"] is None for a in self.jobs)
            hits[0]["sid"]=i.bus.sid
        if i.bus.response:
            hits=[a for a in self.jobs if a["sid"]==i.bus.response_id and a["response"] is None and is_load_kind(self.instructions[a["uid"]]["kind"])==i.bus.response_to_load]
            assert len(hits)==1 and not(i.bus.error and i.bus.nderr)
            hits[0].update(response=tick,data=i.bus.data,error=i.bus.error,nderr=i.bus.nderr);self.counts["actual_external_bus_returns"]+=1
        for bank in range(3):
            p=f"io_replay_{bank}_"
            if pre[p+"valid"] and i.replay_ready[bank]:
                value=120*pre[p+"bits_uop_lqIdx_flag"]+pre[p+"bits_uop_lqIdx_value"]
                s=next(s for pos,s in self.lq_owners.items() if pos%240==value and not(s["cancelled"] or s["released"]))
                assert s["grant"] is None;s["grant"]=pre[p+"bits_replayQueueIdx"];self.counts["actual_replay_grants"]+=1
        if pre["io_cmoOpReq_valid"] and i.cache_ready:
            s=next(s for s in self.program if self.in_rob(s) and s["kind"]=="cbo" and s["order"]==head)
            p=s["source"];assert self.cmo_job is None and p["cbo"]!=3
            assert pre["io_cmoOpReq_bits_opcode"]==p["cbo"] and pre["io_cmoOpReq_bits_address"]==p["paddr"]
            a=dict(job=len(self.cmo_jobs)+1,uid=s["uid"],opcode=p["cbo"],PA=p["paddr"],accepted_tick=tick,returned_tick=None)
            self.cmo_jobs.append(a);self.cmo_job=a;self.counts["actual_original_CBO_Cache_requests"]+=1
        if i.cache_response:
            assert self.cmo_job is not None and pre["io_cmoOpResp_ready"]
            a=self.cmo_job;a.update(returned_tick=tick,denied=i.cache_denied,corrupt=i.cache_corrupt)
            self.instructions[a["uid"]]["cache_response"]=a;self.cmo_job=None
            self.counts["actual_original_CBO_Cache_responses"]+=1
        if pre["io_mmioStout_valid"] and i.writeback_ready:
            value=(160*pre["io_mmioStout_bits_robIdx_flag"]+pre["io_mmioStout_bits_robIdx_value"])*2+int(not pre["io_mmioStout_bits_robIdx_isFormer"])
            s=next(s for s in self.program if s["order"]%640==value and self.in_rob(s))
            assert s["order"]==head
            s["wb"]=tick;s["fault_WB"]=bool(pre["io_mmioStout_bits_exceptionVec_7"] or pre["io_mmioStout_bits_exceptionVec_19"])
        for lane in range(2):
            p=f"io_sbuffer_req_{lane}_"
            if pre[p+"valid"] and i.sbuffer_ready[lane]:
                s=next(s for s in self.program if not is_load_kind(s["kind"]) and not(s["released"] or s["cancelled"]) and
                        (s["kind"]=="store" or s["kind"]=="cbo" and s["source"]["cbo"]==3) and
                        s["consumed"]<(2 if s["source"]["vaddr"]%16+(1<<s["source"]["size"])>16 else 1))
                assert s["sta"] and s["std"] and s["s2"] and s["order"]<=head
                source=s["source"];part=s["consumed"];va=source["vaddr"]//16*16+16*part;pa=source["paddr"]//16*16+16*part
                mask=value=0;zero=bool(s["kind"]=="cbo")
                for offset in range(1<<source["size"]):
                    b=source["vaddr"]+offset-va
                    if 0<=b<16:
                        mask|=1<<b
                        value|=(0 if zero else source["value"]>>(8*offset)&255)<<(8*b)
                assert pre[p+"bits_vaddr"]==va and pre[p+"bits_addr"]==pa and pre[p+"bits_mask"]==mask and pre[p+"bits_wline"]==zero
                valid_bytes=sum(255<<(8*b) for b in range(16) if mask>>b&1)
                assert not((pre[p+"bits_data"]^value)&valid_bytes)
                self.counts["actual_original_zero16_fires" if zero else "actual_original_normal_Store_fragments"]+=1
                s["consumed"]+=1;s["last_fire"]=tick
        new_sh=128*post["io_sqDeqPtr_first_flag"]+64*post["io_sqDeqPtr_second_flag"]+post["io_sqDeqPtr_value"]
        delta=(new_sh-self.sh)%256;assert delta<=2
        for pos in range(self.sh,self.sh+delta):
            s=self.sq_owners[pos];assert not(s["cancelled"] or s["released"])
            s["released"]=True;self.counts["actual_SQ_structure_release"]+=1
        self.sh+=delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            n=post["io_toLsqEnqCtrl_lqDeq_bits"]
            for pos in range(self.lh,self.lh+n):
                s=self.lq_owners[pos]
                assert not(s["cancelled"] or s["released"]) and s.get("finish_ready",tick)<tick
                s["released"]=True;self.counts["actual_LQ_structure_release"]+=1
            self.lh+=n
        if i.redirect.valid:
            cutoff=self.order(i.redirect.rob)+int(not i.redirect.flush_self)
            assert cutoff>=head and self.recovery is None
            target=next((s for s in self.program if s["order"]==self.order(i.redirect.rob) and self.in_rob(s)),None)
            if self.redirect_source=="external_trap_after_original_LSQ_completion":
                assert target is not None and target["fault_WB"]
                assert i.redirect.flush_self and target["order"]==head and target["wb"]<tick
                self.traps.append(dict(uid=target["uid"],tick=tick,ROB=target["order"],LQ_already_released=target["released"]))
            lq_victims=[s for s in self.lq_owners.values() if s["order"]>=cutoff and not(s["released"] or s["cancelled"])]
            sq_victims=[s for s in self.sq_owners.values() if s["order"]>=cutoff and not(s["released"] or s["cancelled"])]
            self.recovery=dict(lq=self.lt-len(lq_victims),sq=min((s["pos"] for s in sq_victims),default=self.st),LQ=False,SQ=False)
            for s in self.program:
                if s["order"]>=cutoff and not s["retired"]:
                    if not s["released"]:s["cancelled"]=True
                    else:s["rob_cancelled_after_release"]=True
            # The actual source S2/S3 outputs on the redirect edge are still
            # valid (NewLoadUnit1216/1557), but killed pipeOutValid must not be
            # carried into the NEXT cycle (1153/1704). Do not invent a packet
            # for those cancelled tickets after their real redirect.
            self.p0,self.p1,self.p2=([x if x is None or self.in_rob(self.instructions[x["uid"]]) else None for x in stage]
                                    for stage in(self.p0,self.p1,self.p2))
            self.heads={uid:x for uid,x in self.heads.items() if self.in_rob(self.instructions[uid])}
            self.counts["actual_shared_redirects"]+=1
        if self.recovery is not None:
            r=self.recovery
            if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:
                assert 120*post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]==r["lq"]%240
                self.lt=r["lq"];r["LQ"]=True
            if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
                assert 128*post["io_toLsqEnqCtrl_sqRedirectPtr_bits_first_flag"]+64*post["io_toLsqEnqCtrl_sqRedirectPtr_bits_second_flag"]+post["io_toLsqEnqCtrl_sqRedirectPtr_bits_value"]==r["sq"]%256
                self.st=r["sq"];r["SQ"]=True
            if r["LQ"] and r["SQ"] and not(post["io_toLsqEnqCtrl_lqRecoverStall"] or post["io_toLsqEnqCtrl_sqRecoverStall"]):self.recovery=None

    def finish(self):
        assert self.recovery is None and all(not x for x in self.external.values())
        assert self.cmo_job is None and all(a["returned_tick"] is not None for a in self.cmo_jobs)
        assert all(s["released"] or s["cancelled"] for s in self.program)
        assert all(j["response"] is not None for j in self.jobs)
        for s in self.program:
            if s["cancelled"]:
                size=120 if is_load_kind(s["kind"]) else 64
                assert any(n["uid"]>s["uid"] and is_load_kind(n["kind"])==is_load_kind(s["kind"]) and n["pos"]%size==s["pos"]%size and
                           n["released"] and not n["fault_WB"] for n in self.program),"a fault-WB release is not normal same-slot replacement completion"

    def summary(self):
        return dict(counts=dict(self.counts),last_source_error=self.last_source_error,original_full_output_error=self.core_error,traps=self.traps,
                    CBO_Cache_jobs=self.cmo_jobs,
                    window=dict(first_tick=self.first_tick,last_tick=self.last_tick),
                    observed_UIDs=[{k:s[k] for k in("uid","order","kind","pos","dispatched","cancelled","released","retired","fault_WB")} for s in self.program],
                    pending_external_jobs={k:len(v) for k,v in self.external.items()},
                    limits="independent online declared-source and public-input/output checks, not persisted per-cycle replay or native upstream proof; initial vector QB current producer route unproven and counted separately")


def sq_dict(p):return 128*int(p["first"])+64*int(p["second"])+p["value"]
def is_load_kind(kind):return kind in("cached","nc_load","mmio_load","io_load")
