#!/usr/bin/env python3
"""Run the locked post-regression coverage/layer/final-index audits."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from audit_evidence_io import write_report

ROOT = Path(__file__).resolve().parents[1]


def run(script: str, name: str, *extra: str) -> None:
    command = [sys.executable, "-B", str(ROOT / "tools" / script), name, *extra]
    subprocess.run(command, cwd=ROOT, check=True)


def audit(name: str) -> int:
    open_gates = []
    resolved_gates = []
    run("coverage_audit.py", name)
    run("audit_coverage_metrics_v1.py", name)
    run("audit_coverage_points_v1.py", name)
    run("audit_coverage_capability_v1.py", name)
    run("audit_line_gap_closure_v1.py", name)
    run("audit_toggle_gap_classification_v1.py", name)
    run("audit_branch_gap_classification_v1.py", name)
    run("audit_initial_branch_boundaries_v1.py", name)
    run("audit_vsq_recovery_boundaries_v1.py", name)
    run("audit_coverage_scope_v1.py", name)
    run("audit_foundation_layer_v1.py", name)
    run("audit_foundation_gaps_v1.py", name)
    run("audit_load_business_layer_v1.py", name)
    run("audit_store_business_layer_v1.py", name)
    run("audit_parent_combinations_v1.py", name)
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_checkpoint_pool_v1.py")], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_store_payload_pool_v1.py")], cwd=ROOT, check=True)
    # Verify the failed historical artifacts with check=True. A generic Python
    # assertion failure must never be mistaken for the known historical gate.
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_store_strict_lifetimes_v1.py"),
                    "--verify-historical-artifacts-only"], cwd=ROOT, check=True)
    report_path = ROOT / "results/store-strict-directory-regression-01/store-strict-regression-evidence-v1.json"
    evidence = json.loads(report_path.read_text())
    assert all(evidence["verification"].values())
    gate = evidence["coverage_monotonicity"]
    assert gate["required"] and not gate["passed"] and not gate["waived"] and gate["newly_missing_toggle_points"] == 2125
    historical_gate = dict(**gate, evidence=str(report_path.relative_to(ROOT)))
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_native_case_probe_v1.py"), "--control",
                    "lsq-native-case-localize-01"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_native_contributor_scope_v1.py")], cwd=ROOT, check=True)
    complete_path = ROOT / "results/store-strict-contributor-regression-02/store-strict-contributor-regression-evidence-v1.json"
    complete = json.loads(complete_path.read_text())
    assert all(complete["verification"].values())
    current_gate = complete["coverage_monotonicity"]
    assert current_gate["required"] and current_gate["passed"] and not current_gate["waived"]
    assert complete["wrapper_original_contributors"] == 730 and complete["wrapper_current_contributors"] == 732
    if historical_gate:
        resolved_gates.append(dict(name=historical_gate["name"], historical_failed_gate=historical_gate,
            current_gate=current_gate, resolution=complete["corrected_scope"],
            current_evidence=str(complete_path.relative_to(ROOT))))
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_store_prefix_byte_v1.py")], cwd=ROOT, check=True)
    latest_path = ROOT / "results/store-prefix-contributor-regression-01/store-prefix-contributor-regression-evidence-v1.json"
    latest = json.loads(latest_path.read_text())
    assert all(latest["verification"].values()) and latest["current_nodes"] == 1072
    current_gate = latest["coverage_monotonicity"]
    assert current_gate["passed"] and current_gate["required"] and not current_gate["waived"]
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_uq_page_pairs_v1.py"), "--full"], cwd=ROOT, check=True)
    uq_path = ROOT / "results/uq-page-contributor-regression-01/uq-page-contributor-regression-evidence-v1.json"
    uq = json.loads(uq_path.read_text())
    assert all(uq["verification"].values()) and uq["current_nodes"] == 1119
    current_gate = uq["coverage_monotonicity"]
    assert current_gate["passed"] and current_gate["required"] and not current_gate["waived"]
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_vsq_release_windows_v1.py"), "--full"], cwd=ROOT, check=True)
    release_path = ROOT / "results/vsq-release-contributor-regression-01/vsq-release-contributor-regression-evidence-v1.json"
    release = json.loads(release_path.read_text())
    assert all(release["verification"].values()) and release["current_nodes"] == 1171
    current_gate = release["coverage_monotonicity"]
    assert current_gate["passed"] and current_gate["required"] and not current_gate["waived"]
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_vsq_release_windows_v1.py"), "--deep"], cwd=ROOT, check=True)
    deep_path = ROOT / "results/vsq-deep-suffix-contributor-regression-01/vsq-deep-suffix-contributor-evidence-v1.json"
    deep = json.loads(deep_path.read_text())
    assert all(deep["verification"].values()) and deep["current_nodes"] == 1172
    current_gate = deep["coverage_monotonicity"]
    assert current_gate["passed"] and current_gate["required"] and not current_gate["waived"]
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_vsq_release_windows_v1.py"), "--batch"], cwd=ROOT, check=True)
    batch_path = ROOT / "results/vsq-retire-batch-contributor-regression-01/vsq-retire-batch-contributor-evidence-v1.json"
    batch = json.loads(batch_path.read_text())
    assert all(batch["verification"].values()) and batch["current_nodes"] == 1173
    current_gate = batch["coverage_monotonicity"]
    assert current_gate["passed"] and current_gate["required"] and not current_gate["waived"]
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_vsq_cancel_capacity_v1.py"), "--full"], cwd=ROOT, check=True)
    cancel_path = ROOT / "results/vsq-cancel-capacity-contributor-regression-01/vsq-cancel-capacity-contributor-evidence-v1.json"
    cancel = json.loads(cancel_path.read_text())
    assert all(cancel["verification"].values()) and cancel["current_nodes"] == 1177
    assert len(cancel["required_new_functional_failures"]) == 1 and cancel["required_new_functional_failures"][0]["outcome"] == "FAIL"
    current_gate = cancel["coverage_monotonicity"]
    assert current_gate["passed"] and current_gate["required"] and not current_gate["waived"]
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_sq_head_permit_domain_v1.py")], cwd=ROOT, check=True)
    head_domain_path = ROOT / "results/vsq-cancel-capacity-contributor-regression-01/sq-head-permit-domain-audit-v1.json"
    head_domain = json.loads(head_domain_path.read_text())
    assert all(head_domain["verification"].values()) and head_domain["native_dynamic_coverage_gain"] == 0
    assert not head_domain["full_upstream_legality_proven"] and not head_domain["failure_waived"]
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_vsq_retire_known_width_v1.py"), "--full"], cwd=ROOT, check=True)
    known_path = ROOT / "results/vsq-retire-known-width-contributor-regression-01/vsq-retire-known-width-contributor-evidence-v1.json"
    known = json.loads(known_path.read_text())
    assert all(known["verification"].values()) and known["current_nodes"] == 1180 and known["original_failures"] == 172
    assert known["required_new_functional_failures"] == cancel["required_new_functional_failures"]
    current_gate = known["coverage_monotonicity"]
    assert current_gate["passed"] and current_gate["required"] and not current_gate["waived"]
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_sq_scalar_reservation_domain_v1.py")], cwd=ROOT, check=True)
    scalar_domain_path = ROOT / "results/vsq-retire-known-width-contributor-regression-01/sq-scalar-reservation-domain-v1.json"
    scalar_domain = json.loads(scalar_domain_path.read_text())
    assert all(scalar_domain["verification"].values()) and not scalar_domain["normal_full_core_producer_proven"]
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_sq_scalar_reservation_pool_v1.py"), "--full"], cwd=ROOT, check=True)
    scalar_path = ROOT / "results/sq-scalar-reservation-contributor-regression-01/sq-scalar-reservation-contributor-evidence-v1.json"
    scalar = json.loads(scalar_path.read_text())
    assert all(scalar["verification"].values()) and scalar["current_nodes"] == 1182 and scalar["original_failures"] == 172
    assert scalar["domain"] == "UNIT_INTERFACE_LSQ_CAPACITY" and not scalar["normal_full_core_producer_proven"]
    current_gate = scalar["coverage_monotonicity"]
    assert current_gate["passed"] and current_gate["required"] and not current_gate["waived"]
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_load_response_payload_v1.py"), "--full"], cwd=ROOT, check=True)
    response_path = ROOT / "results/load-response-contributor-regression-02/load-response-payload-contributor-evidence-v1.json"
    response = json.loads(response_path.read_text())
    assert all(response["verification"].values()) and response["current_nodes"] == 1457 and response["original_failures"] == 192
    assert response["required_new_functional_failures"] == scalar["required_new_functional_failures"]
    current_gate = response["coverage_monotonicity"]
    assert current_gate["passed"] and current_gate["required"] and not current_gate["waived"]
    subprocess.run([sys.executable, "-B", str(ROOT / "tools/audit_load_raw_owners_v1.py"), "--full"], cwd=ROOT, check=True)
    raw_path = ROOT / "results/load-raw-owners-contributor-regression-02/load-RAW-owners-contributor-evidence-v1.json"
    raw = json.loads(raw_path.read_text())
    assert all(raw["verification"].values()) and raw["current_nodes"] == 1569 and raw["original_failures"] == 192
    assert raw["required_new_functional_failures"] == response["required_new_functional_failures"]
    run("audit_gap_closure_summary_v1.py", name)
    run("audit_expanded_regression_v1.py", name)
    run("audit_failure_preservation_v1.py", name)
    return finish_index(name, open_gates, resolved_gates)


def finish_index(name, open_gates, resolved_gates):
    def evidence(run_name, filename):
        path = ROOT / "results" / run_name / filename
        return path, json.loads(path.read_text())
    response_path, response = evidence("load-response-contributor-regression-02", "load-response-payload-contributor-evidence-v1.json")
    raw_path, raw = evidence("load-raw-owners-contributor-regression-02", "load-RAW-owners-contributor-evidence-v1.json")
    scalar_path, scalar = evidence("sq-scalar-reservation-contributor-regression-01", "sq-scalar-reservation-contributor-evidence-v1.json")
    scalar_domain_path, scalar_domain = evidence("vsq-retire-known-width-contributor-regression-01", "sq-scalar-reservation-domain-v1.json")
    known_path, known = evidence("vsq-retire-known-width-contributor-regression-01", "vsq-retire-known-width-contributor-evidence-v1.json")
    release_path, release = evidence("vsq-release-contributor-regression-01", "vsq-release-contributor-regression-evidence-v1.json")
    uq_path, uq = evidence("uq-page-contributor-regression-01", "uq-page-contributor-regression-evidence-v1.json")
    deep_path, deep = evidence("vsq-deep-suffix-contributor-regression-01", "vsq-deep-suffix-contributor-evidence-v1.json")
    batch_path, batch = evidence("vsq-retire-batch-contributor-regression-01", "vsq-retire-batch-contributor-evidence-v1.json")
    cancel_path, cancel = evidence("vsq-cancel-capacity-contributor-regression-01", "vsq-cancel-capacity-contributor-evidence-v1.json")
    latest_path, latest = evidence("store-prefix-contributor-regression-01", "store-prefix-contributor-regression-evidence-v1.json")
    head_domain_path, head_domain = evidence("vsq-cancel-capacity-contributor-regression-01", "sq-head-permit-domain-audit-v1.json")
    for report in (raw, response, scalar, scalar_domain, known, release, uq, deep, batch, cancel, latest, head_domain):
        assert all(report["verification"].values())
    current_gate = raw["coverage_monotonicity"]
    assert current_gate["passed"] and current_gate["required"] and not current_gate["waived"]
    write_report(ROOT / "results" / name / "post-regression-required-gates-v1.json", dict(
        format="lsq-post-regression-required-gates-v1", run=name,
        evidence_checks_completed=True, required_open_gates=open_gates,
        current_required_gates=[dict(**current_gate, evidence=str(raw_path.relative_to(ROOT)))],
        required_new_functional_failures=raw["required_new_functional_failures"],
        domain_limited_supplements=[dict(duts=["store_queue","lsq_wrapper"],domain=scalar["domain"],
            evidence=str(scalar_path.relative_to(ROOT)),source_domain_evidence=str(scalar_domain_path.relative_to(ROOT)),
            normal_full_core_producer_proven=False,global_unreachability_proven=False,
            remaining_boundary=scalar_domain["resource_boundary"])]+[
            dict(duts=[dut],domain="UNIT_INTERFACE_PENDING_JUMP_UNPROVEN_NORMAL_ROB",historical=True,
                evidence=f"results/{run_name}/load-RAW-owners-evidence-v1.json",
                corrected_current_evidence=str(raw_path.relative_to(ROOT)),
                source_domain_evidence="results/lsq-RAW-owners-after-01/ROB-source-correction-v1.json",
                normal_full_core_producer_proven=False,global_unreachability_proven=False,
                remaining_boundary="Historical formal01 advanced pending58 entries in one edge; its original results remain interface-domain evidence, not normal ROB history. Formal02 separately checks bounded commit lines and pendingNext; native upstream ROB remains outside this DUT.")
            for dut,run_name in (("load_queue","lq-RAW-owners-after-01"),("lsq_wrapper","lsq-RAW-owners-after-01"))],
        supplemental_source_triage=[dict(path=str(head_domain_path.relative_to(ROOT)),run=head_domain["run"],
            native_dynamic_coverage_gain=0,full_upstream_legality_proven=False,failure_waived=False,
            verification=head_domain["verification"])],
        prior_current_required_gates=[dict(**response["coverage_monotonicity"], evidence=str(response_path.relative_to(ROOT))),
            dict(**scalar["coverage_monotonicity"], evidence=str(scalar_path.relative_to(ROOT))),
            dict(**known["coverage_monotonicity"], evidence=str(known_path.relative_to(ROOT)))],
        historical_current_required_gates=[dict(**release["coverage_monotonicity"], evidence=str(release_path.relative_to(ROOT))),
            dict(**uq["coverage_monotonicity"], evidence=str(uq_path.relative_to(ROOT))),
            dict(**deep["coverage_monotonicity"], evidence=str(deep_path.relative_to(ROOT))),
            dict(**batch["coverage_monotonicity"], evidence=str(batch_path.relative_to(ROOT))),
            dict(**cancel["coverage_monotonicity"], evidence=str(cancel_path.relative_to(ROOT)))],
        earlier_current_required_gates=[dict(**latest["coverage_monotonicity"], evidence=str(latest_path.relative_to(ROOT)))],
        resolved_runtime_gates=resolved_gates,
        status="OPEN_REQUIRED_GATES" if open_gates else "AUDIT_COMPLETE_NOT_FUNCTIONAL_ACCEPTANCE"))
    run("audit_final_evidence_matrix_v1.py", name)
    return 1 if open_gates else 0


def resume_index(name, failed_log):
    """Narrow recovery of the known final JSON tuple/list comparison failure.

    No simulated subprocess success: rerun the failed audit and final indexes;
    preserve and hash-check all completed evidence and original raw artifacts.
    """
    assert name == "lsq-progress-regression-15"
    log = ROOT / failed_log
    text = log.read_text()
    assert 'assert response_evidence["expected_node_source_relocation"]==response_source_relocation' in text
    assert "audit_failure_preservation_v1.py" in text and "CalledProcessError" in text
    from audit_load_response_payload_v1 import BASELINE, FULL, compare_preexisting_nodes, expected_nodes
    from audit_expanded_regression_v1 import cases
    from audit_coverage_points_v1 import sha256_file
    from audit_load_response_post_round_v1 import critical_paths
    response = json.loads((ROOT / "results" / FULL / "load-response-payload-contributor-evidence-v1.json").read_text())
    assert response["expected_node_source_relocation"] == compare_preexisting_nodes(expected_nodes(), cases(BASELINE))
    raw = json.loads((ROOT / "results" / name / "load-response-raw-artifact-guard-v1.json").read_text())["protected_SHA256s"]
    assert all(sha256_file(ROOT / path) == digest for path, digest in raw.items())
    changing = {f"results/{name}/{filename}" for filename in ("failure-preservation-audit-v1.json", "post-regression-required-gates-v1.json", "final-evidence-matrix-v1.json")}
    prior = {path: sha256_file(ROOT / path) for path in critical_paths() if path not in changing}
    gap = json.loads((ROOT / "results" / name / "gap-closure-summary-v1.json").read_text())
    assert len(gap["directed_supplements"]) == 42 and gap["latest_complete_contributor_run"]["run"] == FULL
    resolved_gates = gap["resolved_runtime_gates"]
    assert len(resolved_gates) == 1
    old = resolved_gates[0]
    resolved = [dict(name=old["historical_failed_gate"]["name"], historical_failed_gate=old["historical_failed_gate"],
        current_gate=old["current_gate"], resolution=old["corrected_scope"], current_evidence=old["evidence"])]
    run("audit_failure_preservation_v1.py", name)
    status = finish_index(name, [], resolved)
    assert all(sha256_file(ROOT / path) == digest for path, digest in raw.items())
    assert all(sha256_file(ROOT / path) == digest for path, digest in prior.items())
    write_report(ROOT / "results" / name / "load-response-post-chain-resume-v1.json", dict(
        format="lsq-post-chain-resume-v1", run=name, previous_chain_exitstatus=1, resumed_exitstatus=status,
        previous_failed_log=failed_log, previous_failed_log_SHA256=sha256_file(log),
        fixed_cause="In-memory sole_diff tuples versus JSON lists; returned evidence is now JSON-canonical. Persisted old JSON, raw results and failure details are unchanged.",
        repeated_only=["audit_failure_preservation_v1.py", "required-gate-index", "audit_final_evidence_matrix_v1.py"],
        prior_report_SHA256s=prior, protected_raw_artifacts=len(raw),
        all_prior_evidence_and_raw_hashes_unchanged=True, native_DUT_reruns=0,
        limits="This is a real resumed tail after the recorded first exit1, not a second full chain or a hidden successful rewrite of the failed log."))
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--resume-index-after", help="resume only the known final tuple/list audit failure from its retained log")
    parser.add_argument("--raw-owners-index-only", action="store_true", help="audit the new RAW evidence and update indexes while hash-protecting the already completed historical chain; no DUT execution")
    parser.add_argument("--normal-replay-index-only", action="store_true", help="audit the normal scalar Replay nine-build evidence and current indexes without rerunning DUTs or the completed old chain")
    parser.add_argument("--replay-cause-index-only", action="store_true", help="audit the repeated Replay cause lifetimes and current50-report index; no DUT or old-chain rerun")
    args = parser.parse_args()
    assert sum(bool(value) for value in (args.resume_index_after, args.raw_owners_index_only, args.normal_replay_index_only, args.replay_cause_index_only)) <= 1
    if args.replay_cause_index_only:
        assert args.name == "lsq-progress-regression-15"
        from audit_replay_cause_post_round_v1 import integrate
        result = integrate()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit(result["exitstatus"])
    if (ROOT / "results" / args.name / "Replay-cause-integration-input-guard-v1.json").exists():
        parser.error("Replay cause evidence is already staged or integrated; use --replay-cause-index-only to preserve the current50-report graph instead of rebuilding an older index")
    if args.normal_replay_index_only:
        assert args.name == "lsq-progress-regression-15"
        from audit_normal_replay_post_round_v1 import integrate
        result = integrate()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit(result["exitstatus"])
    if (ROOT / "results" / args.name / "normal-replay-integration-input-guard-v1.json").exists():
        parser.error("normal Replay evidence is already integrated; use --normal-replay-index-only to preserve the current47-report index instead of rebuilding the older44-report graph")
    if args.raw_owners_index_only:
        from audit_load_raw_owners_post_round_v1 import integrate
        raise SystemExit(integrate(args.name))
    raise SystemExit(resume_index(args.name, args.resume_index_after) if args.resume_index_after else audit(args.name))
