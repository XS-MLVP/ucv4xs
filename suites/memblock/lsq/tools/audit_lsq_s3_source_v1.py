import ucv.runtime as ucv_paths
#!/usr/bin/env python3
"""Native LDU S3 metadata/writing relationship, qualifying previous green flows.

Only raw public stage history and fixed open source. Kept PASS effects are NOT
retroactively changed into RTL failures; normal-producer admission is rejected.
"""
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_population_v1 import events, paths_by_node
from audit_sq_initial import ROOT, sha, verify_common


def inspect(path):
    rows=list(events(path))
    by_tick={r["post_tick"]:r for r in rows}
    counts=Counter()
    violations=[]
    for row in rows:
        t=row["post_tick"]
        for lane,packet in enumerate(row["input"]["loads"]):
            e=packet["execution"]
            if not e["valid"]:continue
            counts["actual_S3_packets"]+=1
            q=by_tick[t-6]["input"]["queries"][lane]
            assert q["valid"],("S3 has no native S0 ticket",path,t,lane)
            checks={"alignedType":(e["aligned_type"],q["size"]),"last_beat":(e["last_beat"],bool(packet["paddr"]&64))}
            f=by_tick[t-4]["after"]
            aligned=q["size"]<=3 and q["vaddr"]%16+(1<<q["size"])<=16
            # An aligned scalar replay with no exception/matchInvalid cannot
            # assert ldout/vldout. Leave split/error/writeback exceptions separate.
            if aligned and e["need_replay"] and not packet["exceptions"] and f[f"io_forward_{lane}_s2Resp_valid"] and not f[f"io_forward_{lane}_s2Resp_bits_matchInvalid"]:
                assert not e["vector"]
                checks["updateAddrValid"]=(packet["update_address"],False)
                counts["aligned_Replay_writeback_relation_checked"]+=1
            for field,(got,want) in checks.items():
                if got!=want:
                    counts[field+"_violations"]+=1
                    violations.append(dict(tick=t,lane=lane,original_ROB=e["uop"]["rob"],original_LQ=e["uop"]["lq"],field=field,actual=got,source_required=want,
                                           cause=e["causes"],source_lines="NewLoadUnit1596/1613/1145-1146+1516+1544+1607"))
    return dict(counts=dict(counts),violations=violations,normal_producer_admission="REJECT" if violations else "NO_VIOLATION_OF_THESE_NECESSARY_FIELDS_ONLY")


def audit():
    source=ucv_paths.source_path_for(ROOT) / 'src/main/scala/xiangshan/mem/pipeline/NewLoadUnit.scala'
    text=source.read_text()
    assert all(s in text for s in("lqWrite.alignedType := in.size","lqWrite.rep_info.last_beat := paddr(log2Up(refillBytes))",
                                 "lqWrite.updateAddrValid := ldoutValid || vldoutValid","val shouldWakeup = !shouldReplay && !isUncache && !exception && !isSwPrefetch"))
    cases=[]
    totals=Counter()
    for name in("lsq-ldu-rar-routing-03","lsq-ldu-mixed-02","lsq-raw-exclusive-04","lsq-raw-exclusive-05"):
        run=ROOT/"results"/name
        manifest,_,nodes=verify_common(run)
        per_run=Counter()
        details=[]
        for node,path in sorted(paths_by_node(run).items()):
            result=inspect(path)
            per_run.update(result["counts"])
            details.append(dict(nodeid=node,pytest_result="FAIL" if nodes[node] else "PASS",journal=str(path.relative_to(run)),raw_SHA256=sha(path),**result))
        assert details
        if name.endswith("exclusive-05"):assert not any(d["violations"] for d in details)
        else:assert all(d["violations"] for d in details if d["pytest_result"]=="PASS")
        totals.update(per_run)
        cases.append(dict(run=name,actual_tests=manifest["tests"],wrapper_cases=len(details),counts=dict(per_run),details=details))
    dest=ROOT/"results/lsq-raw-exclusive-05/evidence-auditors"
    dest.mkdir(exist_ok=True)
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(status="OLD_NORMAL_PRODUCER_CLAIMS_REJECTED_S3_METADATA_RELATION_NEW_ENDPOINT05_GATE_ONLY",counts=dict(totals),runs=cases,
                open_source_SHA256=sha(source),auditor_SHA256=sha(Path(__file__)),
                correction="Old mixed pipeline-v1 incorrectly required update_address=True for every S3 and directed/endpoint fixtures inherited default size0/lastBeat0. Prior native PASS/FAIL, original UID effects and raw DA stay unchanged; their timing checks do not suffice for full normal-producer admission. Endpoint05 fixes size3,PA-bit6 and non-completing Replay update0 only; full mixed producer must be repaired separately after regression10 freeze ends.",
                limits="Necessary retained S3 fields only. Aligned no-exception/no-matchInvalid Replay relation is checked; split/error/NC/MMIO writeback must still be audited by their exact source rules. No new RTL fault attribution, old outcome rewriting, native LDU/DCache claim or final goal completion.")
    out=ROOT/"results/lsq-raw-exclusive-05/ldu-s3-source-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="runs"},indent=2,ensure_ascii=False))


if __name__=="__main__":audit()
