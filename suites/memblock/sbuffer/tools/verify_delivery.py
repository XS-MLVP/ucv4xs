#!/usr/bin/env python3
"""Final delivery audit for the Sbuffer UT workspace."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINAL = {
    "sbuffer_data": "sbuffer-data-initial-04",
    "sbuffer": "sbuffer-top-contract-03",
}
REPORTS = [
    "docs/reports/sbuffer-data-20261024.md",
    "docs/reports/sbuffer-top-20261024.md",
    "docs/reports/coverage-loop-20261024.md",
    "docs/reports/flush-contract-review-20261024.md",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_rtl() -> list[dict]:
    rows = []
    for line in (ROOT / "manifest/sbuffer-rtl.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        path = ROOT / name
        actual = sha256(path)
        rows.append(dict(path=name, expected=digest, actual=actual, ok=digest == actual))
    return rows


def check_build() -> dict:
    path = ROOT / "results/builds/20261024T024302843131Z-sbuffer/report.json"
    report = json.loads(path.read_text())
    command = report["command"]
    return dict(
        report=str(path.relative_to(ROOT)),
        ok=report.get("ok") is True,
        mem_direct="mem_direct" in command,
        trace="memory-direct.fst" in command,
        coverage="-c" in command,
        vpi=report.get("vpi") is True or "--vpi" in command,
        internal_config=report.get("internal_signal_config") is True or "--internal" in command,
        command=command,
    )


def check_run(name: str, *, require_trace: bool) -> dict:
    run = ROOT / "results" / name
    manifest = json.loads((run / "manifest.json").read_text())
    functional = json.loads((run / "functional-coverage.json").read_text())
    audit = json.loads((run / "coverage-audit.json").read_text())
    trace_path = run / "trace-policy.json"
    trace = json.loads(trace_path.read_text()) if trace_path.is_file() else None
    tests = manifest.get("tests", {})
    return dict(
        run=name,
        manifest_state=manifest.get("state"),
        manifest_ok=manifest.get("state") == "committed" and manifest.get("coverage_complete") is True,
        tests=tests,
        pass_only=set(tests) == {"PASS"},
        functional_coverage=functional["coverage"],
        functional_ok=functional["coverage"] == 100.0 and functional["covered"] is True,
        functional_groups_ok=all(group["coverage"] == 100.0 for group in functional["groups"]),
        metrics=audit["verilator_point_metrics"]["metrics"],
        dut_lines=audit["lcov_lines_dut_only"],
        trace_required=require_trace,
        trace_status=(trace or {}).get("status", "not_applicable_historical"),
        trace_ok=(not require_trace) or (trace is not None and trace.get("status") == "PASS"),
        per_cycle_files=[str(p) for p in run.rglob("*.jsonl")]
        + [str(p) for p in run.rglob("*trace*.json") if p.name != "trace-policy.json"],
        waveforms_in_run=[str(p) for p in run.rglob("*.fst") if p.is_file()]
        + [str(p) for p in run.rglob("*.vcd") if p.is_file()],
    )


def check_wline_domain() -> dict:
    """The parent only issues wline for cbo.zero with a zero payload."""
    path = ROOT / "tests/sbuffer/test_sbuffer.py"
    lines = path.read_text().splitlines()
    violations = []
    occurrences = 0
    for index, line in enumerate(lines):
        if "wline=True" not in line:
            continue
        occurrences += 1
        window = "\n".join(lines[index: index + 6])
        if "data=0" not in window:
            violations.append(index + 1)
    return dict(
        file=str(path.relative_to(ROOT)),
        occurrences=occurrences,
        violations=violations,
        ok=occurrences > 0 and not violations,
    )


def main() -> None:
    problems = []
    rtl = check_rtl()
    if not all(row["ok"] for row in rtl):
        problems.append("RTL hash mismatch")
    build = check_build()
    if not build["ok"]:
        problems.append("DUT build report not ok")
    if not build["mem_direct"]:
        problems.append("DUT build is not mem_direct")
    if not build["trace"] or not build["coverage"]:
        problems.append("DUT build lacks trace or coverage")
    if build["vpi"]:
        problems.append("DUT build enables VPI")
    if build["internal_config"]:
        problems.append("DUT build enables internal-signal config")
    contract_tests = [
        "test_fence_flush_empty_requires_sqempty",
        "test_cmo_completion_uses_sbempty_without_sqempty",
        "test_wline_zero_all_lines",
    ]
    test_source = (ROOT / "tests/sbuffer/test_sbuffer.py").read_text()
    missing_contract_tests = [name for name in contract_tests if f"async def {name}(" not in test_source]
    if missing_contract_tests:
        problems.append(f"missing contract tests: {missing_contract_tests}")
    wline = check_wline_domain()
    if not wline["ok"]:
        problems.append(f"top-level wline uses a non-zero/unverifiable payload: {wline}")
    runs = {
        "sbuffer_data": check_run(FINAL["sbuffer_data"], require_trace=False),
        "sbuffer": check_run(FINAL["sbuffer"], require_trace=True),
    }
    for key, row in runs.items():
        if not row["manifest_ok"]:
            problems.append(f"{key}: manifest not committed/complete")
        if not row["pass_only"]:
            problems.append(f"{key}: tests are not all PASS: {row['tests']}")
        if not row["functional_ok"]:
            problems.append(f"{key}: functional coverage not 100%")
        if not row["functional_groups_ok"]:
            problems.append(f"{key}: a functional coverage group is below 100%")
        if not row["trace_ok"]:
            problems.append(f"{key}: trace policy not PASS")
        if row["waveforms_in_run"]:
            problems.append(f"{key}: waveforms retained in run")
        if row["per_cycle_files"]:
            problems.append(f"{key}: per-cycle dump retained")
    missing_reports = [path for path in REPORTS if not (ROOT / path).is_file()]
    if missing_reports:
        problems.append(f"missing reports: {missing_reports}")
    stray = [str(p) for p in ROOT.rglob("*.fst")] + [str(p) for p in ROOT.rglob("*.vcd")]
    if stray:
        problems.append(f"stray waveforms in project: {stray}")
    per_cycle_project = [str(p) for p in ROOT.rglob("*.jsonl")]
    if per_cycle_project:
        problems.append(f"per-cycle dumps in project: {per_cycle_project}")
    for path in (
        "manifest/baseline.json", "manifest/toolchain.json", "manifest/duts.json",
        "manifest/known-issues.json", "manifest/sbuffer-rtl.sha256",
        "dut/sbuffer/__init__.py", "results/builds/20261024T024302843131Z-sbuffer/report.json",
    ):
        if not (ROOT / path).is_file():
            problems.append(f"missing artifact: {path}")
    storage = {
        "results_bytes": sum(p.stat().st_size for p in (ROOT / "results").rglob("*") if p.is_file()),
        "dut_bytes": sum(p.stat().st_size for p in (ROOT / "dut").rglob("*") if p.is_file()),
        "compressed_intermediates": [
            str(p.relative_to(ROOT)) for p in (ROOT / "results").rglob("*.dat.zst")
        ],
    }
    report = {
        "format": "sbuffer-delivery-audit-v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if not problems else "FAIL",
        "problems": problems,
        "rtl": rtl,
        "build": build,
        "wline_domain": wline,
        "contract_tests": contract_tests,
        "missing_contract_tests": missing_contract_tests,
        "runs": runs,
        "reports": REPORTS,
        "stray_waveforms": stray,
        "per_cycle_files_in_project": per_cycle_project,
        "storage": storage,
        "limits": (
            "Functional coverage 100% means every defined semantic bin was hit after successful checks, "
            "not that all RTL lines/toggles/branches are covered. Known native gaps are documented in "
            "manifest/known-issues.json and retain their original denominators."
        ),
    }
    output = ROOT / "results/delivery-audit.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "problems")}, indent=1))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
