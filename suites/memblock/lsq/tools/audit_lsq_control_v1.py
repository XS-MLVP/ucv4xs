#!/usr/bin/env python3
"""Preserve the overstrict same-VA helper rejection and prove real completion.

The original failed samples must be an exact prefix of the corrected case;
only the illegal expectation of immediate unblocked forwarding is rejected.
The real alias/PA-byte safety failures are NOT removed or reclassified.
"""
import argparse
import json
from pathlib import Path
import shutil

from audit_lsq_bus_v2 import rows
from audit_lsq_bus_v3 import differences
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    run, old = ROOT / "results" / name, ROOT / "results/lsq-expanded-05"
    manifest, _, nodes = verify_common(run)
    original, _, old_nodes = verify_common(old)
    assert original["tests"] == {"PASS": 104, "FAIL": 28} and manifest["tests"] == {"PASS": 107, "FAIL": 25}
    assert set(nodes) == set(old_nodes) and len(nodes) == 132
    corrected = {node for node in nodes if old_nodes[node] and not nodes[node]}
    assert len(corrected) == 3 and all("same-va-control" in node for node in corrected)
    assert {node for node, failed in nodes.items() if failed} == {node for node, failed in old_nodes.items() if failed} - corrected
    by_node = lambda directory: {rows(path)[0]["nodeid"]: path for path in (directory / "cases").rglob("lsq_wrapper.jsonl")}
    old_paths, paths = by_node(old), by_node(run)
    memory_path = run / "memory-history-audit-v1.json"
    memory = json.loads(memory_path.read_text())
    assert memory["tests"] == manifest["tests"]
    evidence = {case["nodeid"]: case for case in memory["cases"]}
    cases = []
    for node in sorted(corrected):
        prior, current = rows(old_paths[node]), rows(paths[node])
        assert len(current) > len(prior) and all(row["checked"] and not any(differences(row).values()) for row in prior)
        assert all(all(a[key] == b[key] for key in ("pre_tick", "post_tick", "input", "pins", "post_pins", "before", "after")) for a, b in zip(prior, current[:len(prior)], strict=True))
        rejected = [check for check in rows(old_paths[node].with_name("lsq_checks.jsonl")) if not check["passed"]]
        assert len(rejected) == 1
        rejection = rejected[0]
        different = {key: [rejection["actual"][key], want] for key, want in rejection["expected"].items() if rejection["actual"][key] != want}
        assert len(different) == 1
        pin = next(iter(different))
        assert pin.endswith("s2Resp_bits_forwardInvalid") and different[pin] == [1, 0]
        assert prior[-1]["expected_after"][pin] == prior[-1]["after"][pin] == 1
        accepted = evidence[node]
        assert accepted["result"] == "PASS" and accepted["allocated"] == accepted["completed"] == 3
        assert accepted["cancelled"] == accepted["failure_retained"] == 0 and not accepted["violations"]
        grants = sum(row["before"][f"io_replay_{bank}_valid"] and row["input"]["replay_ready"][bank] for row in current for bank in range(3))
        fragments = sum(row["before"][f"io_sbuffer_req_{lane}_valid"] and row["input"]["sbuffer_ready"][lane] for row in current for lane in range(2))
        assert grants == 1 and fragments == 3
        cases.append(dict(nodeid=node, old_trace_sha256=sha(old_paths[node]), new_trace_sha256=sha(paths[node]),
                          original_raw_samples_exact_prefix=len(prior), original_overstrict_rejected_assertion=different,
                          real_multi_match_replay_grants=grants, actual_original_store_fragments=fragments,
                          completed_original_uids=3))
    dest = run / "evidence-auditors" / Path(__file__).name
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = dict(run=name, original_run=old.name, status="three_overstrict_directed_helper_assertions_corrected_not_RTL_waivers",
                  tests=manifest["tests"], original_tests=original["tests"], cases=cases, auditor_sha256=sha(dest),
                  independent_memory_audit_sha256=sha(memory_path),
                  source_versions={str(relative): {label: sha(directory / "verification-source" / relative) for label, directory in (("original", old), ("corrected", run))}
                                   for relative in (Path("tests/lsq_wrapper/test_forward_memory.py"), Path("tests/lsq_wrapper/memory_owners.py"))},
                  limits="Original132 run/source/28 failures retained. Three same-VA controls follow actual conservative multi-match block through real replay/SQ empty/S3; no PA safety condition is weakened. All other25 failing node IDs retained, including three different-VA alias, six range, three full SQ identity and three previous-release failures plus old10 bus/SID. Address-wait metadata was also aligned between its original Load uop and queries; not a DUT or missing internal feedback edit.")
    output = run / "control-helper-correction-audit-v1.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
