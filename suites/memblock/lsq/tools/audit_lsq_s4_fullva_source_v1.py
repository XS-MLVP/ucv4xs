#!/usr/bin/env python3
"""Old S3 three-field gate did not check S4's tail-selected fullva.

Public S0 head/tail and final S4 input low page offsets suffice to prove this
necessary source relation. No unrecorded TLB high-address/GPAddr value invented.
"""
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_population_v1 import events, paths_by_node
from audit_sq_initial import ROOT, sha, verify_common


def inspect(path):
    rows=list(events(path))
    counts=Counter()
    violations=[]
    for index,row in enumerate(rows):
        for lane,p in enumerate(row["input"]["loads"]):
            q=p["execution"]
            if not q["valid"] or q["aligned_type"]!=4 or q["uop"]["operation"]!=6:continue
            assert index>=4
            head=rows[index-4]["input"]["queries"][lane]
            tail=rows[index-3]["input"]["queries"][lane]
            assert head["valid"] and tail["valid"] and head["size"]==3 and tail["size"]==4
            assert head["vaddr"]%16==12 and tail["vaddr"]==head["vaddr"]//16*16+16
            assert q["vaddr"]==head["vaddr"] and head["sq"]==tail["sq"]==q["uop"]["sq"]
            assert not p["exceptions"],"old random S4 was no-error; split exception input source needs separate evidence"
            counts["actual_no_exception_S4_joins"]+=1
            if p["fullva"]%4096!=tail["vaddr"]%4096:
                violations.append(dict(tick=row["post_tick"],lane=lane,original_ROB=q["uop"]["rob"],original_LQ=q["uop"]["lq"],
                                       head_S0_tick=rows[index-4]["post_tick"],tail_S0_tick=rows[index-3]["post_tick"],
                                       head_VA=head["vaddr"],tail_VA=tail["vaddr"],actual_final_fullva=p["fullva"],
                                       expected_fullva_page_offset=tail["vaddr"]%4096,
                                       source="NewLoadUnit1437,1574: no head exception selects tail fullva, even if no final exception"))
    counts["S4_tail_fullva_low_offset_violations"]=len(violations)
    return dict(counts=dict(counts),violations=violations)


def audit():
    results=[]
    for name in ("lsq-ldu-mixed-02","lsq-ldu-s3-01"):
        run=ROOT/"results"/name
        manifest,source,_=verify_common(run)
        cases=[]
        totals=Counter()
        for node,path in sorted(paths_by_node(run).items()):
            if "mixed.py" not in node:continue
            detail=inspect(path)
            totals.update(detail["counts"])
            cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),raw_SHA256=sha(path),**detail))
        assert totals["actual_no_exception_S4_joins"]==totals["S4_tail_fullva_low_offset_violations"]==18
        results.append(dict(run=name,actual_tests=manifest["tests"],snapshot_files=len(source),counts=dict(totals),cases=cases))
    target_run=ROOT/"results/lsq-ldu-s3-01"
    dest=target_run/"evidence-auditors"
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(status="OLD_THREE_S3_FIELDS_STILL_INSUFFICIENT_FOR_NORMAL_S4_FULLVA_ADMISSION",runs=results,auditor_SHA256=sha(Path(__file__)),
                limits="Only necessary fullva low-page-offset relation is proven violated; unrecorded TLB GPAddr/nonleaf/high fullva not reconstructed or claimed checked. All old output effects/UIDs/ordinary FAILs/native DA remain real. Old18 no-error S4 joins cannot pass full source admission merely because size/lastBeat/update gate passed. New dedicated S4 inputs and unchanged8-kind-seed reruns are required; not native LDU proof or whole-goal signoff.")
    out=target_run/"s4-fullva-source-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:([dict(run=r['run'],counts=r['counts']) for r in v] if k=='runs' else v) for k,v in report.items()},indent=2,ensure_ascii=False))


if __name__=="__main__":audit()
