#!/usr/bin/env python3
"""Exact1808-case,38-DUT repeat: old36 + real LoadQueue + real Wrapper.

Historical basic87 cases have no persisted cycle JSON journal. Report their
node/result/native/functional/source checks, never invent a per-node raw trace.
All other1721 cases compare the complete canonical raw-history multiset, with
separate exact node/results; explicit node maps are only claimed where present.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

from audit_lsq_population_v1 import events
from audit_progress_run_v5 import FAMILIES as OLD_FAMILIES
from audit_sq_initial import ROOT, sha, verify_common


FAMILIES = {**OLD_FAMILIES, "load_queue": 199, "lsq_wrapper": 297}
JOURNALS = dict(vlq=("virtual_load_queue.jsonl",), rar=("load_queue_rar.jsonl",), raw=("load_queue_raw.jsonl",),
                uncache_entry=tuple(f"uncache_entry_{i}.jsonl" for i in range(16)),
                load_uncache=("load_queue_uncache.jsonl",), replay=("load_queue_replay.jsonl",),
                enter_sbuffer=("enter_sbuffer_queue.jsonl",), unalign=("unalign_queue.jsonl",),
                forward=("forward_module.jsonl",), vsq=("virtual_store_queue.jsonl",),
                deq=("deq_module.jsonl", "deq_full.jsonl"), psq=("physical_store_queue.jsonl", "psq_full.jsonl"),
                store_queue=("store_queue.jsonl",), load_queue=("load_queue.jsonl",),
                lsq_wrapper=("lsq_wrapper.jsonl", "lsq_probe.jsonl"))
RAW = ("pre_tick", "post_tick", "input", "post_input", "pins", "post_pins", "before", "after")


def histories(directory, family):
    traces, by_node = Counter(), {}
    for filename in JOURNALS.get(family, ()):
        for path in (directory / "cases").rglob(filename):
            digest, count, previous, node = hashlib.sha256(), 0, None, None
            for row in events(path):
                assert all(key in row for key in ("pre_tick", "post_tick", "before", "after"))
                assert "input" in row or "inputs" in row["before"]
                assert row["pre_tick"]+1 == row["post_tick"]
                assert previous is None or previous+2 == row["post_tick"]
                previous = row["post_tick"]
                if count == 0:
                    node = row.get("nodeid")
                if node is not None:
                    assert row["nodeid"] == node
                data = {key: row[key] for key in RAW if key in row}
                digest.update(json.dumps(data, sort_keys=True, separators=(",", ":")).encode())
                digest.update(b"\n")
                count += 1
            assert count
            key = (digest.hexdigest(), count)
            traces[key] += 1
            if node is not None:
                assert node not in by_node
                by_node[node] = key
    return traces, by_node


def primary(message):
    # Only Python object addresses vary between processes. Do NOT normalize
    # arbitrary hex payloads or actual result fields.
    return re.sub(r"\bat 0x[0-9a-fA-F]+\b", "at <process-address>", message)


def failures(directory):
    result = {}
    for case in ET.parse(directory / "pytest.xml").iter("testcase"):
        failure = case.find("failure")
        if failure is not None:
            node = case.attrib["classname"].replace(".", "/")+".py::"+case.attrib["name"]
            result[node] = primary(failure.attrib["message"])
    return result


def audit(name):
    assert name == "lsq-progress-regression-07", "fixed1808 scope, not future mixed stress"
    run = ROOT / "results" / name
    manifest, source, nodes = verify_common(run)
    assert manifest["tests"] == {"PASS": 1649, "FAIL": 159} and len(nodes) == sum(FAMILIES.values()) == 1808
    assert len(source) == 350
    command = json.loads((run / "command.json").read_text())["command"]
    assert "tests" in command and not any(arg == "-k" or arg.startswith("--deselect") for arg in command)
    directories = {family: ROOT / "results" / ("lsq-expanded-14" if family == "lsq_wrapper" else "lq-expanded-06" if family == "load_queue" else "lsq-progress-regression-06") for family in FAMILIES}
    previous = {d: verify_common(d) for d in set(directories.values())}
    old_nodes, old_failures = {}, {}
    current_failures = failures(run)
    reports, total, mapped = [], 0, 0
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
        if family in JOURNALS:
            assert count == len(current)
        else:
            assert family in ("age", "cam", "freelist") and count == 0
        records = sum(length*copies for (_, length), copies in after.items())
        total += records
        mapped += len(after_nodes)
        reports.append(dict(family=family, prior=directory.name, cases=len(current), tests=dict(Counter("FAIL" if v else "PASS" for v in current.values())),
                            actual_raw_journals_equal=count, actual_raw_records_equal=records, exact_node_raw_mappings=len(after_nodes),
                            raw_trace_sha256_multiset=[dict(sha256=digest, records=length, count=copies) for (digest, length), copies in sorted(after.items())],
                            history_limit="basic fixture has continuous runtime checks but no persisted cycle JSON journal; node/results/native/functional/source only" if not count else "complete per-family raw multiset; exact node mapping only for journals retaining nodeid"))
    assert nodes == old_nodes and current_failures == old_failures and len(current_failures) == 159
    assert sum(r["actual_raw_journals_equal"] for r in reports) == 1721
    lines = json.loads((run / "line-audit.json").read_text())
    native = {r["dut"]: r for r in lines["native"]}
    builds = {a["build"]["build_id"] for a in manifest["artifacts"] if a["kind"] == "native"}
    assert len(native) == len(builds) == 38 and builds == {r["build_id"] for r in native.values()}
    baselines = {}
    for directory in previous:
        for row in json.loads((directory / "line-audit.json").read_text())["native"]:
            assert row["dut"] not in baselines
            baselines[row["dut"]] = row
    assert native.keys() == baselines.keys()
    for dut, row in native.items():
        old = baselines[dut]
        assert row["source_sha256"] == old["source_sha256"]
        assert all(row[key] == old[key] for key in ("line_hit", "line_total", "closure_line_hit", "closure_line_total"))
        assert {g["line"] for g in row["uncovered"]} == {g["line"] for g in old["uncovered"]}
    groups = {g["instance"]: g for g in json.loads((run / "execution/functional-coverage.json").read_text())["groups"]}
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
    for path in (run / "verification-source/tests").rglob("*.py"):
        assert not re.search(r"pytest\.(?:mark\.)?(?:xfail|skip)\b", path.read_text())
    dest = run / "evidence-auditors"
    dest.mkdir(exist_ok=True)
    files = (Path(__file__), ROOT/"tools/audit_sq_initial.py", ROOT/"tools/audit_progress_run_v5.py", ROOT/"tools/audit_lsq_population_v1.py")
    for file in files:
        target = dest/file.name
        if target.exists():
            assert sha(target) == sha(file)
        else:
            shutil.copy2(file, target)
    result = dict(run=name, status="NOT_PASS_1808_cases_38_real_native_DUTs_exact_frozen_results_and_histories_verified", tests=manifest["tests"],
                  source_snapshot_files=len(source), native_builds=len(builds), functional_groups=len(groups), actual_raw_journals_equal=1721,
                  actual_raw_records_equal=total, exact_node_raw_mappings=mapped, basic87_without_persisted_cycle_journal=87,
                  every_failure_primary_signature_equal_after_process_address_normalization=True,
                  source_baseline_reports={d.name: sha(d/"execution/manifest.json") for d in previous},
                  missing_semantic_scenarios=missing, families=reports,
                  manifest_sha256=sha(run/"execution/manifest.json"), auditors={file.name: sha(dest/file.name) for file in files},
                  limits="All currently implemented1808 cases/38 native DUTs, including actual LoadQueue199 and Wrapper297. All159 ordinary FAIL and all outcomes equal independently frozen36-DUT1312+LoadQueue199+Wrapper297 union. Complete1721 raw trace SHA multisets and available exact node maps match; basic87 fixtures have no persisted cycle journal and are NOT given fictional raw-history evidence. Each native DUT keeps its own coverage and failures; no independent-leaf coverage merged into Wrapper. This is a full current-scope uniform repeat, not future missing mixed-domain seeded/coupled-capacity/fair-drain acceptance, all-child strict signoff or final goal completion.")
    output = run / "evidence-check-v7.json"
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
