#!/usr/bin/env python3
"""New normal subset: bind package metadata to603 actual pins and original effects."""
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import shutil

from audit_lsq_joint_history_v4 import JointAudit
from audit_lsq_mixed_history_v2 import inspect as inspect_mixed
from audit_lsq_population_v1 import RAW, events, paths_by_node, same_raw
from audit_lsq_remaining_history_v1 import inspect_cbo
from audit_progress_run_v7 import failures
from audit_sq_initial import ROOT, sha, verify_common


def packages(path):
    count=0
    for row in events(path):
        for lane,a in enumerate(row["input"]["addresses"]):
            if not a["valid"] or not a["fu_op"]&1:continue
            assert (a["size"],a["mask"],bool(a["wline"]),a["vaddr"]%16,a["paddr"]%16)==(4,65535,True,0,0), "normal CBO metadata"
            p=f"io_sta_storeAddrIn_{lane}_"
            for pins in (row["pins"],row["post_pins"]):
                assert pins[p+"valid"]
                for field,value in (("size",4),("mask",65535),("wlineflag",1),("paddr",a["paddr"]),("vaddr",a["vaddr"]),("uop_fuOpType",a["fu_op"])):
                    assert pins[p+"bits_"+field]==value, "CBO SQ/RAW package must match actual driven pins"
            count+=1
    return count


def prefix(first,second):
    count=0
    for a,b in itertools.zip_longest(events(first),events(second)):
        if a is None:break
        assert b is not None and all(a[k]==b[k] for k in RAW), (first,second,count)
        count+=1
    return count


def audit(name):
    assert name=="lsq-normal-cbo-02"
    run,prior=ROOT/"results"/name,ROOT/"results/lsq-normal-cbo-01"
    manifest,source,nodes=verify_common(run)
    old,_,old_nodes=verify_common(prior)
    assert len(nodes)==28 and old["tests"]=={"PASS":6,"FAIL":8}
    paths,previous=paths_by_node(run),paths_by_node(prior)
    counts,cases,visits=Counter(),[],set()
    old_failure,new_failure=failures(prior),failures(run)
    groups=Counter()
    for node,path in sorted(paths.items()):
        metadata=packages(path)
        counts["actual_CBO_STA_bound_to_both603_pin_maps"]+=metadata
        if "::test_normal_cbo_joint_" in node:
            assert not nodes[node]
            a=JointAudit()
            for row in events(path):a.step(row)
            detail=a.finish()
            assert same_raw(previous[node],path)==a.counts["raw_records"]
            counts.update(a.counts)
            groups["joint_complete"]+=1
            detail["prior_normal01_complete_actual_history_equal"]=True
        elif "::test_normal_cbo_full_domain_" in node:
            assert nodes[node] and old_nodes[node]
            detail=inspect_mixed(path)
            detail["normal01_actual_prefix_equal_records"]=prefix(previous[node],path)
            if not node.endswith("[28934]"):
                assert same_raw(previous[node],path)==detail["counts"]["raw_records"]
                assert new_failure[node]==old_failure[node]
            else:
                assert "outside documented SQ age domain" in old_failure[node] and "outside documented SQ age domain" not in new_failure[node]
                assert detail["counts"]["raw_records"]>detail["normal01_actual_prefix_equal_records"]
            groups["mixed_first_FAIL_retained"]+=1
        elif "test_normal_cbo_paths.py::" in node:
            assert not nodes[node] and metadata==256
            detail=inspect_cbo(path)
            visits.update(tuple(v) for v in detail["completed_slot_cbo_sta_witnesses"])
            groups["normal_CBO_all_slots_complete"]+=1
        else:
            assert "test_sq_age_endpoint.py::" in node and not nodes[node] and not metadata
            detail=dict(scope="independently audited by sq-endpoint-audit-v1.json, not counted as CBO effects")
            groups["endpoint_complete"]+=1
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),normal_CBO_STA=metadata,
                          pytest_result="FAIL" if nodes[node] else "PASS",detail=detail))
    assert groups==Counter(joint_complete=6,mixed_first_FAIL_retained=8,normal_CBO_all_slots_complete=2,endpoint_complete=12)
    assert visits=={(slot,cbo,lane) for slot in range(64) for cbo in range(4) for lane in range(2)}
    assert counts["allocated"]==5456 and counts["completed"]==4464 and counts["same_physical_slot_new_uid_complete"]==992
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files=(Path(__file__),ROOT/"tools/audit_lsq_joint_history_v4.py",ROOT/"tools/audit_lsq_remaining_history_v1.py",ROOT/"tools/audit_lsq_mixed_history_v2.py")
    for file in files:
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
    report=dict(run=name,status="NEW28_normal_CBO_pin_metadata_joint_original_effects_all512_CBO_slots_and_mixed_failure_prefixes_audited_NOT_PASS",
                tests=manifest["tests"],snapshot_files=len(source),groups=dict(groups),joint_counts_and_CBO_packages=dict(counts),
                completed_normal_CBO_slot_opcode_STA_combinations=len(visits),cases=cases,
                auditors={file.name:sha(dest/file.name) for file in files},
                limits="No source/model/actor/known-issue answers. All real CBO metadata explicitly agrees with both raw603-pin maps. Six normal joint cases retain complete actual histories from01; seven normal mixed FAIL histories/signatures unchanged, exact128 old reference rejection is an actual prefix of new later failure.512 normal all-slot CBOs+512 associated original Loads complete, including384 Cache responses and128 full16B zero transfers with512 WB fires. Endpoint12 have a separate original-effect audit. Original size3 interface histories are not retroactively normal. Full random/STRESS/late-local-reset-response/Backend/ISA signoff is NOT granted.")
    out=run/"normal-cbo-audit-v3.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
