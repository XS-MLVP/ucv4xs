#!/usr/bin/env python3
"""Integrate verified nine-build evidence into the protected38DUT matrix."""
import argparse
import contextlib
import io
import json
from pathlib import Path

from audit_coverage_points_v1 import sha256_file
from audit_evidence_io import write_report
from audit_expanded_regression_v1 import cases, failure_digest
from audit_failure_preservation_v1 import pytest_status
from audit_final_evidence_matrix_v1 import audit as matrix_audit
from audit_normal_replay_metadata_v1 import FULL, PRIOR, REPLAY_BASE, PAIRS, FILES, audit_full, audit_pair
from audit_normal_replay_remaining_v1 import audit as remaining_audit

ROOT = Path(__file__).resolve().parents[1]
NAME = "lsq-progress-regression-15"
UNIFIED = ROOT / "results" / NAME
INPUT = UNIFIED / "normal-replay-integration-input-guard-v1.json"
POST = UNIFIED / "normal-replay-post-index-guard-v1.json"
CHANGING = {f"results/{NAME}/{name}" for name in (
    "gap-closure-summary-v1.json", "failure-preservation-audit-v1.json",
    "post-regression-required-gates-v1.json", "final-evidence-matrix-v1.json")}


def load(path):
    return json.loads(path.read_text())


def old_version(name, digest):
    path = ROOT / name
    if sha256_file(path) == digest:
        return path
    archive = path.parent / "audit-history" / f"{path.stem}-{digest}.json"
    assert sha256_file(archive) == digest
    return archive


def protect():
    if INPUT.exists():
        guard = load(INPUT)
    else:
        prior = load(UNIFIED / "normal-replay-pre-integration-guard-v1.json")
        assert all(sha256_file(ROOT / path) == digest for path, digest in prior["old43_report_SHA256s"].items())
        raw = dict(prior["protected_raw_artifact_SHA256s"])
        runs = ["normal-replay-metadata-probe-01", "normal-replay-metadata-probe-02", REPLAY_BASE, FULL]
        runs += [name for _, before, after in PAIRS for name in (before, after)]
        runs += [f"{prefix}-normal-metadata-{kind}-01" for prefix in ("lrq", "lq", "lsq") for kind in ("baseline", "after")]
        for name in runs:
            directory = ROOT / "results" / name
            manifest = load(directory / "execution/manifest.json")
            assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
            paths = [directory / "execution/manifest.json", directory / "pytest.xml", directory / "command.json", directory / "console.log",
                directory / "source-aggregate-launch.json", directory / "source-aggregate-end.json"]
            paths += [Path(artifact["path"]) for artifact in manifest["artifacts"]]
            paths += list((directory / "cases").rglob("normal-replay-metadata-witness.json"))
            for path in paths:
                raw[str(path.relative_to(ROOT))] = sha256_file(path)
        for path in (ROOT / "results" / FULL / "whole-runner-receipt.json",
            ROOT / "results" / REPLAY_BASE / "first-baseline-audit-failure.log"):
            raw[str(path.relative_to(ROOT))] = sha256_file(path)
        guard = dict(format="lsq-normal-replay-integration-input-guard-v1",
            old_report_SHA256s=prior["old43_report_SHA256s"], protected_raw_artifact_SHA256s=dict(sorted(raw.items())),
            only_four_prior_index_paths_change=sorted(CHANGING), no_DUT_rerun=True)
        write_report(INPUT, guard)
    assert all(sha256_file(ROOT / path) == digest for path, digest in guard["protected_raw_artifact_SHA256s"].items())
    for path, digest in guard["old_report_SHA256s"].items():
        if path in CHANGING:
            old_version(path, digest)
        else:
            assert sha256_file(ROOT / path) == digest
    return guard


def baseline_index(guard, filename):
    name = f"results/{NAME}/{filename}"
    return load(old_version(name, guard["old_report_SHA256s"][name]))


def rebuild_indexes(guard):
    full_path = ROOT / "results" / FULL / "normal-replay-metadata-contributor-evidence-v1.json"
    full = load(full_path)
    assert all(full["verification"].values()) and full["current_nodes"] == 1762
    assert full["status"]["manifest_tests"] == {"PASS": 1566, "FAIL": 196}
    manifest = load(ROOT / "results" / FULL / "execution/manifest.json")
    native = [item for item in manifest["artifacts"] if item["kind"] == "native"]
    assert len(native) == len(full["rows"]) == 9
    assert {item["build"]["build_id"] for item in native} == {row["native_build_id"] for row in full["rows"]}
    gate = full["coverage_monotonicity"]
    assert gate["passed"] and gate["required"] and not gate["waived"]
    before = dict(cases(PRIOR), **cases(REPLAY_BASE))
    after = cases(FULL)
    assert len(before) == 1750 and len(after) == 1762
    assert all(after[node] == value for node, value in before.items())
    assert failure_digest(before) == failure_digest(after) == full["current_failure_SHA256"]
    gap = baseline_index(guard, "gap-closure-summary-v1.json")
    original = json.loads(json.dumps(gap["directed_supplements"]))
    assert len(original) == 44
    for dut, _, run in PAIRS:
        directory = ROOT / "results" / run
        closure_path = directory / f"directed-gap-closure-{dut}-v1.json"
        closure = load(closure_path)
        evidence_path = directory / "normal-replay-metadata-evidence-v1.json"
        evidence = load(evidence_path)
        assert all(closure["verification"].values()) and all(evidence["verification"].values())
        row = next(row for row in full["rows"] if row["dut"] == dut)
        gap["directed_supplements"].append(dict(path=str(closure_path.relative_to(ROOT)),
            **{key: closure[key] for key in ("dut", "feature_id", "case_id", "before_run", "after_run", "native_build_id", "metrics", "functional_before", "functional_after", "verification")},
            normal_scalar_replay_evidence=dict(path=str(evidence_path.relative_to(ROOT)), contract=evidence["contract"],
                baseline_tests=evidence["baseline_tests"], after_tests=evidence["after_tests"], target_domains=evidence["target_domains"],
                producer_source=evidence["producer_source"], calibration=evidence["calibration"], semantic_limit=evidence["limits"]),
            actual_complete_nine_build_rerun=dict(path=str(full_path.relative_to(ROOT)), run=FULL,
                tests=full["status"]["manifest_tests"], baseline_nodes=1750, current_nodes=1762, added_passing_nodes=12,
                old_failures=196, native_builds=9, metrics=row["metrics"], target_domains=row["target_domains"],
                original_source_line_coverage=row["original_source_line_coverage"],
                original_native_inputs=row["original_native_inputs"], current_native_inputs=row["current_native_inputs"],
                coverage_monotonicity=gate, verification=full["verification"])))
    assert gap["directed_supplements"][:44] == original and len(gap["directed_supplements"]) == 47
    gap["prior_complete_contributor_runs"].append(gap["latest_complete_contributor_run"])
    gap["latest_complete_contributor_run"] = dict(path=str(full_path.relative_to(ROOT)), run=FULL, native_builds=9,
        tests=full["status"]["manifest_tests"], baseline_run=PRIOR, baseline_Replay_run=REPLAY_BASE,
        baseline_nodes=1750, current_nodes=1762, baseline_is_two_actual_disjoint_node_contexts_not_coverage_OR=True,
        coverage_monotonicity=gate)
    gap["normal_replay_source_and_scope_corrections"] = full["calibration"]
    remaining_path = ROOT / "results" / FULL / "remaining-gap-selection-v1.json"
    remaining = load(remaining_path)
    assert all(remaining["verification"].values()) and len(remaining["rows"]) == 9
    gap["current_nine_build_remaining_inventory"] = dict(path=str(remaining_path.relative_to(ROOT)),
        SHA256=sha256_file(remaining_path), unified_classification_changed=False,
        metrics={row["dut"]: row["metrics"] for row in remaining["rows"]}, next_contract_or_tests_created=False)
    gap["status"] = "47 independent directed reports retained; latest actual9build run preserves196prior failures and all native hits. Unified38DUT coverage and227FAIL inventory remain unchanged; whole-LSQ acceptance is open."
    write_report(UNIFIED / "gap-closure-summary-v1.json", gap)

    failure = baseline_index(guard, "failure-preservation-audit-v1.json")
    for _, _, run in PAIRS:
        status = pytest_status(run)
        assert status["failures"] == status["errors"] == status["skipped"] == 0 and status["pytest_exitstatus"] == 0
        failure["directed_supplement_runs"].append(status)
    for name in ("lsqverify/normal_replay_metadata.py", *FILES.values(), "tests/normal_replay_probe/test_probe.py"):
        path = ROOT / name
        text = path.read_text()
        checked = dict(SHA256=sha256_file(path), contains_skip="skip" in text.lower(), contains_xfail="xfail" in text.lower())
        assert not checked["contains_skip"] and not checked["contains_xfail"]
        assert name not in failure["source_checks"]
        failure["source_checks"][name] = checked
    assert len(failure["source_checks"]) == 58
    failure["current_normal_replay_nine_build_rerun"] = dict(**full["status"], baseline_eight_build=PRIOR,
        baseline_Replay=REPLAY_BASE, baseline_nodes=1750, current_nodes=1762, added_passing_nodes=12,
        original_failures=196, current_failure_SHA256=failure_digest(after), original_failure_SHA256=failure_digest(before),
        prior192_and4newly_included_preexisting_ReplayFAILs_not_new_failures=True,
        all1750_old_outcomes_and_primary_failure_details_equal=True, calibration=full["calibration"],
        coverage_monotonicity=gate, evidence=str(full_path.relative_to(ROOT)),
        original_required_functional_failures=full["required_new_functional_failures"])
    write_report(UNIFIED / "failure-preservation-audit-v1.json", failure)

    gates = baseline_index(guard, "post-regression-required-gates-v1.json")
    gates["prior_current_required_gates"] = gates["current_required_gates"] + gates["prior_current_required_gates"]
    gates["current_required_gates"] = [dict(**gate, evidence=str(full_path.relative_to(ROOT)))]
    assert gates["required_new_functional_failures"] == full["required_new_functional_failures"]
    for row in full["calibration"]["historical_interface_domain_runs"]:
        gates["domain_limited_supplements"].append(dict(duts=[load(ROOT / row["evidence"])["dut"]],
            domain=row["domain"], historical=True, evidence=row["evidence"],
            corrected_current_evidence=str(full_path.relative_to(ROOT)),
            source_domain_evidence=full["calibration"]["FTQ_source_correction"],
            normal_full_core_producer_proven=False, global_unreachability_proven=False,
            remaining_boundary="Historical01used16B/start-offset tags; keep functional LSQ interface evidence. Corrected02uses fixed64B blocks and ending-halfword offsets; native upstream Frontend remains outside this DUT."))
    padding = ROOT / "results" / REPLAY_BASE / "ID-padding-source-boundary-v1.json"
    pad = load(padding)
    assert all(pad["verification"].values()) and pad["native_dynamic_coverage_gain"] == 0
    gates["supplemental_source_triage"].append(dict(path=str(padding.relative_to(ROOT)),
        run=FULL, native_dynamic_coverage_gain=0, full_upstream_legality_proven=False, failure_waived=False,
        classification=pad["classification"], verification=pad["verification"]))
    gates["supplemental_source_triage"].append(dict(path=str(remaining_path.relative_to(ROOT)),
        run=FULL, native_dynamic_coverage_gain=0, full_upstream_legality_proven=False, failure_waived=False,
        classification="COMBINATIONAL_ZERO_EXTENSION_VA50_TO_FULLVA64",
        exact_fullva_constant_boundaries=remaining["exact_fullva_constant_boundaries"],
        original_classification_denominators_changed=False, verification=remaining["verification"]))
    write_report(UNIFIED / "post-regression-required-gates-v1.json", gates)
    matrix = matrix_audit(NAME)
    assert len(matrix["rows"]) == 38 and matrix["overall_status"] == "ACTIVE_NOT_ACCEPTED"
    assert matrix["unified_tests"] == {"PASS": 2103, "FAIL": 227}
    return dict(native_builds=38, independent_directed_reports=47, source_checks=58,
        latest_native_builds=9, latest_tests=full["status"]["manifest_tests"], unified_tests=matrix["unified_tests"],
        current_required_gate=gates["current_required_gates"][0], required_new_functional_failures=gates["required_new_functional_failures"],
        overall_status="ACTIVE_NOT_ACCEPTED")


def critical_paths(guard):
    result = list(guard["old_report_SHA256s"])
    result += [f"results/{after}/normal-replay-metadata-evidence-v1.json" for _, _, after in PAIRS]
    result += [f"results/{after}/directed-gap-closure-{dut}-v1.json" for dut, _, after in PAIRS]
    result += [f"results/{FULL}/normal-replay-metadata-contributor-evidence-v1.json",
        f"results/{REPLAY_BASE}/normal-replay-complete-baseline-v1.json", f"results/{REPLAY_BASE}/ID-padding-source-boundary-v1.json",
        f"results/{REPLAY_BASE}/baseline-scope-correction-v1.json",
        "results/normal-replay-metadata-probe-01/FTQ-source-projection-correction-v1.json"]
    result += [f"results/{prefix}-normal-metadata-after-01/normal-replay-metadata-evidence-v1.json" for prefix in ("lrq", "lq", "lsq")]
    result += [f"results/{NAME}/normal-replay-integration-v1.json",
        f"results/{REPLAY_BASE}/next-vsq-release-wait-local-lemma-v1.json",
        f"results/{FULL}/remaining-gap-selection-v1.json",
        "results/normal-replay-metadata-probe-02/frozen-before-contributor-union-v1.json"]
    assert len(result) == len(set(result))
    return result


def integrate():
    guard = protect()
    full = audit_full()
    remaining_audit()
    index = rebuild_indexes(guard)
    protect()
    preserved = {name: str(old_version(name, digest).relative_to(ROOT)) for name, digest in guard["old_report_SHA256s"].items() if name in CHANGING}
    report = dict(format="lsq-normal-replay-integration-v1", index=index, exitstatus=0, native_DUT_reruns=0,
        old_evidence_graph_reexecuted=False, all39_unchanged_prior_reports_SHA256_equal=True,
        four_changed_indexes_prior_versions=preserved,
        protected_raw_files=len(guard["protected_raw_artifact_SHA256s"]), all_raw_hashes_equal=True,
        latest_failure_SHA256=full["current_failure_SHA256"],
        limits="Only the new9build evidence,disjoint baseline scope and affected indexes are rebuilt. No earlier DUT run or entire historical post-chain is repeated; no directed point is credited into unified38DUT coverage.")
    write_report(UNIFIED / "normal-replay-integration-v1.json", report)
    return report


def capture():
    guard = protect()
    index = load(UNIFIED / "normal-replay-integration-v1.json")["index"]
    raw = dict(guard["protected_raw_artifact_SHA256s"])
    for path in (UNIFIED / "post-regression-normal-replay-01.log", UNIFIED / "normal-replay-integration-receipt-v1.json",
        UNIFIED / "normal-replay-old-entrypoint-scope-guard.log", UNIFIED / "post-regression-normal-replay-index-02.log",
        UNIFIED / "normal-replay-entrypoint-receipt-v1.json"):
        raw[str(path.relative_to(ROOT))] = sha256_file(path)
    record = dict(format="lsq-normal-replay-post-index-guard-v1", index=index,
        critical_report_SHA256s={name: sha256_file(ROOT / name) for name in critical_paths(guard)},
        protected_raw_artifact_SHA256s=dict(sorted(raw.items())),
        archives={str(path.relative_to(ROOT)): sha256_file(path) for path in (ROOT / "results").glob("*/audit-history/*.json")})
    if POST.exists():
        assert load(POST) == record
    else:
        write_report(POST, record)
    return record


def audit():
    guard = load(POST)
    with contextlib.redirect_stdout(io.StringIO()):
        for pair in PAIRS:
            audit_pair(*pair)
        from audit_vsq_release_wait_local_lemma_v1 import audit as local_lemma_audit
        local_lemma_audit()
        result = integrate()
    assert result["index"] == guard["index"]
    assert all(sha256_file(ROOT / name) == digest for name, digest in guard["critical_report_SHA256s"].items())
    assert all(sha256_file(ROOT / name) == digest for name, digest in guard["protected_raw_artifact_SHA256s"].items())
    assert {str(path.relative_to(ROOT)): sha256_file(path) for path in (ROOT / "results").glob("*/audit-history/*.json")} == guard["archives"]
    report = dict(format="lsq-normal-replay-round-post-audit-v1", index=guard["index"],
        critical_report_SHA256s=guard["critical_report_SHA256s"], critical_reports_idempotent=len(guard["critical_report_SHA256s"]),
        protected_raw_artifact_SHA256s=guard["protected_raw_artifact_SHA256s"], protected_raw_files=len(guard["protected_raw_artifact_SHA256s"]),
        all_raw_hashes_equal=True, no_duplicate_archive_on_identical_evidence=True, native_DUT_reruns=0,
        completion_not_claimed=True, overall_status="ACTIVE_NOT_ACCEPTED")
    write_report(UNIFIED / "normal-replay-round-post-audit-v1.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--integrate", action="store_true")
    args = parser.parse_args()
    assert not (args.capture and args.integrate)
    result = integrate() if args.integrate else capture() if args.capture else audit()
    print(json.dumps({key: value for key, value in result.items() if not key.endswith("SHA256s")}, indent=2))
