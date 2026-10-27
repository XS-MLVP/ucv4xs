#!/usr/bin/env python3
"""Delivery self-check for the MMU/TLB verification workspace."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SOUNDNESS = ROOT / 'docs/reports/evidence/soundness-20261025'
CURRENT_INDEX = json.loads((SOUNDNESS / 'final-runs.json').read_text())
FINAL_RUNS = {
    key: (row['run'], *row['metrics']['line'], *row['metrics']['toggle'],
          *row['metrics']['branch'])
    for key, row in CURRENT_INDEX['runs'].items() if key != 'checker-selftest'
}
# Runs that are committed but intentionally not fully closed; functional floor
# and exact metrics are recorded, plus a required known-issue id.
PARTIAL_RUNS = {}
# All five historical symptoms were disproved by valid stimulus/handshake
# controls, not waived. The integrity audit now requires PASS-only outcomes
# and rejects every unhandled XFAIL/SKIP across the entire collection.
KNOWN_XFAIL = {}
BUILD_KEYS = {
    "tlbfa": "20261024T104239445213Z-tlbfa",
    "tlbn": "20261025T022103052014Z-tlbn",
    "wrapper": "20261024T110716556319Z-wrapper",
    "tlb": "20261024T111943888651Z-tlb",
    "l2mq": "20261024T113813508753Z-l2mq",
    "l2pf": "20261024T113829798384Z-l2pf",
    "ptwrepeater": "20261024T115030999840Z-ptwrepeater",
    "ptwfilter": "20261024T115047936888Z-ptwfilter",
    "hptw": "20261024T133449754915Z-hptw",
    "ptw": "20261024T134706987086Z-ptw",
    "pmp": "20261024T134735351815Z-pmp",
    "bitmap": "20261024T134806364585Z-bitmap",
    "bitmapcache": "20261024T134827954742Z-bitmapcache",
    "llptw": "20261024T134846434762Z-llptw",
    "l2tlb": "20261024T120138135720Z-l2tlb",
    "ptwcache": "20261024T145358069282Z-ptwcache",
    "l2tlbwrapper": "20261025T004040447536Z-l2tlbwrapper",
}
RTL_MANIFESTS = [
    "manifest/tlbfa-rtl.sha256",
    "manifest/tlbn-rtl.sha256",
    "manifest/wrapper-rtl.sha256",
    "manifest/tlb-rtl.sha256",
    "manifest/l2mq-rtl.sha256",
    "manifest/l2pf-rtl.sha256",
    "manifest/ptwrepeater-rtl.sha256",
    "manifest/ptwfilter-rtl.sha256",
    "manifest/hptw-rtl.sha256",
    "manifest/ptw-rtl.sha256",
    "manifest/pmp-rtl.sha256",
    "manifest/bitmap-rtl.sha256",
    "manifest/bitmapcache-rtl.sha256",
    "manifest/llptw-rtl.sha256",
    "manifest/ptwcache-rtl.sha256",
    "manifest/l2tlb-rtl.sha256",
    "manifest/l2tlbwrapper-rtl.sha256",
]
REQUIRED_REPORTS = [
    "docs/reports/tlbfa-20261024.md",
    "docs/reports/tlbn-20261025.md",
    "docs/reports/wrapper-20261024.md",
    "docs/reports/tlb-20261024.md",
    "docs/reports/l2-leaves-20261024.md",
    "docs/functional-points-tlbfa.md",
    "docs/functional-points-tlbn.md",
    "docs/functional-points-wrapper.md",
    "docs/functional-points-tlb.md",
    "docs/functional-points-l2-leaves.md",
    "docs/reports/l2-filter-repeater-20261024.md",
    "docs/reports/l2tlb-20261024.md",
    "docs/functional-points-l2tlb.md",
    "docs/functional-points-hptw.md",
    "docs/reports/hptw-20261024.md",
    "docs/functional-points-l2-midblocks.md",
    "docs/reports/l2-midblocks-20261024.md",
    "docs/functional-points-ptwcache.md",
    "docs/reports/ptwcache-20261025.md",
    "docs/functional-points-l2tlbwrapper.md",
    "docs/reports/l2tlbwrapper-20261025.md",
    "docs/reports/llptw-20261025.md",
    "docs/reports/final-delivery-20261025.md",
    "docs/reports/final-delivery-phase2-20261025.md",
    "manifest/known-issues.json",
    "docs/reports/verification-soundness-20261025.md",
    "docs/reports/isa-confirmation-20261026.md",
    "docs/reports/evidence/soundness-20261025/final-runs.json",
    "docs/reports/evidence/soundness-20261025/final-residuals.json",
    "docs/reports/evidence/soundness-20261025/source-drift-review.json",
]
EXTRA_EVIDENCE = [
    "docs/reports/evidence/cycle-ptw-20261024/README.md",
    "docs/reports/evidence/cycle-ptw-20261024/ptwrepeater-final-audit.json",
    "docs/reports/evidence/cycle-ptw-20261024/ptwfilter-final-audit.json",
    "docs/reports/evidence/cycle-l2tlb-20261024/README.md",
    "docs/reports/evidence/cycle-l2tlb-20261024/top-final-audit.json",
    "docs/reports/evidence/cycle-l2tlb-20261024/top-final-functional.json",
    "docs/reports/evidence/cycle-hptw-20261024/README.md",
    "docs/reports/evidence/cycle-hptw-20261024/hptw-final-audit.json",
    "docs/reports/evidence/cycle-hptw-20261024/hptw-final-functional.json",
    "docs/reports/evidence/cycle-l2-midblocks-20261024/README.md",
    "docs/reports/evidence/cycle-l2-midblocks-20261024/ptw-final-audit.json",
    "docs/reports/evidence/cycle-l2-midblocks-20261024/ptw-final-functional.json",
    "docs/reports/evidence/cycle-l2-midblocks-20261024/pmp-final-audit.json",
    "docs/reports/evidence/cycle-l2-midblocks-20261024/pmp-final-functional.json",
    "docs/reports/evidence/cycle-l2-midblocks-20261024/bitmap-final-audit.json",
    "docs/reports/evidence/cycle-l2-midblocks-20261024/bitmap-final-functional.json",
    "docs/reports/evidence/cycle-l2-midblocks-20261024/bitmapcache-final-audit.json",
    "docs/reports/evidence/cycle-l2-midblocks-20261024/bitmapcache-final-functional.json",
    "docs/reports/evidence/cycle-l2-midblocks-20261024/llptw-final-audit.json",
    "docs/reports/evidence/cycle-l2-midblocks-20261024/llptw-final-functional.json",
    "docs/reports/evidence/cycle-ptwcache-20261025/README.md",
    "docs/reports/evidence/cycle-ptwcache-20261025/ptwcache-before-audit.json",
    "docs/reports/evidence/cycle-ptwcache-20261025/ptwcache-final-audit.json",
    "docs/reports/evidence/cycle-ptwcache-20261025/ptwcache-final-functional.json",
    "docs/reports/evidence/cycle-l2tlbwrapper-20261025/README.md",
    "docs/reports/evidence/cycle-l2tlbwrapper-20261025/l2tlbwrapper-before-audit.json",
    "docs/reports/evidence/cycle-l2tlbwrapper-20261025/l2tlbwrapper-mid-audit.json",
    "docs/reports/evidence/cycle-l2tlbwrapper-20261025/l2tlbwrapper-prefinal-audit.json",
    "docs/reports/evidence/cycle-l2tlbwrapper-20261025/l2tlbwrapper-final-audit.json",
    "docs/reports/evidence/cycle-l2tlbwrapper-20261025/l2tlbwrapper-final-functional.json",
    "docs/reports/evidence/cycle-l2tlbwrapper-20261025/perf-trace-l2tlb.json",
    "docs/reports/evidence/cycle-l2tlbwrapper-20261025/perf-trace-l2tlbwrapper.json",
    "docs/reports/evidence/cycle-l2tlbwrapper-20261025/perf-trace-comparison.json",
    "docs/reports/evidence/cycle-llptw-20261025/README.md",
    "docs/reports/evidence/cycle-llptw-20261025/llptw-stage2-audit.json",
    "docs/reports/evidence/cycle-llptw-20261025/llptw-slots-audit.json",
    "docs/reports/evidence/cycle-llptw-20261025/llptw-final-audit.json",
    "docs/reports/evidence/cycle-llptw-20261025/llptw-final-functional.json",
    "docs/reports/evidence/cycle-tlbn-20261025/README.md",
    "docs/reports/evidence/cycle-tlb-gpa-20261025/README.md",
    "docs/reports/evidence/cycle-tlb-gpa-20261025/tlb-before-audit.json",
    "docs/reports/evidence/cycle-tlb-gpa-20261025/tlb-final-audit.json",
    "docs/reports/evidence/cycle-tlb-gpa-20261025/tlb-final-functional.json",
    "docs/reports/evidence/cycle-tlbn-20261025/tlbn-before-audit.json",
    "docs/reports/evidence/cycle-tlbn-20261025/tlbn-mid-audit.json",
    "docs/reports/evidence/cycle-tlbn-20261025/tlbn-final-audit.json",
    "docs/reports/evidence/cycle-tlbn-20261025/tlbn-final-functional.json",
    "docs/reports/evidence/cycle-phase2-20261025/README.md",
    "docs/reports/evidence/cycle-phase2-20261025/phase2-closures.json",
    "docs/reports/evidence/cycle-phase2-20261025/phase2-residuals.json",
]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    failures: list[str] = []
    for name in RTL_MANIFESTS:
        for line in (ROOT / name).read_text().splitlines():
            expected, _sep, path = line.partition("  ")
            path_obj = Path(path)
            if not path_obj.is_absolute():
                prefix = "memblock-hash/mmu/"
                path_obj = ROOT / (path[len(prefix):] if path.startswith(prefix) else path)
            actual = digest(path_obj)
            if actual != expected:
                failures.append(f"RTL hash mismatch: {path}")
    for dut, stamp in BUILD_KEYS.items():
        report = ROOT / "results/builds" / stamp / "report.json"
        if not report.is_file():
            failures.append(f"missing build report: {report}")
            continue
        data = json.loads(report.read_text())
        if not data.get("ok"):
            failures.append(f"build not ok: {report}")
    for dut, (run_name, lines, total_lines, toggles, total_toggles, branch, total_branch) in FINAL_RUNS.items():
        run = ROOT / "results" / run_name
        manifest = json.loads((run / "manifest.json").read_text())
        if manifest.get("state") != "committed" or not manifest.get("coverage_complete"):
            failures.append(f"{dut}: run not committed/complete")
        if manifest.get("pytest_exitstatus") != 0:
            failures.append(f"{dut}: pytest failed")
        functional = json.loads((run / "functional-coverage.json").read_text())
        for group in functional["groups"]:
            if group.get("samples", 0) and group.get("coverage", 0) < 100.0:
                failures.append(f"{dut}: functional {group['instance']} = {group['coverage']}")
        audit = json.loads((run / "coverage-audit.json").read_text())
        got_lines = audit["lcov_lines_dut_only"]["covered_lines"]
        got_total = audit["lcov_lines_dut_only"]["unique_lines"]
        got_toggles = audit["toggles"]["covered"]
        got_total_toggles = audit["toggles"]["total"]
        got_branch = audit["branches"]["covered"]
        got_total_branch = audit["branches"]["total"]
        if (got_lines, got_total) != (lines, total_lines):
            failures.append(f"{dut}: line {got_lines}/{got_total} != {lines}/{total_lines}")
        if (got_toggles, got_total_toggles) != (toggles, total_toggles):
            failures.append(f"{dut}: toggle {got_toggles}/{got_total_toggles}")
        if (got_branch, got_total_branch) != (branch, total_branch):
            failures.append(f"{dut}: branch {got_branch}/{got_total_branch}")
    known = json.loads((ROOT / "manifest/known-issues.json").read_text())
    issue_ids = {issue["id"] for issue in known["issues"]}
    for dut, (issue_id, expected_xfail) in KNOWN_XFAIL.items():
        run_name = FINAL_RUNS[dut][0]
        manifest = json.loads((ROOT / "results" / run_name / "manifest.json").read_text())
        got_xfail = manifest.get("tests", {}).get("XFAIL", 0)
        if got_xfail != expected_xfail:
            failures.append(f"{dut}: XFAIL {got_xfail} != {expected_xfail}")
        if issue_id not in issue_ids:
            failures.append(f"{dut}: known issue {issue_id} missing")
    for dut, (run_name, lines, total_lines, toggles, total_toggles, branch,
              total_branch, functional_floor, issue_id) in PARTIAL_RUNS.items():
        run = ROOT / "results" / run_name
        manifest = json.loads((run / "manifest.json").read_text())
        if manifest.get("state") != "committed" or not manifest.get("coverage_complete"):
            failures.append(f"{dut}: partial run not committed/complete")
        if manifest.get("pytest_exitstatus") != 0:
            failures.append(f"{dut}: partial pytest failed")
        audit = json.loads((run / "coverage-audit.json").read_text())
        if (audit["lcov_lines_dut_only"]["covered_lines"],
                audit["lcov_lines_dut_only"]["unique_lines"]) != (lines, total_lines):
            failures.append(f"{dut}: partial line mismatch")
        if (audit["toggles"]["covered"], audit["toggles"]["total"]) != (toggles, total_toggles):
            failures.append(f"{dut}: partial toggle mismatch")
        if (audit["branches"]["covered"], audit["branches"]["total"]) != (branch, total_branch):
            failures.append(f"{dut}: partial branch mismatch")
        functional = json.loads((run / "functional-coverage.json").read_text())
        for group in functional["groups"]:
            if group.get("samples", 0) and group.get("coverage", 0) < functional_floor:
                failures.append(f"{dut}: functional {group['instance']} below floor")
        if issue_id not in issue_ids:
            failures.append(f"{dut}: known issue {issue_id} missing")
    for report in REQUIRED_REPORTS:
        if not (ROOT / report).is_file():
            failures.append(f"missing report: {report}")
    for evidence in ("tlbfa", "wrapper", "tlb"):
        path = ROOT / "docs/reports/evidence" / f"{evidence}-initial" / "coverage-audit.json"
        if not path.is_file():
            failures.append(f"missing initial evidence: {path}")
    for evidence in EXTRA_EVIDENCE:
        if not (ROOT / evidence).is_file():
            failures.append(f"missing cycle evidence: {evidence}")

    from tools.audit_delivery_integrity import audit as audit_integrity
    try:
        integrity_failures, integrity = audit_integrity(ROOT)
        failures.extend(integrity_failures)
    except (OSError, KeyError, ValueError, AssertionError, StopIteration) as error:
        integrity = {'checks': 0, 'error': str(error)}
        failures.append('integrity audit failed: ' + str(error))
    result = {
        "schema_version": 2,
        "workspace": str(ROOT),
        "final_runs": FINAL_RUNS,
        "checks": (len(RTL_MANIFESTS) + len(BUILD_KEYS) + len(FINAL_RUNS) * 4
                   + len(PARTIAL_RUNS) * 4 + len(KNOWN_XFAIL) * 2
                   + len(REQUIRED_REPORTS) + 3 + len(EXTRA_EVIDENCE)
                   + integrity.get('checks', 0)),
        "integrity": integrity,
        "totals": CURRENT_INDEX['totals'],
        "scope": "Evidence integrity and selected regression only; open residuals remain. Not MMU/ISA signoff.",
        "failures": failures,
        "status": "PASS" if not failures else "FAIL",
    }
    (ROOT / "results/delivery-audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(result["status"], f"{len(failures)} failures")
    for failure in failures:
        print(" -", failure)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
