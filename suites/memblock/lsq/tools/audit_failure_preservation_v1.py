#!/usr/bin/env python3
"""Audit that directed supplements do not hide or rewrite existing failures."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from audit_expanded_regression_v1 import cases, failure_digest
from audit_evidence_io import write_report

ROOT = Path(__file__).resolve().parents[1]
RELOCATED_FAILURE_NODES = (
    "tests.vsq.test_extended::test_same_cycle_dispatch_redirect_interface_boundary_has_no_ghost[0]",
    "tests.vsq.test_extended::test_same_cycle_dispatch_redirect_interface_boundary_has_no_ghost[7]",
)


def normalize_known_failure_source_lines(data):
    result = json.loads(json.dumps(data))
    for node in RELOCATED_FAILURE_NODES:
        if node not in result:
            continue
        assert result[node]["outcome"] == "FAIL"
        frame = re.compile(r"(?m)^tests/vsq/test_extended\.py:(196|226): in test_same_cycle_dispatch_redirect_interface_boundary_has_no_ghost$")
        assert len(frame.findall(result[node]["detail"])) == 1
        result[node]["detail"] = frame.sub(
            "tests/vsq/test_extended.py:<known-source-line-relocation>: in test_same_cycle_dispatch_redirect_interface_boundary_has_no_ghost", result[node]["detail"])
    return result


def relocated_failure_source_evidence():
    previous = ROOT / "results/entry-toggle-gap-after-01/verification-source/tests/vsq/test_extended.py"
    current = ROOT / "tests/vsq/test_extended.py"
    left, right = previous.read_text(), current.read_text()
    assert sha256(previous) == "0b6207752c4f4fc7cf8a72f72f1cc96ee7ff59c117f7da78c8e2acb9411d763b"
    assert sha256(current) == "599e85006dcae50c985d1245fd329e31e171243bb3e7b7850b61712cb1837d74"
    diff = [row for row in difflib.SequenceMatcher(a=left.splitlines(), b=right.splitlines()).get_opcodes() if row[0] != "equal"]
    assert len(diff) == 1 and diff[0][0] == "insert" and diff[0][4] - diff[0][3] == 30
    old_tree, new_tree = ast.parse(left), ast.parse(right)
    added_name = "test_redirect_release_walks_after_head_is_consumed"
    added = [node for node in new_tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == added_name]
    assert len(added) == 1
    new_tree.body.remove(added[0])
    assert ast.dump(old_tree, include_attributes=False) == ast.dump(new_tree, include_attributes=False)
    return dict(retained_earlier_source=str(previous.relative_to(ROOT)), retained_earlier_source_SHA256=sha256(previous),
                current_source=str(current.relative_to(ROOT)), current_source_SHA256=sha256(current),
                sole_change="insert30lines_one_preexisting_release_test", inserted_test=added_name,
                all_preexisting_function_ASTs_unchanged=True,
                limits="Compares an existing retained earlier source snapshot and current source; does not invent a complete per-file snapshot for regression15.")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def pytest_status(run: str) -> dict:
    manifest = json.loads((ROOT / "results" / run / "execution/manifest.json").read_text())
    xml = ROOT / "results" / run / "pytest.xml"
    root = ET.parse(xml).getroot()
    cases = root.iter("testcase")
    failures = errors = skipped = 0
    total = 0
    outcomes = Counter()
    for case in cases:
        total += 1
        failures += sum(1 for _ in case.findall("failure"))
        errors += sum(1 for _ in case.findall("error"))
        skipped += sum(1 for _ in case.findall("skipped"))
        outcome = "FAIL" if case.find("failure") is not None else "ERROR" if case.find("error") is not None else "SKIP" if case.find("skipped") is not None else "PASS"
        outcomes[outcome] += 1
    assert outcomes == Counter(manifest["tests"]), (run, outcomes, manifest["tests"])
    for artifact in manifest["artifacts"]:
        assert sha256(Path(artifact["path"])) == artifact["sha256"], artifact["path"]
    return dict(
        run=run, state=manifest["state"], pytest_exitstatus=manifest["pytest_exitstatus"],
        manifest_tests=manifest["tests"], total_cases=total, failures=failures, errors=errors, skipped=skipped,
        coverage_complete=manifest["coverage_complete"], cleanup_complete=manifest["cleanup_complete"],
        manifest_sha256=sha256(ROOT / "results" / run / "execution/manifest.json"),
        junit_counts_match_manifest=True, artifact_hashes_verified=True,
    )


def audit(name: str) -> dict:
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    expanded = json.loads((run / "expanded-regression-audit-v1.json").read_text())
    assert expanded["run"] == name
    comparison = expanded["failure_preservation"]
    old_cases = cases("lsq-progress-regression-13")
    new_cases = cases(name)
    old_failures = {node: item for node, item in old_cases.items() if item["outcome"] in ("FAIL", "ERROR")}
    new_failures = {node: item for node, item in new_cases.items() if item["outcome"] in ("FAIL", "ERROR")}
    direct_comparison = dict(
        before_failure_count=len(old_failures),
        after_failure_count=len(new_failures),
        old_failures_missing=sorted(set(old_failures) - set(new_cases)),
        old_failure_signatures_changed=sorted(node for node, item in old_failures.items() if node in new_cases and new_cases[node] != item),
        new_failure_nodes=sorted(set(new_failures) - set(old_failures)),
        before_failure_primary_SHA256=failure_digest(old_cases),
        after_failure_primary_SHA256=failure_digest(new_cases),
    )
    assert all(comparison[key] == value for key, value in direct_comparison.items())
    assert comparison["every_old_failure_primary_equal"]
    assert not comparison["old_failures_missing"]
    assert not comparison["old_failure_signatures_changed"]
    baseline = pytest_status("lsq-progress-regression-13")
    current = pytest_status(name)
    assert current["total_cases"] == expanded["node_counts"]["after"]
    assert current["failures"] == comparison["after_failure_count"]
    assert current["errors"] == 0 and current["skipped"] == 0

    layer_files = {
        "load": "load-business-layer-audit-v1.json",
        "store": "store-business-layer-audit-v1.json",
        "parent": "parent-combinations-audit-v1.json",
    }
    layer = {}
    for family, filename in layer_files.items():
        data = json.loads((run / filename).read_text())
        rows = []
        for row in data["rows"]:
            tests = row["committed_tests"]
            if "FAIL" in tests:
                rows.append(dict(dut=row["dut"], tests=tests, status=row["status"], issues=row["issues"]))
        layer[family] = rows

    directed = [
        pytest_status("vlq-toggle-gap-after-02"),
        pytest_status("entry-toggle-gap-after-01"),
        pytest_status("entry-toggle-gap-after-02"),
        pytest_status("raw-toggle-gap-after-03"),
        pytest_status("raw-toggle-gap-after-05"),
        pytest_status("vsq-gap-after-04"),
        pytest_status("replay-metadata-gap-after-02"),
        pytest_status("rar-latter-gap-after-02"),
        pytest_status("deq-width-gap-after-02"),
        pytest_status("replay-checkpoint-pool-after-01"),
        pytest_status("lq-checkpoint-pool-after-01"),
        pytest_status("lsq-checkpoint-pool-after-01"),
        pytest_status("forward-payload-pool-after-02"),
        pytest_status("psq-payload-pool-after-02"),
        pytest_status("sq-payload-pool-after-02"),
        pytest_status("psq-strict-lifetimes-after-01"),
        pytest_status("sq-strict-lifetimes-after-01"),
        pytest_status("lsq-strict-lifetimes-after-01"),
        pytest_status("forward-prefix-byte-after-01"),
        pytest_status("psq-prefix-byte-after-01"),
        pytest_status("sq-prefix-byte-after-01"),
        pytest_status("lsq-prefix-byte-after-01"),
        pytest_status("uq-page-pairs-after-02"),
        pytest_status("psq-page-pairs-after-01"),
        pytest_status("sq-page-pairs-after-01"),
        pytest_status("lsq-page-pairs-after-01"),
        pytest_status("vsq-release-windows-after-01"),
        pytest_status("sq-release-windows-after-01"),
        pytest_status("lsq-release-windows-after-01"),
        pytest_status("vsq-deep-suffix-after-02"),
        pytest_status("vsq-retire-batch-after-03"),
        pytest_status("vsq-cancel-capacity-after-01"),
        pytest_status("sq-cancel-capacity-after-01"),
        pytest_status("lsq-cancel-capacity-after-01"),
        pytest_status("vsq-retire-known-width-after-01"),
        pytest_status("sq-retire-known-width-after-01"),
        pytest_status("lsq-retire-known-width-after-01"),
        pytest_status("sq-scalar-reservation-after-01"),
        pytest_status("lsq-scalar-reservation-after-01"),
        pytest_status("lqu-response-payload-after-01"),
        pytest_status("lq-response-payload-after-01"),
        pytest_status("lsq-response-payload-after-01"),
        pytest_status("lq-RAW-owners-after-02"),
        pytest_status("lsq-RAW-owners-after-02"),
    ]
    assert all(
        item["state"] == "committed" and item["pytest_exitstatus"] == 0 and item["failures"] == 0
        and item["errors"] == 0 and item["skipped"] == 0 and item["coverage_complete"] and item["cleanup_complete"]
        for item in directed
    )
    corrected_failure = pytest_status("vlq-toggle-gap-after-01")
    assert corrected_failure["pytest_exitstatus"] != 0 and corrected_failure["failures"] == 1
    rerun_name = "checkpoint-failure-retention-01"
    rerun = pytest_status(rerun_name)
    rerun_cases = cases(rerun_name)
    # These eight original nodes are explicitly selected by the rerun command;
    # do not require the historical full-regression total on a directed rerun.
    expected_rerun_nodes = {
        "tests.replay.test_extended::test_strict_full_pool_is_not_unblocked_by_only_ready_bits",
        "tests.load_queue.test_replay::test_strict_address_wait_ignores_bitmap_until_real_matching_sta",
        *(f"tests.replay.test_timing::test_disabled_feedback_cannot_clear_strict_dependency[{i}]" for i in range(3)),
        *(f"tests.load_queue.test_replay::test_disabled_s3_feedback_cannot_clear_live_strict_dependency[{i}]" for i in range(3)),
    }
    assert set(rerun_cases) == expected_rerun_nodes
    assert rerun["state"] == "committed" and rerun["coverage_complete"] and rerun["cleanup_complete"]
    assert rerun["errors"] == rerun["skipped"] == 0 and rerun["failures"] == 7 and rerun["pytest_exitstatus"] == 1
    assert all(new_cases[node] == item for node, item in rerun_cases.items())
    wrapper_rerun_name = "checkpoint-wrapper-failure-retention-01"
    wrapper_rerun = pytest_status(wrapper_rerun_name)
    wrapper_cases = cases(wrapper_rerun_name)
    wrapper_base = "tests.lsq_wrapper.test_replay_gaps::test_full_population_real_ready_bitmap_does_not_replace_strict_execution_wakeup"
    assert set(wrapper_cases) == {wrapper_base + "[bitmap-control]", wrapper_base + "[strict-full-pool]"}
    assert wrapper_rerun["state"] == "committed" and wrapper_rerun["coverage_complete"] and wrapper_rerun["cleanup_complete"]
    assert wrapper_rerun["errors"] == wrapper_rerun["skipped"] == 0 and wrapper_rerun["failures"] == 1 and wrapper_rerun["pytest_exitstatus"] == 1
    assert all(new_cases[node] == item for node, item in wrapper_cases.items())

    store_run_name = "store-payload-failure-retention-01"
    store_run = pytest_status(store_run_name)
    store_cases = cases(store_run_name)
    prefixes = ("tests.forward.", "tests.psq.", "tests.store_queue.")
    original_store_cases = {node: item for node, item in new_cases.items() if node.startswith(prefixes)}
    assert len(original_store_cases) == 329
    assert set(original_store_cases) <= set(store_cases)
    assert all(store_cases[node] == item for node, item in original_store_cases.items())
    added_store = set(store_cases) - set(original_store_cases)
    assert len(added_store) == 3
    assert all("test_pool_payload::test_all_slots_full_width_high_low_payload_lifetimes" in node and store_cases[node]["outcome"] == "PASS" for node in added_store)
    assert store_run["state"] == "committed" and store_run["coverage_complete"] and store_run["cleanup_complete"]
    assert store_run["errors"] == store_run["skipped"] == 0 and store_run["failures"] == 64 and store_run["pytest_exitstatus"] == 1
    assert store_run["total_cases"] == 332
    assert failure_digest(original_store_cases) == failure_digest(store_cases)
    store_directory = ROOT / "results" / store_run_name
    store_launch = json.loads((store_directory / "source-aggregate-launch.json").read_text())
    store_end = json.loads((store_directory / "source-aggregate-end.json").read_text())
    assert store_end.pop("launch_and_end_equal") and store_launch == store_end
    assert not list((store_directory / "cases").rglob("*.jsonl"))
    assert not list((store_directory / "cases").rglob("*.fst")) and not list((store_directory / "cases").rglob("*.vcd"))

    strict_name = "store-strict-directory-regression-01"
    strict_status = pytest_status(strict_name)
    strict_current = cases(strict_name)
    strict_original = {node: item for node, item in new_cases.items() if node.startswith(prefixes + ("tests.lsq_wrapper.",))}
    assert len(strict_original) == 1018 and len(strict_current) == 1025
    assert all(strict_current[node] == item for node, item in strict_original.items())
    assert failure_digest(strict_original) == failure_digest(strict_current)
    assert len(set(strict_current) - set(strict_original)) == 7
    assert all(strict_current[node]["outcome"] == "PASS" for node in set(strict_current) - set(strict_original))
    assert strict_status["manifest_tests"] == {"PASS": 868, "FAIL": 157}
    assert strict_status["state"] == "committed" and strict_status["coverage_complete"] and strict_status["cleanup_complete"]
    assert strict_status["errors"] == strict_status["skipped"] == 0 and strict_status["pytest_exitstatus"] == 1
    strict_evidence = json.loads((ROOT / "results" / strict_name / "store-strict-regression-evidence-v1.json").read_text())
    assert all(strict_evidence["verification"].values()) and strict_evidence["failure_SHA256"] == failure_digest(strict_current)

    contributor_name = "store-strict-contributor-regression-02"
    contributor_status = pytest_status(contributor_name)
    contributor_current = cases(contributor_name)
    contributor_original = {node: item for node, item in new_cases.items() if node in contributor_current}
    assert len(contributor_original) == 1059 and len(contributor_current) == 1066
    assert all(contributor_current[node] == item for node, item in contributor_original.items())
    assert len(set(contributor_current) - set(contributor_original)) == 7
    assert all(contributor_current[node]["outcome"] == "PASS" for node in set(contributor_current) - set(contributor_original))
    assert failure_digest(contributor_original) == failure_digest(contributor_current)
    assert contributor_status["manifest_tests"] == {"PASS": 897, "FAIL": 169}
    assert contributor_status["state"] == "committed" and contributor_status["coverage_complete"] and contributor_status["cleanup_complete"]
    assert contributor_status["errors"] == contributor_status["skipped"] == 0 and contributor_status["pytest_exitstatus"] == 1
    contributor_evidence = json.loads((ROOT / "results" / contributor_name / "store-strict-contributor-regression-evidence-v1.json").read_text())
    assert all(contributor_evidence["verification"].values()) and contributor_evidence["failure_SHA256"] == failure_digest(contributor_current)
    assert contributor_evidence["coverage_monotonicity"]["passed"] and not contributor_evidence["coverage_monotonicity"]["waived"]

    prefix_name = "store-prefix-contributor-regression-01"
    prefix_status = pytest_status(prefix_name)
    prefix_cases = cases(prefix_name)
    assert len(prefix_cases) == 1072 and set(contributor_current) < set(prefix_cases)
    assert all(prefix_cases[node] == value for node, value in contributor_current.items())
    assert failure_digest(prefix_cases) == failure_digest(contributor_current)
    prefix_added = set(prefix_cases) - set(contributor_current)
    assert len(prefix_added) == 6 and all(prefix_cases[node]["outcome"] == "PASS" for node in prefix_added)
    assert prefix_status["manifest_tests"] == {"PASS": 903, "FAIL": 169} and prefix_status["pytest_exitstatus"] == 1
    assert prefix_status["state"] == "committed" and prefix_status["coverage_complete"] and prefix_status["cleanup_complete"]
    assert prefix_status["errors"] == prefix_status["skipped"] == 0
    prefix_evidence = json.loads((ROOT / "results" / prefix_name / "store-prefix-contributor-regression-evidence-v1.json").read_text())
    assert all(prefix_evidence["verification"].values()) and prefix_evidence["failure_SHA256"] == failure_digest(prefix_cases)
    prefix_probe = pytest_status("store-prefix-byte-probe-01")
    assert prefix_probe["manifest_tests"] == {"PASS": 4, "FAIL": 2} and prefix_probe["pytest_exitstatus"] == 1

    uq_name = "uq-page-contributor-regression-01"
    uq_status = pytest_status(uq_name)
    uq_current = cases(uq_name)
    uq_old = {node: item for node, item in new_cases.items() if node.startswith("tests.unalign.")}
    uq_baseline = dict(prefix_cases); uq_baseline.update(uq_old)
    assert len(uq_baseline) == 1113 and len(uq_current) == 1119
    assert all(uq_current[node] == item for node, item in uq_baseline.items())
    assert failure_digest(uq_baseline) == failure_digest(uq_current)
    uq_added = set(uq_current) - set(uq_baseline)
    assert len(uq_added) == 6 and all(uq_current[node]["outcome"] == "PASS" for node in uq_added)
    assert uq_status["manifest_tests"] == {"PASS": 950, "FAIL": 169} and uq_status["pytest_exitstatus"] == 1
    assert uq_status["state"] == "committed" and uq_status["coverage_complete"] and uq_status["cleanup_complete"]
    assert uq_status["errors"] == uq_status["skipped"] == 0
    uq_evidence = json.loads((ROOT / "results" / uq_name / "uq-page-contributor-regression-evidence-v1.json").read_text())
    assert all(uq_evidence["verification"].values()) and uq_evidence["failure_SHA256"] == failure_digest(uq_current)
    assert uq_evidence["coverage_monotonicity"]["passed"] and not uq_evidence["coverage_monotonicity"]["waived"]

    release_name = "vsq-release-contributor-regression-01"
    release_status = pytest_status(release_name)
    release_current = cases(release_name)
    release_old = dict(uq_current)
    release_vsq_old = {node: item for node, item in new_cases.items() if node.startswith("tests.vsq.")}
    release_old.update(release_vsq_old)
    release_baseline = cases("vsq-release-windows-baseline-01")
    release_baseline_only = set(release_baseline) - set(release_vsq_old)
    release_old.update({node: release_baseline[node] for node in release_baseline_only})
    assert len(release_old) == 1162 and len(release_current) == 1171
    for node, item in release_old.items():
        if node in RELOCATED_FAILURE_NODES:
            assert normalize_known_failure_source_lines({node: release_current[node]})[node] == normalize_known_failure_source_lines({node: item})[node]
        else:
            assert release_current[node] == item
    release_added = set(release_current) - set(release_old)
    assert len(release_added) == 9 and all(release_current[node]["outcome"] == "PASS" for node in release_added)
    assert release_status["manifest_tests"] == {"PASS": 1000, "FAIL": 171} and release_status["pytest_exitstatus"] == 1
    assert release_status["state"] == "committed" and release_status["coverage_complete"] and release_status["cleanup_complete"]
    assert release_status["errors"] == release_status["skipped"] == 0
    assert failure_digest(normalize_known_failure_source_lines(release_old)) == failure_digest(normalize_known_failure_source_lines(release_current))
    release_evidence = json.loads((ROOT / "results" / release_name / "vsq-release-contributor-regression-evidence-v1.json").read_text())
    assert all(release_evidence["verification"].values()) and release_evidence["normalized_failure_SHA256"] == failure_digest(normalize_known_failure_source_lines(release_current))
    assert release_evidence["coverage_monotonicity"]["passed"] and not release_evidence["coverage_monotonicity"]["waived"]

    deep_name = "vsq-deep-suffix-contributor-regression-01"
    deep_status = pytest_status(deep_name)
    deep_current = cases(deep_name)
    assert len(deep_current) == 1172 and set(release_current) < set(deep_current)
    assert all(deep_current[node] == item for node, item in release_current.items())
    deep_added = set(deep_current) - set(release_current)
    assert len(deep_added) == 1 and next(iter(deep_added)).startswith("tests.vsq.test_deep_suffix::")
    assert deep_current[next(iter(deep_added))]["outcome"] == "PASS"
    assert failure_digest(release_current) == failure_digest(deep_current)
    assert deep_status["manifest_tests"] == {"PASS": 1001, "FAIL": 171} and deep_status["pytest_exitstatus"] == 1
    assert deep_status["state"] == "committed" and deep_status["coverage_complete"] and deep_status["cleanup_complete"]
    assert deep_status["errors"] == deep_status["skipped"] == 0
    deep_evidence = json.loads((ROOT / "results" / deep_name / "vsq-deep-suffix-contributor-evidence-v1.json").read_text())
    assert all(deep_evidence["verification"].values()) and deep_evidence["failure_SHA256"] == failure_digest(deep_current)
    assert deep_evidence["coverage_monotonicity"]["passed"] and not deep_evidence["coverage_monotonicity"]["waived"]

    batch_name = "vsq-retire-batch-contributor-regression-01"
    batch_status, batch_current = pytest_status(batch_name), cases(batch_name)
    assert len(batch_current) == 1173 and set(deep_current) < set(batch_current)
    assert all(batch_current[node] == item for node, item in deep_current.items())
    batch_added = set(batch_current) - set(deep_current)
    assert len(batch_added) == 1 and next(iter(batch_added)).startswith("tests.vsq.test_retire_batch_width::")
    assert batch_current[next(iter(batch_added))]["outcome"] == "PASS"
    assert failure_digest(deep_current) == failure_digest(batch_current)
    assert batch_status["manifest_tests"] == {"PASS": 1002, "FAIL": 171} and batch_status["pytest_exitstatus"] == 1
    assert batch_status["state"] == "committed" and batch_status["coverage_complete"] and batch_status["cleanup_complete"]
    assert batch_status["errors"] == batch_status["skipped"] == 0
    batch_evidence = json.loads((ROOT / "results" / batch_name / "vsq-retire-batch-contributor-evidence-v1.json").read_text())
    assert all(batch_evidence["verification"].values()) and batch_evidence["failure_SHA256"] == failure_digest(batch_current)
    assert batch_evidence["coverage_monotonicity"]["passed"] and not batch_evidence["coverage_monotonicity"]["waived"]
    batch_checker = pytest_status("vsq-retire-batch-after-01")
    assert batch_checker["manifest_tests"] == {"PASS": 3, "FAIL": 1} and batch_checker["pytest_exitstatus"] == 1
    assert failure_digest(cases("vsq-retire-batch-after-01")) == batch_evidence["calibration_history"]["batch_checker_failure"]["failure_SHA256"]

    cancel_name = "vsq-cancel-capacity-contributor-regression-01"
    cancel_status, cancel_cases = pytest_status(cancel_name), cases(cancel_name)
    assert len(cancel_cases) == 1177 and set(batch_current) < set(cancel_cases)
    assert all(cancel_cases[node] == value for node, value in batch_current.items())
    cancel_added = set(cancel_cases) - set(batch_current)
    cancel_fail_node = "tests.store_queue.test_cancel_capacity::test_real_cancel_capacity_old_bytes_and_every_new_UID_normal_consumption[True]"
    assert len(cancel_added) == 4 and {node for node in cancel_added if cancel_cases[node]["outcome"] == "FAIL"} == {cancel_fail_node}
    assert sum(cancel_cases[node]["outcome"] == "PASS" for node in cancel_added) == 3
    assert failure_digest(batch_current) == failure_digest({node:cancel_cases[node] for node in batch_current})
    assert cancel_status["manifest_tests"] == {"PASS":1005,"FAIL":172} and cancel_status["errors"] == cancel_status["skipped"] == 0
    assert cancel_status["pytest_exitstatus"] == 1
    cancel_evidence = json.loads((ROOT / "results" / cancel_name / "vsq-cancel-capacity-contributor-evidence-v1.json").read_text())
    assert all(cancel_evidence["verification"].values())
    assert cancel_evidence["current_failure_SHA256"] == failure_digest(cancel_cases)
    cancel_probes = [pytest_status(name) for name in ("vsq-cancel-capacity-probe-01","vsq-cancel-capacity-probe-02")]
    assert cancel_probes[0]["manifest_tests"] == {"PASS":2,"FAIL":1} and cancel_probes[1]["manifest_tests"] == {"PASS":3,"FAIL":1}
    assert all(cases(row["run"])[cancel_fail_node]["outcome"] == "FAIL" for row in cancel_probes)
    assert cancel_evidence["head_permit_failure"]["identity_matches_cancelled_not_replacement"] and not cancel_evidence["head_permit_failure"]["waived"]

    known_name = "vsq-retire-known-width-contributor-regression-01"
    known_status, known_cases = pytest_status(known_name), cases(known_name)
    assert len(known_cases) == 1180 and set(cancel_cases) < set(known_cases)
    assert all(known_cases[node] == value for node,value in cancel_cases.items())
    known_added = set(known_cases) - set(cancel_cases)
    assert len(known_added) == 3 and all(known_cases[node]["outcome"] == "PASS" for node in known_added)
    assert failure_digest(known_cases) == failure_digest(cancel_cases)
    assert known_status["manifest_tests"] == {"PASS":1008,"FAIL":172} and known_status["errors"] == known_status["skipped"] == 0
    assert known_status["pytest_exitstatus"] == 1 and known_cases[cancel_fail_node]["outcome"] == "FAIL"
    known_evidence = json.loads((ROOT / "results" / known_name / "vsq-retire-known-width-contributor-evidence-v1.json").read_text())
    assert all(known_evidence["verification"].values()) and known_evidence["current_failure_SHA256"] == failure_digest(known_cases)
    assert known_evidence["required_new_functional_failures"] == cancel_evidence["required_new_functional_failures"]
    known_probe = pytest_status("vsq-retire-known-width-probe-01")
    assert known_probe["manifest_tests"] == {"PASS":3} and known_probe["errors"] == known_probe["skipped"] == 0

    scalar_name = "sq-scalar-reservation-contributor-regression-01"
    scalar_status,scalar_cases = pytest_status(scalar_name),cases(scalar_name)
    assert len(scalar_cases) == 1182 and set(known_cases) < set(scalar_cases)
    assert all(scalar_cases[node] == value for node,value in known_cases.items())
    scalar_added = set(scalar_cases) - set(known_cases)
    assert len(scalar_added) == 2 and all(scalar_cases[node]["outcome"] == "PASS" for node in scalar_added)
    assert failure_digest(scalar_cases) == failure_digest(known_cases)
    assert scalar_status["manifest_tests"] == {"PASS":1010,"FAIL":172} and scalar_status["errors"] == scalar_status["skipped"] == 0
    assert scalar_status["pytest_exitstatus"] == 1 and scalar_cases[cancel_fail_node]["outcome"] == "FAIL"
    scalar_evidence = json.loads((ROOT/"results"/scalar_name/"sq-scalar-reservation-contributor-evidence-v1.json").read_text())
    assert all(scalar_evidence["verification"].values()) and scalar_evidence["current_failure_SHA256"] == failure_digest(scalar_cases)
    assert scalar_evidence["domain"] == "UNIT_INTERFACE_LSQ_CAPACITY" and not scalar_evidence["normal_full_core_producer_proven"]
    scalar_calibration = scalar_evidence["calibration"]
    assert scalar_calibration["first_probe"]["manifest_tests"] == {"FAIL":2} and scalar_calibration["corrected_probe"]["manifest_tests"] == {"PASS":2}
    assert scalar_calibration["first_probe_failure_SHA256"] == failure_digest(cases("sq-scalar-reservation-probe-01"))

    from audit_load_response_payload_v1 import BASELINE as RESPONSE_BASELINE,FULL as RESPONSE_FULL,compare_preexisting_nodes,expected_nodes
    response_status,response_cases=pytest_status(RESPONSE_FULL),cases(RESPONSE_FULL)
    response_baseline=cases(RESPONSE_BASELINE)
    assert len(response_baseline)==1454 and len(response_cases)==1457
    assert all(response_cases[node]==value for node,value in response_baseline.items())
    assert all(response_cases[node]==value for node,value in scalar_cases.items())
    response_added=set(response_cases)-set(response_baseline)
    assert len(response_added)==3 and all(response_cases[node]["outcome"]=="PASS" for node in response_added)
    assert failure_digest(response_baseline)==failure_digest(response_cases)
    assert response_status["manifest_tests"]=={"PASS":1265,"FAIL":192} and response_status["pytest_exitstatus"]==1
    assert response_status["state"]=="committed" and response_status["coverage_complete"] and response_status["cleanup_complete"]
    response_source_relocation=compare_preexisting_nodes(expected_nodes(),response_baseline)
    response_evidence=json.loads((ROOT/"results"/RESPONSE_FULL/"load-response-payload-contributor-evidence-v1.json").read_text())
    assert all(response_evidence["verification"].values()) and response_evidence["current_failure_SHA256"]==failure_digest(response_cases)
    assert response_evidence["expected_node_source_relocation"]==response_source_relocation

    from audit_load_raw_owners_v1 import FULL as RAW_FULL,PAIRS as RAW_PAIRS,calibration as raw_calibration
    raw_status,raw_cases=pytest_status(RAW_FULL),cases(RAW_FULL)
    assert len(raw_cases)==1569 and all(raw_cases[node]==value for node,value in response_cases.items())
    raw_added=set(raw_cases)-set(response_cases)
    assert raw_added==set().union(*(set(cases(after))-set(cases(before)) for _,before,after in RAW_PAIRS))
    assert len(raw_added)==112 and all(raw_cases[node]["outcome"]=="PASS" for node in raw_added)
    assert raw_status["manifest_tests"]=={"PASS":1377,"FAIL":192} and raw_status["pytest_exitstatus"]==1
    assert raw_status["state"]=="committed" and raw_status["coverage_complete"] and raw_status["cleanup_complete"]
    assert raw_status["errors"]==raw_status["skipped"]==0 and failure_digest(raw_cases)==failure_digest(response_cases)
    raw_evidence=json.loads((ROOT/"results"/RAW_FULL/"load-RAW-owners-contributor-evidence-v1.json").read_text())
    assert all(raw_evidence["verification"].values()) and raw_evidence["current_failure_SHA256"]==failure_digest(raw_cases)
    assert raw_evidence["required_new_functional_failures"]==response_evidence["required_new_functional_failures"]
    raw_calibration_evidence=raw_calibration()
    assert raw_evidence["calibration"]==raw_calibration_evidence

    source_checks = {}
    for path in (
        ROOT / "tests/vlq/test_toggle_gap_closure.py",
        ROOT / "tests/uncache_entry/test_toggle_gap_closure.py",
        ROOT / "tests/raw/test_toggle_gap_closure.py",
        ROOT / "tests/vsq/test_extended.py",
        ROOT / "tests/replay/test_gap_closure.py",
        ROOT / "tests/rar/test_extended.py",
        ROOT / "tests/deq/test_lifecycle.py",
        ROOT / "tests/replay/test_pool_payload.py",
        ROOT / "tests/load_queue/test_checkpoint_pool.py",
        ROOT / "tests/lsq_wrapper/test_checkpoint_pool.py",
        ROOT / "tests/forward/test_pool_payload.py",
        ROOT / "tests/psq/test_pool_payload.py",
        ROOT / "tests/store_queue/test_pool_payload.py",
        ROOT / "lsqverify/store_payload.py",
        ROOT / "tests/psq/test_strict_lifetimes.py",
        ROOT / "tests/store_queue/test_strict_lifetimes.py",
        ROOT / "tests/lsq_wrapper/test_store_strict_lifetimes.py",
        ROOT / "lsqverify/store_strict.py",
        ROOT / "lsqverify/native_case_probe.py",
        ROOT / "lsqverify/store_prefix.py",
        ROOT / "tests/forward/test_prefix_byte_windows.py",
        ROOT / "tests/psq/test_prefix_byte_windows.py",
        ROOT / "tests/store_queue/test_prefix_byte_windows.py",
        ROOT / "tests/lsq_wrapper/test_prefix_byte_windows.py",
        ROOT / "lsqverify/uq_page_pairs.py",
        ROOT / "tests/unalign/test_page_pairs.py",
        ROOT / "tests/psq/test_uq_page_pairs.py",
        ROOT / "tests/store_queue/test_uq_page_pairs.py",
        ROOT / "tests/lsq_wrapper/test_uq_page_pairs.py",
        ROOT / "lsqverify/vsq_recovery.py",
        ROOT / "tests/vsq/test_release_windows.py",
        ROOT / "tests/store_queue/test_release_windows.py",
        ROOT / "tests/lsq_wrapper/test_release_windows.py",
        ROOT / "tests/vsq/test_deep_suffix.py",
        ROOT / "tests/vsq/test_retire_batch_width.py",
        ROOT / "lsqverify/vsq_cancel_capacity.py",
        ROOT / "tests/vsq/test_cancel_capacity.py",
        ROOT / "tests/store_queue/test_cancel_capacity.py",
        ROOT / "tests/lsq_wrapper/test_cancel_capacity.py",
        ROOT / "lsqverify/vsq_retire_known.py",
        ROOT / "tests/vsq/test_retire_known_width.py",
        ROOT / "tests/store_queue/test_retire_known_width.py",
        ROOT / "tests/lsq_wrapper/test_retire_known_width.py",
        ROOT / "lsqverify/sq_scalar_reservation.py",
        ROOT / "tests/store_queue/test_scalar_reservation_pool.py",
        ROOT / "tests/lsq_wrapper/test_scalar_reservation_pool.py",
        ROOT / "lsqverify/load_response_payload.py",
        ROOT / "tests/load_uncache/test_response_payload_pool.py",
        ROOT / "tests/load_queue/test_response_payload_pool.py",
        ROOT / "tests/lsq_wrapper/test_response_payload_pool.py",
        ROOT / "lsqverify/load_raw_owners.py",
        ROOT / "tests/load_queue/test_raw_checkpoint_owners.py",
        ROOT / "tests/lsq_wrapper/test_raw_checkpoint_owners.py",
    ):
        text = path.read_text()
        source_checks[str(path.relative_to(ROOT))] = dict(
            SHA256=sha256(path), contains_skip="skip" in text.lower(), contains_xfail="xfail" in text.lower(),
        )
        assert not source_checks[str(path.relative_to(ROOT))]["contains_skip"]
        assert not source_checks[str(path.relative_to(ROOT))]["contains_xfail"]

    report = dict(
        format="lsq-failure-preservation-audit-v1", run=name,
        unified_regression=dict(
            tests=manifest["tests"], pytest_exitstatus=manifest["pytest_exitstatus"],
            total_cases=current["total_cases"], failures=current["failures"], errors=current["errors"], skipped=current["skipped"],
            baseline="lsq-progress-regression-13", baseline_tests=baseline["manifest_tests"],
            node_counts=expanded["node_counts"],
            every_failure_primary_equal=comparison["every_old_failure_primary_equal"],
            old_failures_missing=comparison["old_failures_missing"],
            old_failure_signatures_changed=comparison["old_failure_signatures_changed"],
            new_failure_nodes=comparison["new_failure_nodes"],
            before_failure_primary_SHA256=comparison["before_failure_primary_SHA256"],
            after_failure_primary_SHA256=comparison["after_failure_primary_SHA256"],
        ),
        parent_and_business_failures_retained=layer,
        directed_supplement_runs=directed,
        corrected_test_failure_retained=corrected_failure,
        current_strict_failure_rerun=dict(**rerun, baseline=name, all_eight_normalized_outcomes_and_failure_details_equal=True,
                                         selected_nodes=sorted(rerun_cases)),
        current_wrapper_strict_failure_rerun=dict(**wrapper_rerun, baseline=name,
            both_normalized_outcomes_and_failure_details_equal=True, selected_nodes=sorted(wrapper_cases)),
        current_store_path_full_directory_rerun=dict(**store_run, baseline=name,
            original_nodes=329, added_passing_pool_nodes=3, original_failures=64,
            all_original_normalized_outcomes_and_failure_details_equal=True,
            original_failure_SHA256=failure_digest(original_store_cases), current_failure_SHA256=failure_digest(store_cases),
            source_aggregate_launch_end_equal=True, per_cycle_JSON=False, waveforms=False,
            directories=["tests/forward", "tests/psq", "tests/store_queue"]),
        current_strict_full_directory_rerun=dict(**strict_status, baseline=name,
            original_nodes=1018, added_passing_nodes=7, original_failures=157,
            all_original_normalized_outcomes_and_failure_details_equal=True,
            original_failure_SHA256=failure_digest(strict_original), current_failure_SHA256=failure_digest(strict_current),
            source_aggregate_launch_end_equal=True, per_cycle_JSON=False, waveforms=False,
            coverage_monotonicity=strict_evidence["coverage_monotonicity"],
            evidence="../store-strict-directory-regression-01/store-strict-regression-evidence-v1.json",
            directories=["tests/forward", "tests/psq", "tests/store_queue", "tests/lsq_wrapper"]),
        current_complete_contributor_rerun=dict(**contributor_status, baseline=name,
            original_nodes=1059, added_passing_nodes=7, original_failures=169,
            original_failure_SHA256=failure_digest(contributor_original), current_failure_SHA256=failure_digest(contributor_current),
            all_original_normalized_outcomes_and_failure_details_equal=True,
            wrapper_original_contributors=730, wrapper_current_contributors=732,
            coverage_monotonicity=contributor_evidence["coverage_monotonicity"],
            historical_failed_partial_run_retained=True, actual_single_fresh_run_not_coverage_OR=True,
            evidence="../store-strict-contributor-regression-02/store-strict-contributor-regression-evidence-v1.json"),
        current_prefix_complete_contributor_rerun=dict(**prefix_status, baseline=contributor_name,
            original_nodes=1066, added_passing_nodes=6, original_failures=169,
            original_failure_SHA256=failure_digest(contributor_current), current_failure_SHA256=failure_digest(prefix_cases),
            all_original_normalized_outcomes_and_failure_details_equal=True,
            wrapper_contributors_before=732, wrapper_contributors_after=735,
            coverage_monotonicity=prefix_evidence["coverage_monotonicity"],
            evidence="../store-prefix-contributor-regression-01/store-prefix-contributor-regression-evidence-v1.json"),
        current_uq_page_five_build_rerun=dict(**uq_status, baseline="store-prefix-contributor-regression-01 + regression15 unalign nodes",
            original_nodes=1113, added_passing_nodes=6, original_failures=169,
            original_failure_SHA256=failure_digest(uq_baseline), current_failure_SHA256=failure_digest(uq_current),
            all_original_normalized_outcomes_and_failure_details_equal=True,
            coverage_monotonicity=uq_evidence["coverage_monotonicity"], historical_prior_runs_retained=True,
            actual_single_fresh_five_build_execution=True,
            evidence="../uq-page-contributor-regression-01/uq-page-contributor-regression-evidence-v1.json"),
        current_vsq_release_six_build_rerun=dict(**release_status,
            baseline="uq-page-contributor-regression-01 + regression15 VSQ nodes + one pre-existing VSQ contributor",
            original_nodes=1162, current_nodes=1171, added_passing_nodes=9, original_failures=171,
            original_failure_SHA256=failure_digest(release_old), current_failure_SHA256=failure_digest(release_current),
            normalized_failure_SHA256=failure_digest(normalize_known_failure_source_lines(release_current)),
            known_source_line_relocations=[dict(node=node, before_line=196, after_line=226) for node in RELOCATED_FAILURE_NODES],
            source_line_relocation_evidence=relocated_failure_source_evidence(),
            all_original_normalized_outcomes_and_failure_details_equal=True,
            coverage_monotonicity=release_evidence["coverage_monotonicity"], historical_prior_runs_retained=True,
            actual_single_fresh_six_build_execution=True,
            evidence="../vsq-release-contributor-regression-01/vsq-release-contributor-regression-evidence-v1.json"),
        current_vsq_deep_suffix_six_build_rerun=dict(**deep_status,
            baseline="vsq-release-contributor-regression-01",
            original_nodes=1171, current_nodes=1172, added_passing_nodes=1, original_failures=171,
            original_failure_SHA256=failure_digest(release_current), current_failure_SHA256=failure_digest(deep_current),
            all_original_normalized_outcomes_and_failure_details_equal=True,
            coverage_monotonicity=deep_evidence["coverage_monotonicity"], historical_prior_runs_retained=True,
            actual_single_fresh_six_build_execution=True,
            evidence="../vsq-deep-suffix-contributor-regression-01/vsq-deep-suffix-contributor-evidence-v1.json"),
        current_vsq_retire_batch_six_build_rerun=dict(**batch_status,
            baseline="vsq-deep-suffix-contributor-regression-01",
            original_nodes=1172, current_nodes=1173, added_passing_nodes=1, original_failures=171,
            original_failure_SHA256=failure_digest(deep_current), current_failure_SHA256=failure_digest(batch_current),
            all_original_normalized_outcomes_and_failure_details_equal=True,
            coverage_monotonicity=batch_evidence["coverage_monotonicity"], historical_prior_runs_retained=True,
            actual_single_fresh_six_build_execution=True,
            evidence="../vsq-retire-batch-contributor-regression-01/vsq-retire-batch-contributor-evidence-v1.json"),
        current_vsq_cancel_capacity_six_build_rerun=dict(**cancel_status, baseline=batch_name,
            original_nodes=1173,current_nodes=1177,added_passing_nodes=3,original_failures=171,
            new_required_functional_failures=cancel_evidence["required_new_functional_failures"],
            original171_failure_SHA256=failure_digest(batch_current),current172_failure_SHA256=failure_digest(cancel_cases),
            all_original_outcomes_and_failure_details_equal=True,
            head_permit_failure=cancel_evidence["head_permit_failure"],probes=cancel_probes,
            coverage_monotonicity=cancel_evidence["coverage_monotonicity"],
            actual_single_fresh_six_build_execution=True,
            evidence="../vsq-cancel-capacity-contributor-regression-01/vsq-cancel-capacity-contributor-evidence-v1.json"),
        current_vsq_retire_known_width_six_build_rerun=dict(**known_status,baseline=cancel_name,
            original_nodes=1177,current_nodes=1180,added_passing_nodes=3,original_failures=172,
            original_failure_SHA256=failure_digest(cancel_cases),current_failure_SHA256=failure_digest(known_cases),
            all_original_outcomes_and_failure_details_equal=True,
            required_new_functional_failures=known_evidence["required_new_functional_failures"],
            head_permit_failure=known_evidence["head_permit_failure"],probe=known_probe,
            coverage_monotonicity=known_evidence["coverage_monotonicity"],actual_single_fresh_six_build_execution=True,
            evidence="../vsq-retire-known-width-contributor-regression-01/vsq-retire-known-width-contributor-evidence-v1.json"),
        current_scalar_reservation_interface_six_build_rerun=dict(**scalar_status,baseline=known_name,
            original_nodes=1180,current_nodes=1182,added_passing_nodes=2,original_failures=172,
            original_failure_SHA256=failure_digest(known_cases),current_failure_SHA256=failure_digest(scalar_cases),
            all_original_outcomes_and_failure_details_equal=True,domain=scalar_evidence["domain"],normal_full_core_producer_proven=False,
            required_new_functional_failures=scalar_evidence["required_new_functional_failures"],head_permit_failure=scalar_evidence["head_permit_failure"],
            calibration=scalar_calibration,coverage_monotonicity=scalar_evidence["coverage_monotonicity"],actual_single_fresh_six_build_execution=True,
            evidence="../sq-scalar-reservation-contributor-regression-01/sq-scalar-reservation-contributor-evidence-v1.json"),
        corrected_vsq_retire_batch_checker_failure_retained=dict(**batch_checker,
            failure_SHA256=failure_digest(cases("vsq-retire-batch-after-01")),
            explanation="The first test precondition mixed physical end with virtual position. The real FAIL and raw JUnit remain; corrected case checks eight4-flow uops, actual public end32 then normal end33. No DUT/model/checker comparison was removed."),
        current_load_response_eight_build_rerun=dict(**response_status,baseline=RESPONSE_BASELINE,
            original_nodes=1454,current_nodes=1457,added_passing_nodes=3,original_failures=192,
            original_failure_SHA256=failure_digest(response_baseline),current_failure_SHA256=failure_digest(response_cases),
            all1454_outcomes_and_failure_details_exactly_equal=True,prior1182_results_preserved=True,
            expected_node_source_relocation=response_source_relocation,
            required_new_functional_failures=response_evidence["required_new_functional_failures"],
            coverage_monotonicity=response_evidence["coverage_monotonicity"],
            interrupted_run_preserved=response_evidence["interrupted_run_preserved"],
            source_correct_S3_serial_response_not_SID_waiver=True,
            evidence=f"../{RESPONSE_FULL}/load-response-payload-contributor-evidence-v1.json"),
        corrected_prefix_consumer_failures_retained=dict(**prefix_probe,
            explanation="Two retained first-probe failures are address-only generic consumer ambiguity. Directed ordered UID consumer now checks the same legal alias stimuli without modifying shared actors/models; not an RTL counterexample or removed case."),
        current_load_RAW_owners_eight_build_rerun=dict(**raw_status,baseline=RESPONSE_FULL,
            original_nodes=1457,current_nodes=1569,added_passing_nodes=112,original_failures=192,
            original_failure_SHA256=failure_digest(response_cases),current_failure_SHA256=failure_digest(raw_cases),
            all1457_outcomes_and_failure_details_exactly_equal=True,
            required_new_functional_failures=raw_evidence["required_new_functional_failures"],
            coverage_monotonicity=raw_evidence["coverage_monotonicity"],calibration=raw_calibration_evidence,
            historical_formal01_normal_ROB_claim_withdrawn=True,formal02_bounded_pendingNext_projection=True,
            native_full_upstream_ROB_proven=False,
            evidence=f"../{RAW_FULL}/load-RAW-owners-contributor-evidence-v1.json"),
        source_checks=source_checks,
        separation=dict(
            directed_results_are_separate_directories=True,
            directed_passes_not_merged_into_unified_regression=True,
            unified_failure_count_is_explicit_and_historical_nodes_unchanged=True,
            no_skip_xfail_in_new_supplement_tests=True,
        ),
        conclusion="The expanded committed regression preserves every regression13 failure node and normalized primary failure signature, explicitly lists any new failure node, and keeps directed supplement results separate. The initial incorrect VLQ assertion is retained as a failed diagnostic run and is not used as evidence of DUT failure or success.",
        limits="This preserves historical failure signatures and result separation; it does not prove the remaining reachable toggle/branch points or semantic failures are closed.",
    )
    output = run / "failure-preservation-audit-v1.json"
    write_report(output, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
