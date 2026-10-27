#!/usr/bin/env python3
"""Three previously unclassified mixed terminal observations, original UIDs.

No DUT/model/actor/change/expected fields are used as semantic answers. The
existing independent prefix legality helper is retained, not widened. A zero
flush transition is deliberately NOT called an observed bad WB or SQ release.
"""
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, rob, rob_matches, sq
from audit_lsq_mixed_history_v1 import Timeline
from audit_lsq_mixed_history_v2 import inspect as inspect_prefix
from audit_lsq_population_v1 import events, paths_by_node
from audit_sq_initial import ROOT, sha, verify_common


def words(s):
    a = s["address"]
    result = []
    for part in range(2 if a["cross_word"] else 1):
        va,pa,mask,value = a["vaddr"]//16*16+part*16,a["paddr"]//16*16+part*16,0,0
        for b in range(1<<a["size"]):
            target = a["vaddr"]+b-va
            if 0<=target<16:
                mask |= 1<<target
                value |= ((s["data"]>>(8*b)) & 255)<<(8*target) if s.get("cbo")!=3 else 0
        result.append((va,pa,mask,value))
    return result


class History:
    def __init__(self):
        self.timeline = Timeline()
        self.owners,self.stores,self.loads,self.jobs,self.fires = [],{},{},[],[]
        self.sh=self.st=self.lh=self.lt=0
        self.s2=[]
        self.previous=None
        self.final=None

    def owner(self,ptr,kind):
        order=self.timeline.decode(ptr)
        found=[s for s in self.owners if s["order"]==order and s["kind"]==kind and not s["cancelled"]]
        assert len(found)==1,("original ROB generation",order,kind)
        return found[0]

    def step(self,row):
        i,pre,post,tick=row["input"],row["before"],row["after"],row["post_tick"]
        if i["reset"]:
            assert not self.owners
            self.previous=row
            return
        assert pointer(pre,"io_sqDeqPtr_")==self.sh%256
        head=self.timeline.decode(i["pending"],True)
        for d in i["dispatch"]:
            if not d["valid"]:continue
            order=self.timeline.decode(d["rob"],True)
            s=dict(uid=len(self.owners)+1,order=order,rob=d["rob"],kind="load" if d["need_alloc"]==1 else "store",cancelled=False,complete=False,consumed=set())
            self.owners.append(s)
            if s["kind"]=="store":
                s["pos"]=self.st
                self.stores[self.st]=s
                self.st+=1
                assert sq(d["store_end"])==self.st%256
            else:
                s.update(pos=self.lt,bound=self.st)
                self.loads[self.lt%240]=s
                self.lt+=1
        for s,lane,last in self.s2:
            a=i["attributes"][lane]
            if last:
                s.update(address_ready=True,memory=bool(a["nc"] or a["mmio"] or not a["memory"]))
        self.s2=[]
        for lane,a in enumerate(i["addresses"]):
            if not a["valid"]:continue
            pos=self.sh+(a["slot"]-self.sh)%64
            s=self.stores[pos]
            assert s["rob"]==a["rob"] and not s["cancelled"] and not s["complete"]
            if not a["tlb_miss"]:
                if not a["cross_word"] or not a["last"] or "address" not in s:s["address"]=a
                s["cbo"]=a["fu_op"]>>1 & 7 if a["fu_op"] & 1 else None
                self.s2.append((s,lane,a["last"]))
        for d in i["data"]:
            if d["valid"]:
                pos=self.sh+(sq(d["sq"])-self.sh)%256
                assert not self.stores[pos]["cancelled"]
                self.stores[pos]["data"]=d["data"]
        for packet in i["loads"]:
            q=packet["execution"]
            if q["valid"]:
                s=self.loads[120*int(q["uop"]["lq"]["flag"])+q["uop"]["lq"]["value"]]
                assert s["rob"]==q["uop"]["rob"]
                s.update(packet=packet,pa=packet["paddr"],va=q["vaddr"])
        for q in i["rar_queries"]:
            if q["valid"]:
                s=self.owner(q["rob"],"load")
                s["pa"]=q["paddr"]
        if pre["io_uncache_req_valid"] and i["bus"]["ready"]:
            kind="load" if pre["io_uncache_req_bits_cmd"]==0 else "store"
            ptr=dict(flag=bool(pre["io_uncache_req_bits_robIdx_flag"]),value=pre["io_uncache_req_bits_robIdx_value"],former=bool(pre["io_uncache_req_bits_robIdx_isFormer"]))
            order=self.timeline.decode(ptr)
            matches=[s for s in self.owners if s["order"]==order and s["kind"]==kind and
                     (kind=="load" or not s["cancelled"]) and
                     s.get("pa",s.get("address",{}).get("paddr"))==pre["io_uncache_req_bits_addr"]]
            # Actual elastic Load packages may finish accepting after their
            # redirect. Original PA+ROB binds their old UID uniquely; unlike
            # a Store, cancellation does not erase an old external read job.
            # The unchanged independent prefix helper separately checks the
            # producer domain. Do not discard these reads from this ledger.
            assert len(matches)==1
            s=matches[0]
            self.jobs.append(dict(owner=s,kind=kind,mid=pre["io_uncache_req_bits_id"],sid=None,response=None,request_tick=tick,
                                  serial=not(i["bus"]["outstanding"] and pre["io_uncache_req_bits_nc"]),pa=pre["io_uncache_req_bits_addr"]))
        b=i["bus"]
        if b["ack"]:
            js=[j for j in self.jobs if j["sid"] is None and j["mid"]==b["mid"] and (j["kind"]=="load")==b["ack_to_load"]]
            assert len(js)==1
            js[0]["sid"]=b["sid"]
        returned=None
        if b["response"]:
            js=[j for j in self.jobs if j["response"] is None and j["sid"]==b["response_id"] and (j["kind"]=="load")==b["response_to_load"]]
            assert len(js)==1
            returned=js[0]
            returned["response"]=tick
        for lane in range(2):
            p=f"io_sbuffer_req_{lane}_"
            if pre[p+"valid"] and i["sbuffer_ready"][lane]:
                candidates=[s for s in self.stores.values() if not s["cancelled"] and not s["complete"] and s.get("address_ready") and not s.get("memory") and s.get("cbo") in (None,3) and len(s["consumed"])<len(words(s))]
                s=min(candidates,key=lambda s:s["pos"])
                part=len(s["consumed"])
                va,pa,mask,value=words(s)[part]
                assert (pre[p+"bits_vaddr"],pre[p+"bits_addr"],pre[p+"bits_mask"],pre[p+"bits_wline"])==(va,pa,mask,int(s.get("cbo")==3))
                bits=sum(255<<(8*b) for b in range(16) if mask>>b & 1)
                assert not((pre[p+"bits_data"]^value)&bits)
                s["consumed"].add(part)
                self.fires.append(dict(tick=tick,uid=s["uid"],sq=s["pos"],part=part,pa=pa,va=va,wline=pre[p+"bits_wline"]))
        if "error" in row:
            self.final=dict(tick=tick,head=head,pending=i["pending"],returned=returned,row=row,
                            owners=list(self.owners),eligible_stores=[s.copy() for s in self.stores.values() if not s["cancelled"] and not s["complete"]],
                            previous=self.previous)
        if i["redirect"]["valid"]:
            cut=self.timeline.decode(i["redirect"]["rob"])
            for s in self.owners:
                if not s["complete"] and s["order"]>=cut:s["cancelled"]=True
        delta=(pointer(post,"io_sqDeqPtr_")-self.sh)%256
        assert delta<=2
        for p in range(self.sh,self.sh+delta):self.stores[p]["complete"]=True
        self.sh+=delta
        if post["io_toLsqEnqCtrl_lqDeq_valid"]:
            for p in range(self.lh,self.lh+post["io_toLsqEnqCtrl_lqDeq_bits"]):self.loads[p%240]["complete"]=True
            self.lh+=post["io_toLsqEnqCtrl_lqDeq_bits"]
        if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:self.st=self.sh+(pointer(post,"io_toLsqEnqCtrl_sqRedirectPtr_bits_")-self.sh)%256
        if post["io_toLsqEnqCtrl_lqRedirectPtr_valid"]:self.lt=self.lh+(120*post["io_toLsqEnqCtrl_lqRedirectPtr_bits_flag"]+post["io_toLsqEnqCtrl_lqRedirectPtr_bits_value"]-self.lh)%240
        self.previous=row


def describe(s):
    return dict(uid=s["uid"],kind=s["kind"],absolute_rob=s["order"],absolute_queue_position=s["pos"],rob=s["rob"],
                address=s.get("address"),data=s.get("data"),cbo=s.get("cbo"),consumed_parts=sorted(s["consumed"]))


def serial(h):
    f=h.final
    row=f["row"]
    pre,post,b=row["before"],row["after"],row["input"]["bus"]
    blocked=[j for j in h.jobs if j["serial"] and j["response"] is None]
    assert len(blocked)==1 and blocked[0]["kind"]=="store" and blocked[0]["request_tick"]==214
    old=blocked[0]
    returned=f["returned"]
    assert f["tick"]==216 and returned is not None and returned["kind"]=="load" and returned is not old
    assert not pre["io_uncache_req_valid"] and post["io_uncache_req_valid"]
    assert post["io_uncache_req_bits_cmd"]==0 and post["io_uncache_req_bits_robIdx_value"]!=old["owner"]["rob"]["value"]
    return dict(issue="LSQ-BUS-OWNERSHIP-001",observed="new visible read while accepted serial Store still owes its OWN response",
                serial_store=describe(old["owner"]),serial_store_request_tick=old["request_tick"],serial_store_mid=old["mid"],serial_store_sid=old["sid"],
                unrelated_returned_load=describe(returned["owner"]),returned_sid=returned["sid"],returned_tick=returned["response"],
                wrong_new_visible_tick=f["tick"],wrong_new_visible_PA=post["io_uncache_req_bits_addr"],
                scope="actual post-edge req.valid violates serial ownership; no following third request.fire/response or ISA consequence claimed")


def zero(h):
    f=h.final
    row=f["row"]
    pre,post=row["before"],row["after"]
    z=[s for s in f["eligible_stores"] if s["order"]==f["head"] and s.get("cbo")==3]
    assert len(z)==1 and f["tick"]==302 and not pre["io_flushSbuffer_valid"] and post["io_flushSbuffer_valid"]
    z=z[0]
    fires=[fire for fire in h.fires if fire["tick"]==302]
    assert len(fires)==1 and fires[0]["uid"]!=z["uid"] and not fires[0]["wline"] and not z["consumed"]
    assert not pre["io_mmioStout_valid"] and not post["io_mmioStout_valid"]
    return dict(observed="zero-at-ROB-head flush rises on a DIFFERENT original ordinary Store consumption",zero=describe(z),
                triggering_actual_ordinary_fragment=fires[0],tick=f["tick"],
                scope="staged phase divergence consistent with NewStoreQueue.scala975-978 using untagged head.fire; this prefix observes NO zero WB, no zero SQ release and no ISA violation. Existing directed protocol zero counterexamples remain separate evidence, not invented follow-on effects.")


def physical(h):
    f=h.final
    row,old=f["row"],f["previous"]
    assert f["tick"]==390 and not any(a["valid"] for a in row["input"]["addresses"])
    lane=1
    q=old["input"]["queries"][lane]
    r=old["input"]["rar_queries"][lane]
    load=h.owner(r["rob"],"load")
    assert q["valid"] and load["bound"]%256==sq(q["sq"])
    pa=row["input"]["translations"][lane]["paddr"]
    assert not row["input"]["translations"][lane]["kill"] and pa==r["paddr"]
    p=f"io_forward_{lane}_s2Resp_"
    post=row["after"]
    assert post[p+"valid"] and not any(post[p+"bits_"+name] for name in ("forwardInvalid","matchInvalid","addrInvalid_valid","dataInvalid_valid"))
    eligible=[s for s in f["eligible_stores"] if h.sh<=s["pos"]<min(load["bound"],h.sh+64) and s.get("address_ready")]
    counterexamples=[]
    for byte in range(16):
        if not post[p+f"bits_forwardMask_{byte}"]:continue
        address=pa//16*16+byte
        sources=[]
        for s in eligible:
            a=s["address"]
            off=address-a["paddr"]
            # CBO describes a cache LINE, not an ordinary size-byte Store.
            # PSQ's public STD fu-op writes zero for cbo.zero irrespective of
            # input STD payload (NewStoreQueue.scala1966). v2 incorrectly
            # confined every candidate to [PA,PA+size), losing this producer.
            hit=(address//64==a["paddr"]//64) if s.get("cbo") is not None else 0<=off<1<<a["size"]
            if hit and "data" in s:
                sources.append((s,0 if s.get("cbo")==3 else s["data"]>>(8*off)&255))
        assert sources,"no physical source in original eligible bank"
        latest,want=max(sources,key=lambda item:item[0]["pos"])
        actual=post[p+f"bits_forwardData_{byte}"]
        if actual!=want:
            matching=[s for s,value in sources if value==actual]
            assert matching
            counterexamples.append(dict(byte=byte,physical_byte_address=address,actual_byte=actual,expected_youngest_original_byte=want,
                                        youngest_original_source=describe(latest),matching_stale_original_sources=[describe(s) for s in matching]))
    assert counterexamples
    assert all(b["youngest_original_source"]["cbo"]==3 for b in counterexamples)
    return dict(observed="whole-line original CBO.zero suppressed by ordinary byte-range selection; unblocked older bytes returned",load=describe(load),query_tick=old["post_tick"],response_tick=f["tick"],lane=lane,
                query_VA=q["vaddr"],translated_PA=pa,original_SQ_boundary=load["bound"],physical_dequeue=h.sh,bytes=counterexamples,
                scope="actual unblocked bytes are stale against a younger original zero-line producer in the current physical window. This is not relabelled as a VA synonym example: both share this VA/PA line. Minimal normal-size directed reproduction and exact root-cause isolation remain work; no resulting ISA execution consequence claimed")


def audit():
    run=ROOT/"results/lsq-expanded-16"
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":269,"FAIL":48}
    paths=paths_by_node(run)
    cases=[]
    for seed,extract in ((28928,physical),(28932,zero),(28933,serial)):
        node=next(n for n in paths if "test_seeded_mixed.py::" in n and n.endswith(f"[{seed}]"))
        path=paths[node]
        prefix=inspect_prefix(path)
        assert not prefix["independent_terminal_counterexamples"] and nodes[node]
        h=History()
        for row in events(path):h.step(row)
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),public_prefix_legality_records=prefix["counts"]["raw_records"],**extract(h)))
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    for f in (Path(__file__),ROOT/"tools/audit_lsq_mixed_terminal_v1.py",ROOT/"tools/audit_lsq_mixed_terminal_v2.py",ROOT/"tools/audit_lsq_mixed_history_v2.py"):
        target=dest/f.name
        if target.exists():assert sha(target)==sha(f)
        else:shutil.copy2(f,target)
    report=dict(run=run.name,status="three_remaining_mixed_terminal_observations_original_UID_and_scope_audited_NOT_PASS",cases=cases,
                auditor_sha256=sha(dest/Path(__file__).name),limits="No stimuli/reference/RTL changes, no failures hidden, no original obligations completed by audit. PA and serial visibility have independent original-effect witnesses. Zero is strictly phase-only, not a fabricated bad WB/release. Prefix audit remains unchanged. No full random/STRESS or Backend/ISA acceptance.")
    report["preserved_v1_rejection"]="v1 wrongly excluded cancelled elastic Load requests from all ROB lookup, so rejected an actually late accepted old Load. v2 binds that actual external read by original PA+ROB uniquely, while cancelled Store remains excluded. The existing independent prefix legality helper and tests/stimuli/outputs are unchanged; v1 source retained."
    report["preserved_v2_rejection"]="v2 confined all physical producers to ordinary size bytes, so missed the same-line original CBO.zero. v3 uses true whole-line CBO coverage and zero data semantics; this rejects rather than blesses stale bytes. v1/v2 source preserved; actual raw traces/strict comparison/independent prefix helper unchanged."
    out=run/"mixed-terminal-audit-v3.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=="__main__":audit()
