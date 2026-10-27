import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""CBO normal PACKAGE fields do not waive actual NoSpec/BlockBack producer rules."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import pointer, sq
from audit_lsq_mixed_history_v1 import Timeline
from audit_lsq_population_v1 import events, paths_by_node
from audit_sq_initial import ROOT, sha, verify_common


def inspect(path):
    history,bysq,program=[],{},[]
    head=tail=epoch=0
    timeline=Timeline()
    resetting=False
    for row in events(path):
        i,pre,post,tick=row["input"],row["before"],row["after"],row["post_tick"]
        if i["reset"]:
            if not resetting:
                for s in program:
                    if s["cancel_tick"] is None:s["cancel_tick"]=tick
                if program:epoch+=1
                program,bysq=[],{}
                head=tail=0
                timeline=Timeline()
            resetting=True
            continue
        resetting=False
        order=timeline.decode(i["pending"],True)
        assert pointer(pre,"io_sqDeqPtr_")==head%256
        for d in i["dispatch"]:
            if not d["valid"]:continue
            assert d["flows"]==1 and d["need_alloc"] in(1,2)
            age=timeline.decode(d["rob"],True)
            s=dict(uid=len(history)+1,epoch=epoch,order=age,rob=d["rob"],dispatch_tick=tick,head_order_at_dispatch=order,
                   prior_ROB_uids=[old["uid"] for old in program if old["cancel_tick"] is None and old["order"]>=order],
                   kind="store" if d["need_alloc"]==2 else "load",cancel_tick=None,cbo=None)
            history.append(s)
            program.append(s)
            if s["kind"]=="store":
                s["sq_position"]=tail
                bysq[tail]=s
                tail+=1
                assert sq(d["store_end"])==tail%256
        for a in i["addresses"]:
            if not a["valid"]:continue
            s=bysq[head+(a["slot"]-head)%64]
            assert s["rob"]==a["rob"] and s["cancel_tick"] is None
            if a["fu_op"]&1:
                s["cbo"]=a["fu_op"]>>1&7
                s.setdefault("STA_tick",tick)
                s.setdefault("STA_shape",[a["size"],a["mask"],bool(a["wline"])])
        if i["redirect"]["valid"]:
            cut=timeline.decode(i["redirect"]["rob"])
            for s in program:
                if s["cancel_tick"] is None and s["order"]>=cut:s["cancel_tick"]=tick
        head+=(pointer(post,"io_sqDeqPtr_")-head)%256
        if post["io_toLsqEnqCtrl_sqRedirectPtr_valid"]:
            tail=head+(pointer(post,"io_toLsqEnqCtrl_sqRedirectPtr_bits_")-head)%256
    cases=[]
    counts=Counter()
    for s in history:
        if s["cbo"] is None:continue
        younger=[other for other in history if other["epoch"]==s["epoch"] and other["dispatch_tick"]>=s["dispatch_tick"] and
                 other["order"]>s["order"] and other["head_order_at_dispatch"]<=s["order"] and
                 (s["cancel_tick"] is None or other["dispatch_tick"]<s["cancel_tick"])]
        counts["CBO_original_owners_identified_from_actual_STA"]+=1
        counts["NoSpec_prior_ROB_not_empty"]+=bool(s["prior_ROB_uids"])
        counts["BlockBack_younger_admitted_before_CBO_retired_or_cancelled"]+=bool(younger)
        if s["prior_ROB_uids"] or younger:
            cases.append(dict(uid=s["uid"],epoch=s["epoch"],rob=s["rob"],absolute_order=s["order"],cbo=s["cbo"],
                              dispatch_tick=s["dispatch_tick"],STA_tick=s["STA_tick"],actual_STA_shape=s["STA_shape"],
                              NoSpec_prior_ROB_UIDs=s["prior_ROB_uids"],BlockBack_younger_UIDs=[o["uid"] for o in younger],
                              first_younger_public_witness=None if not younger else {k:younger[0][k] for k in("uid","rob","dispatch_tick","head_order_at_dispatch")}))
    return dict(counts=dict(counts),violations=cases)


def audit(name):
    assert name=="lsq-normal-cbo-03"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":26,"FAIL":8} and len(nodes)==34
    repo=ucv_paths.source_path_for(ROOT)
    files=[repo/"src/main/scala/xiangshan/backend/decode/opcode/Opcode.scala",
           repo/"src/main/scala/xiangshan/backend/vector/Decoder/DecodeStage.scala",
           repo/"src/main/scala/xiangshan/backend/dispatch/Dispatch.scala",
           repo/"src/main/scala/xiangshan/backend/rob/Rob.scala"]
    op,decode,dispatch,rob=(p.read_text() for p in files)
    for name in("cbo_zero","cbo_clean","cbo_flush","cbo_inval"):
        assert any(name in line and "+ NoSpec + BlockBack" in line for line in op.splitlines())
    assert "bits.waitForward := uopInfo.noSpec" in decode and "bits.blockBackward := uopInfo.blockBack" in decode
    assert "blockedByWaitForward(0) := !io.enqRob.isEmpty && isWaitForward(0)" in dispatch
    assert "!isBlockBackward(i)" in dispatch and "!blockedByWaitForward(i) && notBlockedByPrevious(i) && io.enqRob.canAccept" in dispatch
    assert "io.enq.canAccept := allowEnqueue && !hasBlockBackward" in rob
    assert "when(enqUop.valid && enqUop.bits.blockBackward && io.enq.canAccept)" in rob
    paths=paths_by_node(run)
    totals,results=Counter(),[]
    for node,path in sorted(paths.items()):
        if not any(t in node for t in("test_normal_cbo_mixed.py::","test_normal_cbo_paths.py::")):continue
        detail=inspect(path)
        totals.update(detail["counts"])
        results.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),pytest_result="FAIL" if nodes[node] else "PASS",**detail))
    assert len(results)==16 and any(r["violations"] for r in results)
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(Path(__file__),target)
    report=dict(run=name,status="REJECT_FULL_NORMAL_CBO_PROGRAM_ADMISSION_PACKAGE_FIELDS_ALONE_ARE_NOT_SUFFICIENT",tests_unchanged=manifest["tests"],
                counts=dict(totals),cases=results,source_evidence=[dict(path=str(p.relative_to(repo)),sha256=sha(p)) for p in files],
                auditor_sha256=sha(target),
                limits="Raw CBO QB/fullmask/wline pin metadata, actual effects, native coverage and FAILs remain real evidence. They do NOT establish normal Backend CBO reachability. NoSpec requires empty ROB at CBO dispatch; same-cycle BlockBack plus real ROB hasBlockBackward prevents younger dispatch until CBO retires/cancels. Unresolved older LSQ Stores may remain physically pending AFTER ROB retirement; this legal boundary must not be excluded when fixing producer. All original CBO opcodes/types/seeds must remain in new serialized traffic, not removed to pass. Full mixed/joint/simultaneous-pool claims involving current CBO program are interface-only until corrected. Endpoint18 contain no CBO and retain their separate proof. No existing result/RTL or rejection is modified.")
    out=run/"cbo-serialization-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
