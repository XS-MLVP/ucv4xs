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
    run=ROOT/"results/lsq-expanded-16"
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":269,"FAIL":48}
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
        normal_required="test_seeded_mixed.py::" in node or "test_joint_capacity.py::" in node
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
    assert counts["required_normal_cases_not_admitted"]==14 and not counts["required_normal_cases_admitted"]
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    tool=Path(__file__)
    target=dest/tool.name
    if target.exists():assert sha(tool)==sha(target)
    else:shutil.copy2(tool,target)
    report=dict(run=run.name,status="REJECT_PREVIOUS_NORMAL_CBO_PRODUCER_CLAIMS_KEEP_INTERFACE_RESULTS_AND_ALL_FAILURES",
                tests_unchanged=manifest["tests"],counts=dict(counts),actual_shapes=[dict(size=k[0],mask=k[1],wline=k[2],va_mod16=k[3],pa_mod16=k[4],writes=v) for k,v in sorted(patterns.items())],
                source_evidence=[dict(path=str(p),sha256=sha(p)) for p in (unit,common,lsq)],
                source_bindings="NewStoreUnit.scala98-102 whole-line mask;433-438 aligned16/QB/wline=true; MemCommon.scala169 QB=b100; LSQWrapper.scala206/252 connects same STA to SQ and LQ",
                auditor_sha256=sha(target),cases=cases,
                consequences="All eight current mixed prefixes and six current joint directed cases contain non-normal CBO metadata. Prior prefix/effect audits remain evidence of the raw PUBLIC INTERFACE executions only, not normal full-domain CBO traffic. Existing original311/199 equality, native/source provenance and simultaneous pre-CBO pool peaks remain facts, but they cannot bless ordinary producer legality. The size3 CBO stale-byte observation is interface-only, not a normal CBO RTL/ISA defect. Correct the CBO producer metadata without removing CBO/synonyms/SID/errors or weakening strict checking; freeze the currently running regression before editing its launch files, then rerun/audit new normal cases. Do not alter old artifacts, hide FAILs or mark STRESS checked.")
    out=run/"cbo-producer-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":audit()
