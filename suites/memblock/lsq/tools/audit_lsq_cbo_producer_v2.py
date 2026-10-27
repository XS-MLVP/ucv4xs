import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Real StoreUnit CBO bindings: a green staged check is not producer legality.

Read-only source/journals. Retains every ordinary FAIL and old result. No
model/actor/expected/change/issue manifest is an oracle. This deliberately
refuses previous NORMAL claims if interface-only CBO metadata was supplied.
"""
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_population_v1 import events, paths_by_node
from audit_sq_initial import ROOT, sha, verify_common


def audit():
    run=ROOT/"results/lsq-normal-cbo-01"
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":6,"FAIL":8} and len(nodes)==14
    unit=ucv_paths.source_path_for(ROOT) / 'src/main/scala/xiangshan/mem/pipeline/NewStoreUnit.scala'
    common=ucv_paths.source_path_for(ROOT) / 'src/main/scala/xiangshan/mem/MemCommon.scala'
    lsq=ucv_paths.source_path_for(ROOT) / 'src/main/scala/xiangshan/mem/lsqueue/LSQWrapper.scala'
    u,c,w=(p.read_text() for p in (unit,common,lsq))
    required=("toSqAddr.paddr := Mux(isCbo, alignVWordAddr(paddr), paddr)",
              "toSqAddr.vaddr := Mux(isCbo, alignVWordAddr(vaddr), vaddr)",
              "toSqAddr.size := Mux(isCbo, MemorySize.QB.U, size)","toSqAddr.wlineflag := isCbo",
              "Fill(VLEN/8, 1.U(1.W))")
    assert all(s in u for s in required) and 'case object QB extends Size(BitPat("b100"))' in c
    assert "storeQueue.io.fromStoreUnit.storeAddrIn     <> io.sta.storeAddrIn" in w
    assert "loadQueue.io.sta.storeAddrIn     <> io.sta.storeAddrIn" in w
    paths=paths_by_node(run)
    cases=[]
    patterns,counts=Counter(),Counter()
    for node,path in sorted(paths.items()):
        normal_required="test_normal_cbo_mixed.py::" in node
        assert normal_required
        defects=[]
        writes=0
        for row in events(path):
            for lane,a in enumerate(row["input"]["addresses"]):
                if not a["valid"] or not a["fu_op"] & 1:continue
                writes+=1
                shape=(a["size"],a["mask"],int(a["wline"]),a["vaddr"]%16,a["paddr"]%16)
                patterns[shape]+=1
                errors=[]
                for name,expected in (("size",4),("mask",65535),("wline",True)):
                    if a[name]!=expected:errors.append(dict(field=name,actual=a[name],normal_producer=expected))
                if a["vaddr"]%16 or a["paddr"]%16:errors.append(dict(field="PA/VA alignment",actual=[a["paddr"]%16,a["vaddr"]%16],normal_producer=[0,0]))
                if errors:defects.append(dict(tick=row["post_tick"],lane=lane,rob=a["rob"],slot=a["slot"],cbo_opcode=a["fu_op"]>>1 & 7,errors=errors))
        if writes:
            counts["cases_with_CBO_STA"]+=1
            counts["actual_CBO_STA_writes"]+=writes
            counts["non_normal_CBO_STA_writes"]+=len(defects)
            if normal_required:
                counts["required_normal_cases_not_admitted" if defects else "required_normal_cases_admitted"]+=1
            cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),pytest_result="FAIL" if nodes[node] else "PASS",
                              normal_domain_claim_required=normal_required,actual_CBO_STA=writes,producer_violations=defects,
                              classification="NOT_ADMITTED_NORMAL_CBO_FLOW" if defects else "normal_retained_CBO_metadata_present"))
    assert counts["required_normal_cases_admitted"]==14 and not counts["required_normal_cases_not_admitted"] and not counts["non_normal_CBO_STA_writes"]
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    tool=Path(__file__)
    target=dest/tool.name
    if target.exists():assert sha(tool)==sha(target)
    else:shutil.copy2(tool,target)
    report=dict(run=run.name,status="NORMAL_CBO_PACKAGE_METADATA_ADMITTED_FOR_NEW14_NOT_FULL_RANDOM_ACCEPTANCE",
                tests_unchanged=manifest["tests"],counts=dict(counts),actual_shapes=[dict(size=k[0],mask=k[1],wline=k[2],va_mod16=k[3],pa_mod16=k[4],writes=v) for k,v in sorted(patterns.items())],
                source_evidence=[dict(path=str(p),sha256=sha(p)) for p in (unit,common,lsq)],
                source_bindings="NewStoreUnit.scala98-102 whole-line mask;433-438 aligned16/QB/wline=true; MemCommon.scala169 QB=b100; LSQWrapper.scala206/252 connects same STA to SQ and LQ",
                auditor_sha256=sha(target),cases=cases,
                consequences="All14 NEW native cases really carry normal aligned16/QB/fullmask/wline CBO on the shared SQ/RAW STA input. v1 rejection of old size3 interface cases remains unchanged and is not retroactively overturned. This is CBO-package metadata admission ONLY, not complete Backend/dispatch legality, full-domain random completion, late response handling or STRESS signoff. Six joint positives and eight first-failure mixed attempts require their own UID/effect/reference-domain audits. No old result/RTL/stimulus changed, no FAIL hidden.")
    original=ROOT/"tools/audit_lsq_cbo_producer_v1.py"
    old_target=dest/original.name
    if old_target.exists():assert sha(original)==sha(old_target)
    else:shutil.copy2(original,old_target)
    out=run/"cbo-producer-audit-v2.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":audit()
