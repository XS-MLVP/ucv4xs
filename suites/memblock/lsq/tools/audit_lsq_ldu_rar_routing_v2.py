#!/usr/bin/env python3
"""Third normal LDU iteration: 3 complete full-pool programs and real bins.

Preserves the frozen first two raw/semantic audits; never upgrades summaries
to checked. Original15 cases and rotation0 must have identical public history.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_ldu_rar_routing_v1 import inspect
from audit_lsq_population_v1 import paths_by_node, same_raw
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name=="lsq-ldu-rar-routing-03"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":15,"FAIL":3} and len(nodes)==18
    prior=ROOT/"results/lsq-ldu-rar-routing-02"
    old_manifest,old_source,old_nodes=verify_common(prior)
    assert old_manifest["tests"]=={"PASS":13,"FAIL":3}
    assert {k:v for k,v in source.items() if k.startswith("lsqverify/")}=={k:v for k,v in old_source.items() if k.startswith("lsqverify/")}
    paths,old_paths=paths_by_node(run),paths_by_node(prior)
    assert set(paths)==set(nodes)
    mappings=[]
    for node,path in sorted(old_paths.items()):
        new=node+"[0]" if "full_96_RAR" in node else node
        assert nodes[new]==old_nodes[node]
        mappings.append(dict(prior_node=node,current_node=new,public_records_equal=same_raw(path,paths[new])))
    counts,cases=Counter(),[]
    for node,path in sorted(paths.items()):
        result=inspect(path,nodes[node])
        counts.update(result["counts"])
        if "full_96_RAR" in node:
            assert not nodes[node] and result["peak_public_RAR_ownership"]==96 and result["counts"]["completed"]==97
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),pytest_result="FAIL" if nodes[node] else "PASS",**result))
    assert counts["original_RAR_flushAfter"]==counts["same_physical_slot_new_UID_completion"]==3
    assert counts["C_NK_bound_to_real_older_concurrent_STA"]==counts["original_Store_Sbuffer_consumptions"]==3
    assert counts["actual_original_replay_grants"]==counts["original_slot_S3_feedbacks"]==6
    assert counts["allocated"]==324 and counts["completed"]==315 and counts["cancelled"]==3 and counts["failed_retained"]==6
    fc=json.loads((run/"line-audit.json").read_text())["functional"]
    checked=next(g for g in fc if g["instance"]=="lsq.lsq_wrapper.checked")
    reached=next(g for g in fc if g["instance"]=="lsq.lsq_wrapper.reached")
    contract=(run/"verification-source/docs/contracts/lsq-wrapper.md").read_text()
    catalog=set()
    for line in contract.splitlines():
        if line.startswith("| LSQ-"):
            _,group,parts,*_=line.split("|")
            catalog.update(group.strip()+"."+part.strip() for part in parts.split("/"))
    expected={"LSQ-RAR.current_release","LSQ-RAR.revoke","LSQ-RAR.head_reclaim","LSQ-RECOVER.partial","LSQ-RECOVER.sent_load", 
              "LSQ-RECOVER.reuse","LSQ-RETIRE.ordinary","LSQ-RETIRE.rob_before_sbuffer"}
    assert len(catalog)==82 and catalog-set(checked["missing"])==expected and checked["hit"]==8
    assert catalog-set(reached["missing"])==expected|{"LSQ-RAR.previous_release"} and reached["hit"]==9
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    auditor_hashes={}
    for file in(Path(__file__),Path(__file__).with_name("audit_lsq_ldu_rar_routing_v1.py")):
        copy=dest/file.name
        if copy.exists():assert sha(copy)==sha(file)
        else:shutil.copy2(file,copy)
        auditor_hashes[file.name]=sha(file)
    report=dict(run=name,status="NORMAL_LDU_3_FULL_POOL_PROGRAMS_ORIGINAL_RECOVERY_NATIVE_BINS_AUDITED_RETAIN_3_FAILS",tests=manifest["tests"],
                snapshot_files=len(source),counts=dict(counts),cases=cases,prior=prior.name,prior_to_current_exact_public_mappings=mappings,
                normal_subset_reached=9,normal_subset_checked=8,scenario_denominator_unchanged=82,
                full_pool_original_UIDs_completed=291,auditors=auditor_hashes,
                limits="Original15 cases and complete rotation0 public records unchanged from iteration02. Three independent 96-younger-reader programs all complete97 original Loads; no private RAR slot is used as oracle. Only8 actually marked scenarios checked; previous_release stays reached-only and ordinary FAIL. This is not full Wrapper capacity, full8-seed random, old-stream normal admission or goal completion. RTL/reference/knownness/masks unchanged.")
    out=run/"ldu-rar-routing-audit-v2.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in("cases","prior_to_current_exact_public_mappings")},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
