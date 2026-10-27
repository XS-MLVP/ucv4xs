#!/usr/bin/env python3
"""Delivery audit for the LSU UT workspace.

Checks, without trusting any single previous report:

1. the manifest lists exactly the 19 expected DUTs and every top resolves to a
   unique generated-RTL file whose bytes match ``manifest/lsu-rtl.sha256``;
2. every DUT has a native Picker build report with ``ok``/``smoke.passed``;
3. every DUT has a semantic contract, a gap/coverage file and tests;
4. the referenced unified run has one coverage audit entry per DUT, a matching
   coverage summary and 100% functional coverage;
5. tests contain no xfail/skip/waiver markers;
6. no waveform or per-cycle dump was left in the project tree.
"""
from __future__ import annotations

import hashlib
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DUTS = 19
EXPECTED_FAMILIES = {"store": 9, "load": 9, "std": 1}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    errors: list[str] = []
    checks: list[dict] = []

    duts = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]
    hashes = {}
    for line in (ROOT / "manifest/lsu-rtl.sha256").read_text().splitlines():
        line = line.strip()
        if line:
            digest, name = line.split()
            hashes[name] = digest
    if len(duts) != EXPECTED_DUTS:
        fail(errors, f"manifest lists {len(duts)} DUTs, expected {EXPECTED_DUTS}")
    families = {}
    for key, info in duts.items():
        families[info["family"]] = families.get(info["family"], 0) + 1
    for family, count in EXPECTED_FAMILIES.items():
        if families.get(family) != count:
            fail(errors, f"family {family}: {families.get(family)} DUTs, expected {count}")

    builds = {}
    for report in sorted((ROOT / "results/builds").glob("*/report.json")):
        record = json.loads(report.read_text())
        key = record.get("key")
        if key:
            builds[key] = (report, record)
    summary = json.loads((ROOT / "manifest/coverage-summary.json").read_text())
    baseline = json.loads((ROOT / "manifest/baseline.json").read_text())
    review = baseline.get("failure_review", {})
    if review.get("acceptance_passed") is False:
        fail(errors, f"failure review blocks acceptance: {review.get('status')}")
    for finding in review.get("known_rtl_defects", []):
        fail(errors, f"unresolved RTL defect: {finding}")
    if review.get("historical_failures_fully_attributed") is False:
        fail(errors, "historical failures lack per-node evidence; blanket false-positive verdict is not justified")
    if review.get("independent_reached_checked_complete") is False:
        fail(errors, "independent per-bin reached/checked evidence is incomplete")
    run = summary["run"]
    audit_path = ROOT / "results" / run / "coverage-audit.json"
    if not audit_path.is_file():
        fail(errors, f"missing coverage audit for run {run}")
        audit = {"builds": []}
    else:
        audit = json.loads(audit_path.read_text())
    audited = {b["key"]: b for b in audit["builds"]}
    functional = json.loads((ROOT / "results" / run / "functional-coverage.json").read_text())
    if not functional.get("covered") or functional.get("coverage") != 100.0:
        fail(errors, f"functional coverage is not 100%: {functional.get('coverage')}")

    for key, info in sorted(duts.items()):
        top = info["top"]
        own = ROOT / "rtl" / key / (top + ".sv")
        providers = sorted((ROOT / "rtl").rglob(top + ".sv"))
        if not own.is_file():
            fail(errors, f"{key}: missing {own.relative_to(ROOT)}")
        for candidate in providers:
            if hashes.get(top + ".sv") != sha256(candidate):
                fail(errors, f"{key}: {candidate.relative_to(ROOT)} hash differs from the manifest")
        if not providers:
            fail(errors, f"{key}: no generated RTL for {top}")
        build = builds.get(key)
        if build is None:
            fail(errors, f"{key}: no build report")
        else:
            path, record = build
            if not record.get("ok"):
                fail(errors, f"{key}: build report not ok ({path})")
            smoke = record.get("smoke") or {}
            if not smoke.get("passed"):
                fail(errors, f"{key}: native smoke did not pass")
        contract = ROOT / "docs/contracts" / (key.replace("_", "-") + ".md")
        gap = ROOT / "docs/gaps" / (key + ".json")
        tests = ROOT / "tests" / key
        if not contract.is_file():
            fail(errors, f"{key}: missing contract {contract.relative_to(ROOT)}")
        if not gap.is_file():
            fail(errors, f"{key}: missing gap file {gap.relative_to(ROOT)}")
        else:
            record = json.loads(gap.read_text())
            recorded = (record.get("rtl_sha256") or {}).get(top + ".sv")
            if recorded != hashes.get(top + ".sv"):
                fail(errors, f"{key}: gap file does not bind the RTL hash")
            if "metrics" not in record or "uncovered" not in record:
                fail(errors, f"{key}: gap file lacks metrics/uncovered")
            allowed = {"existing_function_gap", "missing_function_point",
                       "unreachable_structural", "tool_boundary",
                       "unreachable", "structural", "rtl_defect",
                       "mixed_structural_and_rtl_defect"}
            for item in record.get("uncovered", []):
                if not item.get("id") or not item.get("evidence"):
                    fail(errors, f"{key}: uncovered entry without id/evidence: {item}")
                elif item.get("kind") not in allowed:
                    fail(errors, f"{key}: uncovered entry kind {item.get('kind')!r} not classified")
        if not tests.is_dir() or not list(tests.glob("test_*.py")):
            fail(errors, f"{key}: no tests")
        if key not in audited:
            fail(errors, f"{key}: no coverage audit entry in {run}")
        checks.append({"dut": key, "top": top, "family": info["family"],
                       "contract": contract.name, "gap": gap.name,
                       "build": bool(build), "audited": key in audited})

    test_markers = re.compile(r"@pytest\.mark\.(xfail|skip)|pytest\.skip|pytest\.xfail")
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        if test_markers.search(path.read_text()):
            fail(errors, f"skip/xfail marker in {path.relative_to(ROOT)}")
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Assert):
                continue
            expr = node.test
            if (isinstance(expr, ast.Constant) and bool(expr.value) or
                isinstance(expr, ast.BoolOp) and isinstance(expr.op, ast.Or) and
                    any(isinstance(x, ast.Constant) and x.value is True for x in expr.values) or
                isinstance(expr, ast.IfExp) and isinstance(expr.test, ast.Constant) and
                    expr.test.value is False and isinstance(expr.orelse, ast.Constant) and
                    expr.orelse.value is True):
                fail(errors, f"vacuous assertion in {path.relative_to(ROOT)}:{node.lineno}")

    strays = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
              if p.suffix in (".fst", ".vcd") and "results" not in p.parts]
    if strays:
        fail(errors, f"stray waveform files: {strays}")
    trace = json.loads((ROOT / "results" / run / "trace-policy.json").read_text())
    if trace.get("status") != "PASS":
        fail(errors, f"trace policy not PASS: {trace.get('status')}")
    execution = json.loads((ROOT / "results" / run / "manifest.json").read_text())
    if execution.get("pytest_exitstatus") != 0:
        fail(errors, f"pytest exit status {execution.get('pytest_exitstatus')}")
    nonpass = {key: value for key, value in execution.get("tests", {}).items()
               if key != "PASS" and value}
    if nonpass:
        fail(errors, f"non-PASS test outcomes: {nonpass}")
    if execution.get("tests", {}).get("PASS") != summary["tests"]["PASS"]:
        fail(errors, f"test count mismatch between manifest and summary")
    expected_builds = len(duts)
    if len(audited) != expected_builds:
        fail(errors, f"audit has {len(audited)} builds, expected {expected_builds}")
    if summary.get("build_count") != expected_builds:
        fail(errors, f"summary build_count {summary.get('build_count')} != {expected_builds}")

    report = {
        "schema_version": 1,
        "run": run,
        "duts": checks,
        "checks": {
            "dut_count": len(duts),
            "build_reports": len(builds),
            "audited_builds": len(audited),
            "tests_passed": summary["tests"]["PASS"],
            "tests_failed": summary["tests"]["FAIL"],
            "functional_coverage": functional.get("coverage"),
        },
        "errors": errors,
        "status": "PASS" if not errors else "FAIL",
    }
    out = ROOT / "results" / run / ("delivery-recheck-audit.json"
                                      if review else "delivery-audit.json")
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report["checks"], indent=1))
    print("status:", report["status"], "->", out.relative_to(ROOT))
    for error in errors:
        print("ERROR:", error)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
