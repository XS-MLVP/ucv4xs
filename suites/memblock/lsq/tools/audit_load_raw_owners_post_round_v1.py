#!/usr/bin/env python3
"""Increment the RAW-owner evidence graph, retaining the completed old chain."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys

from audit_coverage_points_v1 import sha256_file
from audit_evidence_io import write_report
from audit_load_raw_owners_v1 import FULL,PAIRS

ROOT=Path(__file__).resolve().parents[1]
NAME="lsq-progress-regression-15"
UNIFIED=ROOT/"results"/NAME
INPUT_GUARD=UNIFIED/"load-RAW-owner-integration-input-guard-v1.json"
INDEX_GUARD=UNIFIED/"load-RAW-owner-post-index-guard-v1.json"
CHANGING={f"results/{NAME}/{name}" for name in (
    "gap-closure-summary-v1.json","failure-preservation-audit-v1.json",
    "post-regression-required-gates-v1.json","final-evidence-matrix-v1.json")}


def load(path):return json.loads(path.read_text())


def preserved_version(name,digest):
    path=ROOT/name
    if sha256_file(path)==digest:return name
    archive=path.parent/"audit-history"/f"{path.stem}-{digest}.json"
    assert sha256_file(archive)==digest,(name,digest)
    return str(archive.relative_to(ROOT))


def critical_paths():
    old=load(UNIFIED/"load-response-round-post-audit-v1.json")
    paths=list(old["critical_report_SHA256s"])
    paths.extend(f"results/{after}/load-RAW-owners-evidence-v1.json" for _,_,after in PAIRS)
    paths.append(f"results/{FULL}/load-RAW-owners-contributor-evidence-v1.json")
    paths.append(f"results/{FULL}/replay-exception-payload-boundary-v1.json")
    paths.extend(("results/lq-RAW-owners-after-01/load-RAW-owners-evidence-v1.json",
        "results/lsq-RAW-owners-after-01/load-RAW-owners-evidence-v1.json",
        "results/lsq-RAW-owners-after-01/ROB-source-correction-v1.json",
        "results/load-raw-owners-contributor-regression-01/runner-limitation-v1.json"))
    assert len(paths)==len(set(paths))
    return paths


def protect_inputs():
    if INPUT_GUARD.exists():
        guard=load(INPUT_GUARD)
    else:
        old=load(UNIFIED/"load-response-round-post-audit-v1.json")
        assert all(sha256_file(ROOT/path)==digest for path,digest in old["critical_report_SHA256s"].items())
        raw=load(UNIFIED/"load-RAW-owner-raw-guard-v1.json")["protected_raw_artifact_SHA256s"]
        assert len(raw)==365
        raw=dict(raw)
        runs=["load-raw-owners-probe-03"]+[name for _,before,after in PAIRS for name in (before,after)]+[FULL]
        for name in runs:
            directory=ROOT/"results"/name
            manifest=load(directory/"execution/manifest.json")
            assert manifest["state"]=="committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
            paths=[directory/"execution/manifest.json",directory/"pytest.xml",directory/"command.json",
                directory/"source-aggregate-launch.json",directory/"source-aggregate-end.json"]
            paths.extend(Path(item["path"]) for item in manifest["artifacts"])
            paths.extend((directory/"cases").rglob("load-raw-owner-witness.json"))
            for path in paths:raw[str(path.relative_to(ROOT))]=sha256_file(path)
        cli=ROOT/"results/load-raw-owners-contributor-regression-01"
        for filename in ("command.json","console.log","source-aggregate-launch.json","source-aggregate-end.json"):
            path=cli/filename;raw[str(path.relative_to(ROOT))]=sha256_file(path)
        guard=dict(format="lsq-load-RAW-owner-integration-input-guard-v1",previous_completed_chain="load-response-round-post-audit-v1.json",
            old_report_SHA256s=old["critical_report_SHA256s"],only_planned_index_changes=sorted(CHANGING),
            protected_raw_artifact_SHA256s=dict(sorted(raw.items())),DUT_rerun_required=False)
        write_report(INPUT_GUARD,guard)
    assert all(sha256_file(ROOT/path)==digest for path,digest in guard["protected_raw_artifact_SHA256s"].items())
    preserved={}
    for path,digest in guard["old_report_SHA256s"].items():
        if path in CHANGING:preserved[path]=preserved_version(path,digest)
        else:assert sha256_file(ROOT/path)==digest,path
    return guard,preserved


def audit_index():
    gap=load(UNIFIED/"gap-closure-summary-v1.json")
    failure=load(UNIFIED/"failure-preservation-audit-v1.json")
    gates=load(UNIFIED/"post-regression-required-gates-v1.json")
    matrix=load(UNIFIED/"final-evidence-matrix-v1.json")
    assert len(gap["directed_supplements"])==44 and gap["latest_complete_contributor_run"]["run"]==FULL
    assert gap["full_run_point_classification"]["toggle_missing_points"]==235610
    assert gap["full_run_point_classification"]["branch_missing_points"]==563
    assert gap["full_run_point_classification"]["line_remaining"]=={"load_queue":7,"load_queue_uncache":6,"lsq_wrapper":7}
    assert len(failure["source_checks"])==53
    assert all(not row["contains_skip"] and not row["contains_xfail"] for row in failure["source_checks"].values())
    status=failure["current_load_RAW_owners_eight_build_rerun"]
    assert status["total_cases"]==1569 and status["manifest_tests"]=={"PASS":1377,"FAIL":192}
    assert status["all1457_outcomes_and_failure_details_exactly_equal"]
    assert len(matrix["rows"])==38 and matrix["overall_status"]=="ACTIVE_NOT_ACCEPTED"
    assert matrix["unified_tests"]=={"PASS":2103,"FAIL":227}
    gate=gates["current_required_gates"]
    assert len(gate)==1 and gate[0]["evidence"]==f"results/{FULL}/load-RAW-owners-contributor-evidence-v1.json"
    assert gate[0]["passed"] and gate[0]["required"] and not gate[0]["waived"]
    assert gates["required_new_functional_failures"][0]["outcome"]=="FAIL" and not gates["required_new_functional_failures"][0]["waived"]
    assert len(gates["domain_limited_supplements"])==3 and gates["domain_limited_supplements"][0]["domain"]=="UNIT_INTERFACE_LSQ_CAPACITY"
    assert all(row["historical"] and row["domain"]=="UNIT_INTERFACE_PENDING_JUMP_UNPROVEN_NORMAL_ROB" for row in gates["domain_limited_supplements"][1:])
    return dict(native_builds=38,directed_reports=44,source_checks=53,unified_tests=matrix["unified_tests"],
        latest_tests=status["manifest_tests"],current_required_gate=gate[0],
        required_new_functional_failures=gates["required_new_functional_failures"],
        domain_limited_supplements=gates["domain_limited_supplements"],overall_status="ACTIVE_NOT_ACCEPTED")


def integrate(name):
    assert name==NAME
    guard,_=protect_inputs()
    # Only the new evidence graph and its affected indexes. The old complete
    # chain already audited the other31 immutable reports, protected above.
    for script,args in (("audit_load_raw_owners_v1.py",["--full"]),
        ("audit_gap_closure_summary_v1.py",[name]),("audit_failure_preservation_v1.py",[name])):
        subprocess.run([sys.executable,"-B",str(ROOT/"tools"/script),*args],cwd=ROOT,check=True)
    from audit_post_regression_v1 import finish_index
    gap=load(UNIFIED/"gap-closure-summary-v1.json")
    resolved=[dict(name=row["historical_failed_gate"]["name"],historical_failed_gate=row["historical_failed_gate"],
        current_gate=row["current_gate"],resolution=row["corrected_scope"],current_evidence=row["evidence"]) for row in gap["resolved_runtime_gates"]]
    status=finish_index(name,[],resolved)
    _,preserved=protect_inputs()
    index=audit_index()
    write_report(UNIFIED/"load-RAW-owner-integration-v1.json",dict(format="lsq-load-RAW-owner-integration-v1",
        exitstatus=status,index=index,new_evidence_and_changed_indexes_audited=True,old_historical_chain_reexecuted=False,
        preserved_prior_index_versions=preserved,other31_old_reports_SHA256_equal=True,
        protected_raw_files=len(guard["protected_raw_artifact_SHA256s"]),all_raw_hashes_equal=True,native_DUT_reruns=0,
        limits="A real targeted integration after the recorded35report chain, not a claim that the entire historical chain was rerun. No original native denominator,JUnit,FAIL or coverage dat is rewritten."))
    print(json.dumps(dict(exitstatus=status,index=index,protected_raw_files=len(guard["protected_raw_artifact_SHA256s"])),indent=2))
    return status


def capture():
    guard,preserved=protect_inputs();index=audit_index()
    protected=dict(guard["protected_raw_artifact_SHA256s"])
    for path in (ROOT/"results"/FULL/"whole-runner-receipt.json",
        UNIFIED/"post-regression-load-RAW-owners-01.log",UNIFIED/"load-RAW-owners-integration-receipt-v1.json"):
        protected[str(path.relative_to(ROOT))]=sha256_file(path)
    record=dict(format="lsq-load-RAW-owner-post-index-guard-v1",index=index,preserved_prior_index_versions=preserved,
        critical_report_SHA256s={path:sha256_file(ROOT/path) for path in critical_paths()},
        protected_raw_artifact_SHA256s=dict(sorted(protected.items())),
        archives={str(path.relative_to(ROOT)):sha256_file(path) for path in (ROOT/"results").glob("*/audit-history/*.json")})
    if INDEX_GUARD.exists():assert load(INDEX_GUARD)==record
    else:write_report(INDEX_GUARD,record)
    print(json.dumps(dict(critical_reports=len(record["critical_report_SHA256s"]),protected_raw_files=len(record["protected_raw_artifact_SHA256s"]),index=index),indent=2))
    return record


def audit():
    guard=load(INDEX_GUARD)
    from audit_load_raw_owners_v1 import audit_full
    from audit_gap_closure_summary_v1 import audit as gap_audit
    from audit_failure_preservation_v1 import audit as failure_audit
    from audit_post_regression_v1 import finish_index
    from audit_replay_exception_payload_boundary_v1 import audit as payload_boundary_audit
    with contextlib.redirect_stdout(io.StringIO()):
        audit_full();payload_boundary_audit();gap=gap_audit(NAME);failure_audit(NAME)
        resolved=[dict(name=row["historical_failed_gate"]["name"],historical_failed_gate=row["historical_failed_gate"],
            current_gate=row["current_gate"],resolution=row["corrected_scope"],current_evidence=row["evidence"]) for row in gap["resolved_runtime_gates"]]
        assert finish_index(NAME,[],resolved)==0
    assert audit_index()==guard["index"]
    assert all(sha256_file(ROOT/path)==digest for path,digest in guard["critical_report_SHA256s"].items())
    assert all(sha256_file(ROOT/path)==digest for path,digest in guard["protected_raw_artifact_SHA256s"].items())
    assert {str(path.relative_to(ROOT)):sha256_file(path) for path in (ROOT/"results").glob("*/audit-history/*.json")}==guard["archives"]
    report=dict(format="lsq-load-RAW-owner-round-post-audit-v1",overall_status="ACTIVE_NOT_ACCEPTED",index=guard["index"],
        integration_evidence="results/lsq-progress-regression-15/load-RAW-owner-integration-v1.json",
        critical_report_SHA256s=guard["critical_report_SHA256s"],critical_reports_idempotent=len(guard["critical_report_SHA256s"]),
        protected_raw_artifact_SHA256s=guard["protected_raw_artifact_SHA256s"],protected_raw_files=len(guard["protected_raw_artifact_SHA256s"]),
        preserved_prior_index_versions=guard["preserved_prior_index_versions"],all_raw_hashes_equal=True,
        no_duplicate_archive_on_identical_evidence=True,native_DUT_reruns=0,completion_not_claimed=True,
        limits="New8build evidence,supplemental exact exception-payload source boundary and affected44report/53source/38DUT indexes are actually rebuilt and hash-checked. This is not a second complete historical chain or a new38DUT regression. All192latest and227unified functional failures remain. Source-boundary evidence is not native coverage gain or a removed denominator.")
    write_report(UNIFIED/"load-RAW-owner-round-post-audit-v1.json",report)
    print(json.dumps({key:value for key,value in report.items() if not key.endswith("SHA256s")},indent=2))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--capture",action="store_true");args=parser.parse_args()
    capture() if args.capture else audit()
