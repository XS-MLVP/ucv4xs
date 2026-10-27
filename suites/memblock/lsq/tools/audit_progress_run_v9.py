#!/usr/bin/env python3
"""Exact1828-case/38-DUT repeat after original mixed14 and joint6 additions.

Preserve all v7/v8 reports and scope gates. Reuse raw history/failure and full
LCOV-set helpers unchanged; only explicitly enlarge the required Wrapper set.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import shutil

from audit_progress_run_v7 import FAMILIES as OLD_FAMILIES, JOURNALS, failures, histories
from audit_sq_initial import ROOT, sha, verify_common
from coverage_audit import lcov


FAMILIES = {**OLD_FAMILIES,"lsq_wrapper":317}


def coverage_signature(row):
    entries = (row, *row.get("dependencies", []))
    hit, total = sum(e["line_hit"] for e in entries), sum(e["line_total"] for e in entries)
    if row.get("dependencies"):
        assert row["closure_line_hit"] == hit and row["closure_line_total"] == total
    else:
        assert "closure_line_hit" not in row and "closure_line_total" not in row
    tables = lcov(ROOT / row["lcov"])
    answer = {}
    for entry in entries:
        path = entry["source"]
        digest = entry.get("source_sha256", entry.get("sha256"))
        assert sha(ROOT/path) == digest
        counts = tables.get(str(ROOT/path), {})
        assert len(counts) == entry["line_total"] and sum(bool(n) for n in counts.values()) == entry["line_hit"]
        assert {n for n, count in counts.items() if not count} == {gap["line"] for gap in entry["uncovered"]}
        answer[path] = (digest, tuple(sorted((line, bool(count)) for line, count in counts.items())))
    return answer


def audit(name):
    assert name == "lsq-progress-regression-08", "exact1828 case/38 native DUT scope"
    run = ROOT/"results"/name
    manifest, source, nodes = verify_common(run)
    assert manifest["tests"] == {"PASS": 1658, "FAIL": 170} and len(nodes) == sum(FAMILIES.values()) == 1828 and len(source) >= 364
    assert "tests/lsq_wrapper/test_joint_capacity.py" in source and "tests/lsq_wrapper/test_seeded_mixed.py" in source
    command = json.loads((run/"command.json").read_text())["command"]
    assert "tests" in command and not any(arg == "-k" or arg.startswith("--deselect") for arg in command)
    directories = {family: ROOT/"results"/("lsq-expanded-16" if family == "lsq_wrapper" else "lq-joint-impact-02" if family == "load_queue" else "lsq-progress-regression-06") for family in FAMILIES}
    previous = {d: verify_common(d) for d in set(directories.values())}
    old_nodes, old_failures, reports, total, mapped = {}, {}, [], 0, 0
    for family, directory in directories.items():
        prior = {n: failed for n, failed in previous[directory][2].items() if n.startswith(f"tests/{family}/")}
        current = {n: failed for n, failed in nodes.items() if n.startswith(f"tests/{family}/")}
        assert prior == current and len(current) == FAMILIES[family]
        old_nodes.update(prior)
        old_failures.update({n: message for n, message in failures(directory).items() if n.startswith(f"tests/{family}/")})
        before, before_nodes = histories(directory, family)
        after, after_nodes = histories(run, family)
        assert before == after and before_nodes == after_nodes, (family, "changed raw native history")
        count = sum(after.values())
        assert count == len(current) if family in JOURNALS else family in ("age", "cam", "freelist") and count == 0
        records = sum(length*copies for (_, length), copies in after.items())
        total += records
        mapped += len(after_nodes)
        reports.append(dict(family=family, prior=directory.name, cases=len(current), tests=dict(Counter("FAIL" if v else "PASS" for v in current.values())),
                            actual_raw_journals_equal=count, actual_raw_records_equal=records, exact_node_raw_mappings=len(after_nodes),
                            raw_trace_sha256_multiset=[dict(sha256=digest, records=length, count=copies) for (digest, length), copies in sorted(after.items())],
                            history_limit="basic fixture has continuous runtime checks but no persisted cycle JSON journal; node/results/native/functional/source only" if not count else "complete per-family raw multiset; exact node mapping only for journals retaining nodeid"))
    assert nodes == old_nodes and failures(run) == old_failures and len(old_failures) == 170
    assert sum(r["actual_raw_journals_equal"] for r in reports) == 1741 and total==284165 and mapped==979
    native = {r["dut"]: r for r in json.loads((run/"line-audit.json").read_text())["native"]}
    builds = {a["build"]["build_id"] for a in manifest["artifacts"] if a["kind"] == "native"}
    assert len(native) == len(builds) == 38 and builds == {r["build_id"] for r in native.values()}
    baselines = {}
    for directory in previous:
        for row in json.loads((directory/"line-audit.json").read_text())["native"]:
            assert row["dut"] not in baselines
            baselines[row["dut"]] = row
    assert native.keys() == baselines.keys()
    for dut, row in native.items():
        assert coverage_signature(row) == coverage_signature(baselines[dut]), (dut, "changed original DA universe/hit set")
    groups = {g["instance"]: g for g in json.loads((run/"execution/functional-coverage.json").read_text())["groups"]}
    assert len(groups) == 76
    missing = {}
    for instance, group in groups.items():
        point = group["points"][0]
        assert group["collection_complete"] and not point["unknown"] and not point["unmatched"]
        if instance.endswith("checked"):
            reached = groups[instance.removesuffix("checked")+"reached"]["points"][0]["counts"]
            assert all(count <= reached[key] for key, count in point["counts"].items())
        absent = [key for key, count in point["counts"].items() if not count]
        if absent:
            missing[instance] = absent
    for path in (run/"verification-source/tests").rglob("*.py"):
        assert not re.search(r"pytest\.(?:mark\.)?(?:xfail|skip)\b", path.read_text())
    dest = run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__), ROOT/"tools/audit_progress_run_v8.py", ROOT/"tools/audit_progress_run_v7.py", ROOT/"tools/audit_sq_initial.py", ROOT/"tools/audit_progress_run_v5.py", ROOT/"tools/audit_lsq_population_v1.py", ROOT/"tools/coverage_audit.py")
    for file in files:
        target = dest/file.name
        if target.exists():
            assert sha(target) == sha(file)
        else:
            shutil.copy2(file, target)
    result = dict(run=name, status="NOT_PASS_1828_cases_38_real_native_DUTs_exact_frozen_results_and_histories_verified", tests=manifest["tests"],
                  source_snapshot_files=len(source), native_builds=len(builds), functional_groups=len(groups), actual_raw_journals_equal=1741,
                  actual_raw_records_equal=total, exact_node_raw_mappings=mapped, basic87_without_persisted_cycle_journal=87,
                  every_failure_primary_signature_equal_after_process_address_normalization=True,
                  each_DUT_original_DA_universe_and_hit_set_equal_its_frozen_baseline=True,
                  source_baseline_reports={d.name: sha(d/"execution/manifest.json") for d in previous},
                  missing_semantic_scenarios=missing, families=reports,
                  v7_preserved_failure=dict(error="KeyError: closure_line_hit", cause="coverage_audit deliberately omits redundant closure keys on leaf rows; v7 required them unconditionally", original_auditor_sha256=sha(dest/"audit_progress_run_v7.py"),
                                             correction="v8 uses the unchanged v7 raw-history/node/failure cores and validates every actual LCOV DA source/line/hit set; no outcome, domain or stimulus changed"),
                  manifest_sha256=sha(run/"execution/manifest.json"), auditors={file.name: sha(dest/file.name) for file in files},
                  limits="All currently implemented1828 cases/38 native DUTs, including actual LoadQueue199 and Wrapper317. All170 ordinary FAIL and every outcome equal frozen36-DUT1312+LoadQueue199+Wrapper317 union. Complete1741 raw trace SHA multisets/284165 records and979 available exact node maps match; basic87 fixtures have no persisted cycle journal and are NOT given fictional raw-history evidence. Every native DUT original DA universe and hit set matches its own baseline, never merged across independent DUTs. Supplemental six clean coupled directed cases really reach fair service but do NOT replace eight full-domain mixed first-failure prefixes or make STRESS checked. No all-child strict signoff, complete random or final goal completion claim.")
    output = run/"evidence-check-v9.json"
    if output.exists():
        assert json.loads(output.read_text()) == result
    else:
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps({**{k: v for k, v in result.items() if k != "families"},
                      "families": [{k: v for k, v in r.items() if k != "raw_trace_sha256_multiset"} for r in reports]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
