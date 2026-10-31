#!/usr/bin/env python3
"""Audit this bounded failure review; never call an evidence PASS a DUT PASS."""
from __future__ import annotations
import ucv.runtime as ucv_paths

from collections import Counter
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "review/failure_recheck_20261026"
RUN = "failure-recheck-final-03"
COMMIT = "893e1580b705d81f113c30c7a05734e09a08050e"


def load(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + chr(10))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def junit(path):
    nodes = []
    for case in ET.parse(path).getroot().iter("testcase"):
        child = next((case.find(tag) for tag in ("failure", "error", "skipped")
                      if case.find(tag) is not None), None)
        outcome = {"failure": "FAIL", "error": "ERROR", "skipped": "SKIP"}.get(
            child.tag if child is not None else "", "PASS")
        nodes.append(dict(classname=case.get("classname"), name=case.get("name"),
                          outcome=outcome, message=child.get("message", "") if child is not None else None))
    return nodes


def point_id(point):
    return (Path(point["file"]).name, point["line"], point["name"])


def sync_metadata(report, audit):
    """Refresh current indexes only; preserve old run and metadata snapshots."""
    for relative in ("manifest/baseline.json", "manifest/coverage-summary.json",
                     "docs/gaps/load_s2.json", "docs/gaps/new_load_unit.json"):
        source = ROOT / relative; backup = REVIEW / "before-metadata" / relative
        if not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(source.read_bytes())
    baseline = load(ROOT / "manifest/baseline.json")
    review_info = {k: report[k] for k in ("status", "acceptance_passed", "known_rtl_defects",
                   "historical_failures_fully_attributed", "independent_reached_checked_complete")}
    review_info.update(report="docs/bug-reports-20261026/README.md",
                       evidence="review/failure_recheck_20261026/final-audit.json")
    baseline.update(current_status="known_rtl_performance_defect_and_evidence_limits",
                    final_run=RUN, failure_review=review_info,
                    current_status_note="Review supersedes earlier closure: 582 PASS / 1 ordinary FAIL; 1 confirmed RTL performance-event defect; historical per-node and independent reached/checked evidence remain incomplete.")
    status = baseline["verification_status"]
    status.update(duts_built=sorted(b["key"] for b in audit["builds"]),
                  functional_tests_run=True, coverage_closed=False)
    save(ROOT / "manifest/baseline.json", baseline)
    summary = dict(schema_version=2, run=RUN, tests=report["outcomes"], build_count=19,
        acceptance_passed=False, known_rtl_defects=report["known_rtl_defects"],
        functional_coverage=dict(coverage=audit["functional_coverage"].get("coverage"),
            covered=audit["functional_coverage"].get("covered"),
            meaning="declared bin sampling only; not independent reached/checked completeness",
            independent_reached_checked_complete=False), duts=[],
        totals={k:0 for k in ("line_hit","line_total","branch_hit","branch_total",
                             "toggle_hit","toggle_total","procedural_uncovered")},
        note="Per-DUT original denominators retained. Totals are display sums only. Coverage completion does not override ordinary FAIL or prove independent semantic checking.")
    for b in sorted(audit["builds"], key=lambda x:x["key"]):
        row=dict(dut=b["key"],build_id=b["build_id"],
            line_hit=b["lcov_lines_dut_only"]["covered_lines"], line_total=b["lcov_lines_dut_only"]["unique_lines"],
            branch_hit=b["branches"]["covered"],branch_total=b["branches"]["total"],
            toggle_hit=b["toggles_dut_only"]["covered"],toggle_total=b["toggles_dut_only"]["total"],
            procedural_uncovered=b["lcov_lines_dut_only"]["procedural_uncovered"],
            coverage_dat_sha256=b["coverage_dat_sha256"])
        summary["duts"].append(row)
        for k in summary["totals"]:
            summary["totals"][k]+=row[k]
    save(ROOT / "manifest/coverage-summary.json",summary)
    for key in ("load_s2", "new_load_unit"):
        p=ROOT / "docs/gaps" / (key+".json"); gap=load(p)
        b=next(x for x in audit["builds"] if x["key"]==key)
        gap["run"]=RUN
        metrics=gap["metrics"]
        for name, hit, total in [("line_dut_only",b["lcov_lines_dut_only"]["covered_lines"],b["lcov_lines_dut_only"]["unique_lines"]),
                                 ("branch",b["branches"]["covered"],b["branches"]["total"]),
                                 ("toggle_closure" if key=="new_load_unit" else "toggle_dut_only",
                                  b["toggles_dut_only"]["covered"],b["toggles_dut_only"]["total"])]:
            metrics[name]=dict(hit=hit,total=total,percent=round(100*hit/total,2) if total else 0)
        metrics["functional"]["checked"]=False
        metrics["functional"]["note"]="Tool reports 100% declared-bin sampling; independent per-bin reached/checked completeness is not proven."
        gap["status"]="KNOWN_RTL_PERFORMANCE_DEFECT_AND_EVIDENCE_LIMITS"
        gap["review"]=review_info
        for item in gap["uncovered"]:
            if item["id"]=="LS2-PERF3-CONSTANT-ZERO":
                item.update(kind="rtl_defect",required_supplement=True,defect_id="LSU-HWPF-MISS-001")
                item["evidence"]=[
                    "rtl/load_s2/LoadUnitS2.sv:549-550 troubleMaker excludes instrType[2]; :573-575 cause_6 includes troubleMaker and dcacheResp.miss",
                    "rtl/load_s2/LoadUnitS2.sv:396-397 isHwPrefetch requires instrType[2]; :865-866 perf3 samples isHwPrefetch AND cause_6 through two registers; :1137 exports it",
                    "NewLoadUnit.scala:1061,1120,1280-1286 proves the same contradictory conditions; :1266 counts raw prefetch miss separately",
                    "tests/load_s2/test_spec_prefetch_miss.py: miss=1 independently expects 1 and actually reads 0; retained ordinary FAIL"]
            if item["id"]=="LS2-PERF-WIDTH":
                item["evidence"]=["rtl/load_s2/LoadUnitS2.sv:1134-1136 exports {5'h0, boolean_REG_1}; upper bits are literal zeros, separate from the perf3 defect"]
            if item["id"]=="NLU-PERF-WIDTH-AND-DEAD-COUNTER":
                item.update(kind="mixed_structural_and_rtl_defect",defect_id="LSU-HWPF-MISS-001",required_supplement=True)
                item["evidence"]=[
                    "Leaf stage perf outputs zero-extend delayed booleans. NewLoadUnit.sv:1138-1159 forwards stage events through 6-bit registers; upper bits settle to zero but can have random initialization transients",
                    "NewLoadUnit.sv:1152-1153,4011 forwards S2 perf3 as parent perf7. S2 defect LSU-HWPF-MISS-001 is proven dynamically only at the exposed S2 boundary; generated parent has no direct hardware-prefetch injection port",
                    "174 residual raw points are a mixed group, not 174 harmless constants or 174 independent bugs; no denominator is removed"]
            if item["id"]=="NLU-SCALAR-ACCESS-CONSTANTS":
                item["points"]="3 points on scalar lane accessType instruction/prefetch encoding bits"
            if item["id"]=="NLU-TRAIN-META-RESIDUAL":
                item["evidence"]=["No metaSource residual remains in the final raw uncovered list; the previous duplicate-copy explanation is not used as an unreachable proof"]
        if key=="load_s2":
            gap["failures"]=[dict(id="LSU-HWPF-MISS-001",node="tests/load_s2/test_spec_prefetch_miss.py::test_hw_pf_miss_event_counts_a_real_cache_miss[1]",expected=1,actual=0,run=RUN)]
            for finding in gap["semantic_findings"]:
                if finding["id"]=="LS2-PERF3-DEAD":
                    finding.update(defect_claim=True,defect_id="LSU-HWPF-MISS-001",impact="Confirmed performance-event defect; no data-correctness failure claimed. RTL remains unchanged.")
        else:
            ids={"NLU-CHILD-PORT-CAUSE-COPIES","NLU-ALLOW-RR-PULSE"}
            retracted=[item for item in gap["uncovered"] if item["id"] in ids]
            if retracted:
                gap["retracted_gap_classifications"]=dict(reason="Legally reached by new parent cases; original 21+1 unreachable claims are disproved, denominators unchanged.",
                    old_entries=retracted,recovered_points=next(x for x in report["per_dut"] if x["dut"]==key)["recovered"])
                gap["uncovered"]=[item for item in gap["uncovered"] if item["id"] not in ids]
            gap["known_defects"]=[dict(id="LSU-HWPF-MISS-001",observation="S2 dynamic reproduction; parent perf7 static propagation only. Direct hardware-prefetch parent input absent in this generated configuration.")]
        save(p,gap)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--sync-metadata",action="store_true")
    args=parser.parse_args()
    errors = []
    inventory = load(REVIEW / "inventory.json")
    history = []
    for old in inventory["historical_runs"]:
        path = ROOT / "results" / old["run"] / "manifest.json"
        unchanged = sha(path) == old["manifest_sha256"]
        if not unchanged:
            errors.append(f"historical manifest changed: {old['run']}")
        history.append(dict(old, manifest_unchanged=unchanged,
            verdict="collection_failure_not_dut_execution" if old["exit"] == 2 else
                    "historical_node_root_cause_unresolved"))
    run = ROOT / "results" / RUN
    manifest = load(run / "manifest.json")
    nodes = junit(run / "junit.xml")
    outcomes = Counter(n["outcome"] for n in nodes)
    if dict(outcomes) != {"PASS": 582, "FAIL": 1}:
        errors.append(f"unexpected final outcomes: {dict(outcomes)}")
    failed = [n for n in nodes if n["outcome"] != "PASS"]
    if len(failed) != 1 or failed[0]["name"] != "test_hw_pf_miss_event_counts_a_real_cache_miss[1]":
        errors.append("final failure identity does not match confirmed RTL defect")
    parts = {}
    for n in nodes:
        group = ("checker_sensitivity" if "test_checker_sensitivity" in n["classname"] else
                 "independent" if "test_independent_recheck" in n["classname"] else "regular_tests")
        counter = parts.setdefault(group, Counter()); counter[n["outcome"]] += 1
    artifacts = []
    for a in manifest["artifacts"]:
        path = Path(a["path"]); ok = path.is_file() and sha(path) == a["sha256"]
        if not ok:
            errors.append(f"artifact hash mismatch: {path}")
        artifacts.append(dict(kind=a["kind"], path=str(path.relative_to(ROOT)), sha256=a["sha256"], valid=ok))
    native = [a for a in manifest["artifacts"] if a["kind"] == "native"]
    if len(native) != 19:
        errors.append(f"expected 19 native artifacts, found {len(native)}")
    build_file_checks = {}
    for a in native:
        for name, expected in a["build"]["files"].items():
            p = Path(name)
            build_file_checks[name] = p.is_file() and sha(p) == expected
    errors.extend(f"build fingerprint mismatch: {name}" for name, ok in build_file_checks.items() if not ok)
    source_checks = []
    for line in (ROOT / "manifest/lsu-rtl.sha256").read_text().splitlines():
        expected, name = line.split()
        files = sorted((ROOT / "rtl").rglob(Path(name).name))
        original = ucv_paths.soc_rtl_for(ROOT) / Path(name).name
        for p in [original] + files:
            ok = p.is_file() and sha(p) == expected
            source_checks.append(dict(path=str(p), sha256=expected, valid=ok))
            if not ok:
                errors.append(f"fixed RTL differs: {p}")
    provenance = load(run / "run-provenance.json")
    if sha(run / "console.log") != provenance["console_sha256"]:
        errors.append("final console hash mismatch")
    execution_sources = []
    reporting_changes = []
    for name, expected in provenance["sources_sha256"].items():
        ok = (ROOT / name).is_file() and sha(ROOT / name) == expected
        if name.startswith(("tests/", "", "review/")) or name in ("conftest.py", "pytest.ini", "tools/run.py"):
            execution_sources.append(dict(path=name, matched=ok))
            if not ok:
                errors.append(f"execution source changed since run: {name}")
        elif not ok:
            reporting_changes.append(name)
    for path in (ROOT / "tests").rglob("test_*.py"):
        text = path.read_text()
        if re.search(r"@pytest\.mark\.(?:xfail|skip)|pytest\.(?:xfail|skip)", text):
            errors.append(f"waiver marker: {path}")
        for n in ast.walk(ast.parse(text)):
            if not isinstance(n, ast.Assert):
                continue
            e = n.test
            if (isinstance(e, ast.Constant) and bool(e.value) or
                isinstance(e, ast.BoolOp) and isinstance(e.op, ast.Or) and
                    any(isinstance(x, ast.Constant) and x.value is True for x in e.values) or
                isinstance(e, ast.IfExp) and isinstance(e.test, ast.Constant) and
                    e.test.value is False and isinstance(e.orelse, ast.Constant) and e.orelse.value is True):
                errors.append(f"constant assertion: {path}:{n.lineno}")
    seed_runs = []
    for seed, name in [(1, "recheck-prefetch-spec-02"), (17, "recheck-prefetch-seed-17-01"),
                       (123, "recheck-prefetch-seed-123-01")]:
        p = ROOT / "results" / name
        m = load(p / "manifest.json"); pr = load(p / "run-provenance.json"); ns = junit(p / "junit.xml")
        ok = (Counter(x["outcome"] for x in ns) == {"PASS": 1, "FAIL": 1} and
              pr["verilator_seed"] == seed and sum(w["native_inputs"] for w in m["workers"]) == 2 and
              len([a for a in m["artifacts"] if a["kind"] == "native"]) == 1)
        if not ok:
            errors.append(f"seed evidence incomplete: {name}")
        seed_runs.append(dict(run=name, seed=seed, outcomes=m["tests"], checked=ok))
    before = load(ROOT / "results/unified-regression-02/coverage-audit.json")
    after = load(run / "coverage-audit.json")
    delta = []
    for b in sorted(after["builds"], key=lambda x: x["key"]):
        prev = next(x for x in before["builds"] if x["key"] == b["key"])
        for section, denom in [("toggles_dut_only", "total"), ("branches", "total"),
                               ("lcov_lines_dut_only", "unique_lines")]:
            if prev[section][denom] != b[section][denom]:
                errors.append(f"denominator changed: {b['key']} {section}")
        old = {point_id(p) for p in prev["toggles_dut_only"]["uncovered_points"]}
        new = {point_id(p) for p in b["toggles_dut_only"]["uncovered_points"]}
        recovered = [dict(file=f, line=l, name=n) for f, l, n in sorted(old - new)]
        delta.append(dict(dut=b["key"], line=[b["lcov_lines_dut_only"]["covered_lines"], b["lcov_lines_dut_only"]["unique_lines"]],
            branch=[b["branches"]["covered"], b["branches"]["total"]],
            old_toggle=[prev["toggles_dut_only"]["covered"],prev["toggles_dut_only"]["total"]],
            new_toggle=[b["toggles_dut_only"]["covered"],b["toggles_dut_only"]["total"]], recovered=recovered))
    parent = next(x for x in delta if x["dut"] == "new_load_unit")
    if len(parent["recovered"]) != 22 or parent["new_toggle"] != [39686,40024]:
        errors.append("parent coverage recheck differs from reported 22-point recovery")
    fixed = []
    for filename in ("NewLoadUnit.scala", "NewStoreUnit.scala", "StdExeUnit.scala"):
        relative = "src/main/scala/xiangshan/mem/pipeline/" + filename
        data = subprocess.check_output(["git", "-C", str(ucv_paths.source_path_for(ROOT)), "show", COMMIT + ":" + relative])
        ok = (ucv_paths.source_path_for(ROOT) / relative).read_bytes() == data
        if not ok:
            errors.append(f"Scala working source differs from fixed commit: {filename}")
        fixed.append(dict(file=relative, sha256=hashlib.sha256(data).hexdigest(), matched=ok))
    intermediates = []
    for p in sorted(REVIEW.glob("*.xml")):
        ns = junit(p)
        intermediates.append(dict(file=str(p.relative_to(ROOT)), outcomes=dict(Counter(n["outcome"] for n in ns)),
                                  failed_nodes=[n for n in ns if n["outcome"] != "PASS"]))
    for path in [run, ROOT / "results/recheck-prefetch-spec-02"]:
        if load(path / "trace-policy.json")["status"] != "PASS":
            errors.append(f"trace policy not PASS: {path}")
    document_checks=[]
    for path in sorted((ROOT / "docs/bug-reports-20261026").glob("*.md")):
        text=path.read_text(); links=[]; quotes=[]
        for label,target in re.findall(r"\[([^]]+)\]\(([^)]+)\)",text):
            if target.startswith(("http:","https:","#")):
                continue
            ok=(path.parent/target.split("#")[0]).resolve().exists()
            links.append(dict(target=target,valid=ok))
            if not ok:
                errors.append(f"broken report link: {path.name}: {target}")
        pattern=r"<!-- source: ([^:]+):(\d+)-(\d+) -->\s*```scala\n(.*?)\n```"
        for name,lo,hi,excerpt in re.findall(pattern,text,re.S):
            source=(ROOT.parent.parent/name).read_text().splitlines()
            ok=chr(10).join(source[int(lo)-1:int(hi)])==excerpt
            quotes.append(dict(file=name,lines=[int(lo),int(hi)],matched=ok))
            if not ok:
                errors.append(f"fixed-source excerpt mismatch: {path.name}:{name}:{lo}")
        document_checks.append(dict(file=str(path.relative_to(ROOT)),sha256=sha(path),links=links,source_excerpts=quotes))
    if len(document_checks)!=5:
        errors.append(f"expected five report files, got {len(document_checks)}")
    lock=load(ROOT/"manifest/toolchain.json")
    checkout=lock["toffee"]["checkout"]
    def git_ref(ref):
        return subprocess.check_output(["git","-C",checkout,"rev-parse",ref],text=True).strip()
    tool_refs=dict(checkout=checkout,branch=subprocess.check_output(
        ["git","-C",checkout,"branch","--show-current"],text=True).strip(),
        head=git_ref("HEAD"),local_origin_main=git_ref("refs/remotes/origin/main"),
        network_checked=False,locked_installed_package_version=lock["toffee"]["package_version"])
    report = dict(schema_version=1, date="2026-10-26", fixed_commit=COMMIT, final_run=RUN,
        evidence_consistency="PASS" if not errors else "FAIL", acceptance_passed=False,
        status="CONFIRMED_RTL_DEFECT_AND_EVIDENCE_LIMITS", outcomes=dict(outcomes),
        partitions={k:dict(v) for k,v in parts.items()}, known_rtl_defects=["LSU-HWPF-MISS-001"],
        historical_failures=history, historical_failures_fully_attributed=False,
        failed_nodes=failed, seed_runs=seed_runs, per_dut=delta,
        independent_reached_checked_complete=False, artifacts=artifacts,
        build_fingerprint_files=len(build_file_checks), fixed_rtl_files=source_checks, fixed_scala=fixed,
        execution_sources=execution_sources, post_run_reporting_source_changes=reporting_changes,
        report_documents=document_checks,local_toffee_refs=tool_refs,
        intermediate_reviews=intermediates,
        limitations=["17 historical FAIL observations have no original per-node traceback or source revision",
                    "manual functional bins are not independent reached/checked proof",
                    "readback controls cover one selected checker path per DUT, not exhaustive RTL mutation",
                    "random bit patterns are not all demonstrated legal transactions",
                    "prime remains an unchecked window; first-load no-prime control is bounded"], errors=errors)
    save(REVIEW / "final-audit.json", report)
    if args.sync_metadata:
        if errors:
            raise SystemExit("refuse metadata refresh because evidence audit failed")
        sync_metadata(report,after)
    print(json.dumps({k:report[k] for k in ("evidence_consistency","acceptance_passed","outcomes","partitions","errors")}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
