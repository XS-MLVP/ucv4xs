#!/usr/bin/env python3
"""Build the compact request/feature/check/coverage/gap evidence matrix."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from audit_evidence_io import write_report

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def audit(name: str) -> dict:
    run = ROOT / "results" / name
    metrics = load(run / "coverage-metrics-summary-v1.json")
    points = load(run / "coverage-points-summary-v1.json")
    scoped = load(run / "coverage-scope-audit-v1.json")
    assert all(scoped["verification"].values())
    assert scoped["classification_missing_counts_match"] == {"toggle": True, "branch": True}
    line = load(run / "line-audit.json")
    toggle = load(run / "toggle-gap-classification-v1.json")
    branch = load(run / "branch-gap-classification-v1.json")
    initial = load(run / "initial-branch-boundary-audit-v1.json")
    vsq_boundary = load(run / "vsq-recovery-boundary-audit-v1.json")
    assert all(vsq_boundary["verification"].values()) and vsq_boundary["proven_post_reset_state3_points"] == 3
    runtime_gates = load(run / "post-regression-required-gates-v1.json")
    assert runtime_gates["evidence_checks_completed"]
    assert all(initial["verification"].values())
    assert initial["total_missing_branch_points"] == branch["total_missing_branch_points"]
    assert initial["initial_process_missing_points"] == sum(row["classification_counts"].get("tool_or_artifact_limit", 0) for row in branch["rows"])
    functional = load(run / "execution/functional-coverage.json")
    manifest = load(run / "execution/manifest.json")
    foundation = load(run / "foundation-layer-audit-v1.json")["rows"]
    load_layer = load(run / "load-business-layer-audit-v1.json")["rows"]
    store = load(run / "store-business-layer-audit-v1.json")["rows"]
    parents = load(run / "parent-combinations-audit-v1.json")["rows"]
    layer_rows = {row["dut"]: row for row in foundation + load_layer + store + parents}
    line_rows = {row["dut"]: row for row in line["native"]}
    toggle_rows = {row["dut"]: row for row in toggle["rows"]}
    branch_rows = {row["dut"]: row for row in branch["rows"]}
    metric_rows = {row["dut_export"]: row for row in metrics["builds"]}
    scope_rows = {row["dut"]: row for row in scoped["rows"]}
    specs = load(ROOT / "manifest/duts.json")["duts"]
    functional_rows = {}
    for group in functional["groups"]:
        functional_rows.setdefault(group["instance"], group)
    closure = load(run / "gap-closure-summary-v1.json")["directed_supplements"]
    closure_by_dut = {}
    for item in closure:
        if "dut" in item:
            closure_by_dut.setdefault(item["dut"], []).append(item)
        elif item.get("family") == "uncache_entry":
            for index in range(16):
                closure_by_dut.setdefault(f"uncache_entry_{index}", []).append(item)

    rows = []
    for dut, spec in specs.items():
        export = "DUT" + spec["export_name"]
        assert export in metric_rows and dut in line_rows and dut in toggle_rows and dut in branch_rows
        line_row = line_rows[dut]
        scope_row = scope_rows[dut]
        assert scope_row["build_id"] == metric_rows[export]["build_id"]
        scoped_metrics = {kind: scope_row["metrics"][kind]["original_nonwrapper"] for kind in ("toggle", "branch")}
        assert scoped_metrics["toggle"]["missing"] == toggle_rows[dut]["missing_toggle_points"]
        assert scoped_metrics["branch"]["missing"] == branch_rows[dut]["missing_branch_points"]
        remaining_line = len(line_row.get("uncovered", [])) + sum(len(dep.get("uncovered", [])) for dep in line_row.get("dependencies", []))
        functional_key = f"lsq.{dut}"
        reached = functional_rows.get(functional_key + ".reached")
        checked = functional_rows.get(functional_key + ".checked")
        layer_row = layer_rows.get(dut, {})
        rows.append(dict(
            dut=dut, export=export, top=spec["top"], parameters=spec,
            contract=layer_row.get("contract"), historical_report=layer_row.get("report"),
            semantic_status=layer_row.get("status", "CURRENT_REGRESSION_ONLY"),
            historical_tests=layer_row.get("committed_tests"),
            current_functional=dict(
                reached=dict(hit=sum(value > 0 for value in reached["points"][0]["counts"].values()), total=len(reached["points"][0]["counts"])) if reached else None,
                checked=dict(hit=sum(value > 0 for value in checked["points"][0]["counts"].values()), total=len(checked["points"][0]["counts"])) if checked else None,
            ),
            line=dict(hit=line_row.get("closure_line_hit", line_row["line_hit"]), total=line_row.get("closure_line_total", line_row["line_total"]), remaining=remaining_line, scope="LCOV original source closure excluding Picker wrapper"),
            toggle=dict(hit=scoped_metrics["toggle"]["hit"], total=scoped_metrics["toggle"]["total"], missing=scoped_metrics["toggle"]["missing"], classification=toggle_rows[dut]["classification_counts"], missing_SHA256=scoped_metrics["toggle"]["missing_point_inventory_SHA256"], scope="native original nonwrapper points"),
            branch=dict(hit=scoped_metrics["branch"]["hit"], total=scoped_metrics["branch"]["total"], missing=scoped_metrics["branch"]["missing"], classification=branch_rows[dut]["classification_counts"], missing_SHA256=scoped_metrics["branch"]["missing_point_inventory_SHA256"], scope="native original nonwrapper points"),
            native_build_id=metric_rows[export]["build_id"],
            directed_supplements=closure_by_dut.get(dut, []),
            remaining_boundary=dict(
                line=remaining_line,
                toggle_classifications=toggle_rows[dut]["classification_counts"],
                branch_classifications=branch_rows[dut]["classification_counts"],
                semantic_issues=layer_row.get("issues", []),
                supplemental_required_failures=[item for item in runtime_gates["required_new_functional_failures"] if item["dut"] == dut],
                supplemental_domain_limits=[item for item in runtime_gates["domain_limited_supplements"] if dut in item["duts"]],
                vsq_post_reset_state3_evidence=[dict(source=item["source"], source_line=item["source_line"],
                    hierarchy=item["hierarchy"], source_SHA256=item["source_SHA256"], hit=item["hit"], boundary=item["boundary"])
                    for item in vsq_boundary["proven_points"] if item["dut"] == dut],
                vsq_open_release_wait_evidence=[item for item in vsq_boundary["open_release_wait_points"] if item["dut"] == dut],
                observed_rerun_coverage_gates=[gate for gate in runtime_gates["required_open_gates"] if dut in gate["failed_duts"]],
            ),
        ))
    assert len(rows) == 38
    report = dict(
        format="lsq-final-evidence-matrix-v1", run=name,
        overall_status="ACTIVE_NOT_ACCEPTED",
        unified_tests=manifest["tests"], functional_groups=manifest["functional_groups"],
        native_builds=metrics["native_builds"],
        source_artifacts=dict(
            metrics="coverage-metrics-summary-v1.json", points="coverage-points-summary-v1.json",
            scopes="coverage-scope-audit-v1.json",
            branch_initial_boundaries="initial-branch-boundary-audit-v1.json",
            vsq_recovery_boundaries="vsq-recovery-boundary-audit-v1.json",
            required_runtime_gates="post-regression-required-gates-v1.json",
            line="line-audit.json", toggle="toggle-gap-classification-v1.json", branch="branch-gap-classification-v1.json",
            gap_closure="gap-closure-summary-v1.json", failure_preservation="failure-preservation-audit-v1.json",
        ),
        rows=rows,
        open_required_runtime_gates=runtime_gates["required_open_gates"],
        resolved_runtime_gates=runtime_gates["resolved_runtime_gates"],
        current_required_runtime_gates=runtime_gates["current_required_gates"],
        required_new_functional_failures=runtime_gates["required_new_functional_failures"],
        supplemental_source_triage=runtime_gates["supplemental_source_triage"],
        domain_limited_supplements=runtime_gates["domain_limited_supplements"],
        limits="This matrix is a compact audit index. It retains per-DUT denominators and hashes/references, not a full point list or cycle trace. ACTIVE_NOT_ACCEPTED is intentional: remaining reachable gap classifications and parent semantic failures are explicit, and no leaf/green subset is promoted to whole-LSQ acceptance.",
    )
    output = run / "final-evidence-matrix-v1.json"
    write_report(output, report)
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2, ensure_ascii=False))
    print("rows", len(rows))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
