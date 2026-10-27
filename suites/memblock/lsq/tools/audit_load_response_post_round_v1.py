#!/usr/bin/env python3
"""Protect raw runs and rebuild the new evidence graph without rerunning DUTs."""
import argparse
import contextlib
import io
import json
from pathlib import Path

from audit_coverage_points_v1 import sha256_file
from audit_evidence_io import write_report
from audit_load_response_payload_v1 import FULL,PAIRS

ROOT=Path(__file__).resolve().parents[1]
UNIFIED=ROOT/"results/lsq-progress-regression-15"
GUARD=UNIFIED/"load-response-post-index-guard-v1.json"


def load(path):return json.loads(path.read_text())


def critical_paths():
    old=load(UNIFIED/"sq-scalar-reservation-round-post-audit-v1.json")
    paths=list(old["critical_report_SHA256s"])
    paths.extend(f"results/{after}/load-response-payload-evidence-v1.json" for _,_,after,_ in PAIRS)
    paths.extend((f"results/{FULL}/load-response-payload-contributor-evidence-v1.json",
        "results/lsq-codec-cache-after-02/runtime-performance-control-v1.json",
        "results/load-response-contributor-baseline-01/load-response-complete-baseline-audit-v1.json"))
    return paths


def audit_index():
    matrix=load(UNIFIED/"final-evidence-matrix-v1.json")
    gap=load(UNIFIED/"gap-closure-summary-v1.json")
    failure=load(UNIFIED/"failure-preservation-audit-v1.json")
    gates=load(UNIFIED/"post-regression-required-gates-v1.json")
    assert len(matrix["rows"])==38 and matrix["overall_status"]=="ACTIVE_NOT_ACCEPTED"
    assert matrix["unified_tests"]=={"PASS":2103,"FAIL":227}
    assert len(gap["directed_supplements"])==42 and gap["latest_complete_contributor_run"]["run"]==FULL
    assert gap["full_run_point_classification"]["toggle_missing_points"]==235610
    assert gap["full_run_point_classification"]["branch_missing_points"]==563
    assert gap["full_run_point_classification"]["line_remaining"]=={"load_queue":7,"load_queue_uncache":6,"lsq_wrapper":7}
    assert failure["current_load_response_eight_build_rerun"]["total_cases"]==1457
    assert failure["current_load_response_eight_build_rerun"]["manifest_tests"]=={"PASS":1265,"FAIL":192}
    assert len(failure["source_checks"])==50 and all(not item["contains_skip"] and not item["contains_xfail"] for item in failure["source_checks"].values())
    current=gates["current_required_gates"]
    assert len(current)==1 and current[0]["passed"] and current[0]["required"] and not current[0]["waived"]
    assert current[0]["evidence"]==f"results/{FULL}/load-response-payload-contributor-evidence-v1.json"
    assert gates["required_new_functional_failures"][0]["outcome"]=="FAIL" and not gates["required_new_functional_failures"][0]["waived"]
    assert matrix["domain_limited_supplements"][0]["domain"]=="UNIT_INTERFACE_LSQ_CAPACITY"
    resume=load(UNIFIED/"load-response-post-chain-resume-v1.json")
    assert resume["previous_chain_exitstatus"]==1 and resume["resumed_exitstatus"]==0
    assert resume["all_prior_evidence_and_raw_hashes_unchanged"] and resume["native_DUT_reruns"]==0
    assert sha256_file(ROOT/resume["previous_failed_log"])==resume["previous_failed_log_SHA256"]
    return dict(native_builds=38,directed_reports=42,source_checks=50,current_required_gate=current[0],
        unified_tests=matrix["unified_tests"],latest_tests={"PASS":1265,"FAIL":192},
        required_new_functional_failures=gates["required_new_functional_failures"],
        domain_limited_supplements=gates["domain_limited_supplements"])


def capture():
    index=audit_index()
    previous=load(UNIFIED/"load-response-raw-artifact-guard-v1.json")
    protected=dict(previous["protected_SHA256s"])
    for name in ("lsq-runtime-profile-01","lsq-codec-cache-unit-01","lsq-codec-cache-baseline-01",
                 "lsq-codec-cache-after-01","lsq-codec-cache-after-02","lsq-codec-cache-baseline-02"):
        root=ROOT/"results"/name
        for path in [root/"execution/manifest.json",root/"pytest.xml"]+list((root/"execution/native").rglob("coverage.dat")):
            protected[str(path.relative_to(ROOT))]=sha256_file(path)
    assert all(sha256_file(ROOT/path)==digest for path,digest in protected.items())
    reports={path:sha256_file(ROOT/path) for path in critical_paths()}
    archives={str(path.relative_to(ROOT)):sha256_file(path) for path in (ROOT/"results").glob("*/audit-history/*.json")}
    record=dict(format="lsq-load-response-post-index-guard-v1",index=index,
        critical_report_SHA256s=reports,protected_raw_artifact_SHA256s=dict(sorted(protected.items())),
        archives=archives,old277_raw_files_unchanged=True)
    if GUARD.exists():assert load(GUARD)==record
    else:write_report(GUARD,record)
    print(json.dumps(dict(index=index,critical_reports=len(reports),protected_raw_files=len(protected)),indent=2))
    return record


def audit():
    guard=load(GUARD)
    # Do not repeat all historical audits or a full native regression solely
    # for idempotence. The preceding full chain audited those immutable inputs.
    from audit_load_response_payload_v1 import audit_full
    from audit_gap_closure_summary_v1 import audit as gap_audit
    from audit_failure_preservation_v1 import audit as failure_audit
    from audit_final_evidence_matrix_v1 import audit as matrix_audit
    from audit_runtime_performance_v1 import audit as performance_audit
    with contextlib.redirect_stdout(io.StringIO()):
        audit_full();gap_audit("lsq-progress-regression-15");failure_audit("lsq-progress-regression-15")
        matrix_audit("lsq-progress-regression-15");performance_audit()
    assert audit_index()==guard["index"]
    assert all(sha256_file(ROOT/path)==digest for path,digest in guard["critical_report_SHA256s"].items())
    assert all(sha256_file(ROOT/path)==digest for path,digest in guard["protected_raw_artifact_SHA256s"].items())
    archives={str(path.relative_to(ROOT)):sha256_file(path) for path in (ROOT/"results").glob("*/audit-history/*.json")}
    assert archives==guard["archives"]
    report=dict(format="lsq-load-response-round-post-audit-v1",overall_status="ACTIVE_NOT_ACCEPTED",
        full_post_regression_log="results/lsq-progress-regression-15/post-regression-load-response-01.log",
        full_post_regression_initial_exitstatus=1,resumed_index_exitstatus=0,
        completed_chain_after_resuming_last_step=True,
        tail_resume_evidence="results/lsq-progress-regression-15/load-response-post-chain-resume-v1.json",
        post_audit_scope="new actual8build evidence,42supplement index,all failure preservation,38DUT matrix and performance controls rebuilt; all35critical reports and prior raw inputs hash-checked. No DUT rerun or second complete historical chain is claimed.",
        index=guard["index"],critical_report_SHA256s=guard["critical_report_SHA256s"],
        critical_reports_idempotent=len(guard["critical_report_SHA256s"]),
        protected_raw_artifact_SHA256s=guard["protected_raw_artifact_SHA256s"],protected_raw_artifact_count=len(guard["protected_raw_artifact_SHA256s"]),
        all_manifest_JUnit_native_dat_hashes_unchanged=True,no_duplicate_archive_on_identical_evidence=True,
        performance_optional_and_not_functional_coverage_gain=True,completion_not_claimed=True)
    write_report(UNIFIED/"load-response-round-post-audit-v1.json",report)
    print(json.dumps({key:value for key,value in report.items() if not key.endswith("SHA256s")},indent=2))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--capture",action="store_true")
    args=parser.parse_args()
    capture() if args.capture else audit()
