#!/usr/bin/env python3
"""Original8 seeds, legitimate serialized CBO packages, all retained failures."""
import argparse
import ast
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_cbo_serialization_v2 import inspect as serialization
from audit_lsq_mixed_history_v4 import inspect as history
from audit_lsq_normal_cbo_v3 import packages
from audit_lsq_population_v1 import paths_by_node
from audit_progress_run_v7 import failures
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name=="lsq-serialized-mixed-01"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"FAIL":8} and len(nodes)==8
    paths=paths_by_node(run)
    failed=failures(run)
    counts,cases,producer=Counter(),[],Counter()
    for seed in range(28928,28936):
        node=next(n for n in paths if n.endswith(f"[{seed}]"))
        path=paths[node]
        assert nodes[node] and "test_serialized_mixed.py::" in node
        legal=serialization(path)
        assert not legal["violations"]
        producer.update(legal["counts"])
        producer["actual_CBO_STA_packages_bound_to_both603_pin_maps"]+=packages(path)
        outer=failed[node] if seed==28928 else None
        if outer is not None:assert "mixed fair drain left original obligations" in outer
        detail=history(path,outer_failure=outer)
        counts.update(detail["counts"])
        if seed==28928:
            assert detail["counts"]["raw_records"]==5611 and detail["counts"]["failed_live"]==18
            assert not detail["independent_terminal_counterexamples"]
            scope="600_random_plus5000_actual_fair_edges_then_outer_liveness_FAIL_not_bad_RTL_pin"
        else:
            assert len(detail["independent_terminal_counterexamples"])==1
            wanted="original_returned_SID_error_until_s1" if seed==28929 else "original_Cache_errors_until_actual_WB_fire"
            assert detail["independent_terminal_counterexamples"][0]["obligation"]==wanted
            scope="SID_original_error_s1_counterexample" if seed==28929 else "Cache_original_error_lost_during_valid_held_WB_before_ready_no_later_fire_fabricated"
        cases.append(dict(nodeid=node,journal=str(path.relative_to(run)),sha256=sha(path),real_producer=legal,
                          observed_failure_scope=scope,actual_JUnit_failure=failed[node],**detail))
    assert counts["raw_records"]==7677 and counts["allocated"]==430==counts["completed"]+counts["cancelled"]+counts["failed_live"]
    assert (counts["completed"],counts["cancelled"],counts["failed_live"])==(214,166,50)
    assert counts["load_bus_fires"]+counts["store_bus_fires"]==69==counts["sid_responses"] and not counts["pending_external_responses"]
    assert producer["CBO_original_owners_identified_from_actual_STA"]==33 and producer["actual_CBO_STA_packages_bound_to_both603_pin_maps"]==34
    assert not producer["NoSpec_prior_ROB_not_empty"] and not producer["BlockBack_younger_admitted_before_CBO_retired_or_cancelled"]
    frozen=run/"verification-source"
    base=ast.parse((frozen/"tests/lsq_wrapper/mixed_owners.py").read_text())
    constants={target.id:ast.literal_eval(n.value) for n in ast.walk(base) if isinstance(n,ast.Assign) for target in n.targets if isinstance(target,ast.Name) and target.id in("KINDS","WEIGHTS")}
    assert constants==dict(KINDS=("cached","nc_load","mmio_load","io_load","store","nc_store","io_store","cbo"),WEIGHTS=(30,12,3,2,36,6,4,7))
    policy=(frozen/"tests/lsq_wrapper/serialized_mixed_owners.py").read_text()
    assert "known-issues" not in policy and "self.planned_kind=kind" in policy and "LSQ_physical_empty_not_required=True" in policy
    command=json.loads((run/"command.json").read_text())["command"]
    assert not any(arg=="-k" or arg.startswith("--deselect") for arg in command)
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    tools=(Path(__file__),ROOT/"tools/audit_lsq_serialized_mixed_v1.py",ROOT/"tools/audit_lsq_cbo_serialization_v2.py",ROOT/"tools/audit_lsq_mixed_history_v4.py",ROOT/"tools/audit_lsq_mixed_history_v2.py")
    for file in tools:
        target=dest/file.name
        if target.exists():assert sha(file)==sha(target)
        else:shutil.copy2(file,target)
    report=dict(run=name,status="eight_source_legal_serialized_CBO_mixed_attempts_independent_original_effects_audited_ALL_FAIL_NOT_FULL_RANDOM_ACCEPTANCE",
                tests=manifest["tests"],snapshot_files=len(source),counts=dict(counts),producer_counts=dict(producer),cases=cases,
                original_eight_type_weights={key:list(value) for key,value in constants.items()},auditors={file.name:sha(dest/file.name) for file in tools},
                limits="All8 original seeds/types/weights retained in source; actual33 CBO owners/34 STA packages satisfy QB/fullmask/wline plus real NoSpec/BlockBack and603 pins. Source uses sticky sampled instruction intent, no CBO resampling/removal; this source review does not invent runtime completion of unadmitted intent. Independent7677 records/430UIDs=214complete+166cancel+50failed-live,39shared recoveries,69accepted bus jobs/69real responses and8returned-unconsumed Load data remain explicit. Six Cache error failures are held-WB visibility, not invented later fires; actual wrong WB.fire separately directed-proven. One SID error and one600+5000 fair-bound failure retained. No fair success, full random acceptance, all cancelled-slot restoration, DUT edits or STRESS checked.")
    report["preserved_v1_report_rejection"]="v1 duplicated terminal_scope while combining its per-case label with the unchanged raw helper's existing terminal_scope, so dict construction raised TypeError. v2 renames only the report label observed_failure_scope; all native evidence/NoSpec/BlockBack/UID/terminal checks stay identical. v1 source retained; no partial report was called complete."
    out=run/"serialized-mixed-audit-v2.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="cases"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
