#!/usr/bin/env python3
"""Audit full RAR evidence, preserving failures as failures (never a PASS waiver)."""
import argparse
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def differences(actual, expected):
    result = []
    for key in ("ready", "full", "perf_fire", "perf_nuke"):
        if actual[key] != expected[key]:
            result.append(key)
    for lane, (got, want) in enumerate(zip(actual["responses"], expected["responses"], strict=True)):
        if got["valid"] != want["valid"]:
            result.append(f"response.{lane}.valid")
        if want["valid"] and got["nuke"] != want["nuke"]:
            result.append(f"response.{lane}.nuke")
    return result


def audit(name):
    run = ROOT / "results" / name
    manifest_path = run / "execution/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    assert manifest["pytest_exitstatus"] == 1, "this audit certifies evidence with known failures, never DUT acceptance"
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"], artifact["path"]
        if artifact["kind"] == "native":
            for path, digest in artifact["build"]["files"].items():
                assert sha(Path(path)) == digest, path
    source = json.loads((run / "source-evidence.json").read_text())
    for path, digest in source["files"].items():
        assert sha(run / "verification-source" / path) == digest, path
    issues = json.loads((run / "verification-source/manifest/known-issues.json").read_text())["issues"]
    issue = next(item for item in issues if item["id"] == "RAR-REL-001")
    assert issue["status"] == "open" and issue["not_a_waiver"]
    known = {case["nodeid"]: case for case in issue["failure_cases"]}
    xml = ET.parse(run / "pytest.xml").getroot()
    cases = list(xml.iter("testcase"))
    assert len(cases) == 54 and sum(manifest["tests"].values()) == len(cases)
    failed = {c.attrib["classname"].replace(".", "/") + ".py::" + c.attrib["name"] for c in cases if c.find("failure") is not None}
    assert failed == set(known) and manifest["tests"] == {"PASS": 47, "FAIL": 7}
    assert not list(xml.iter("skipped")) and not list(xml.iter("error"))
    audit_path = run / "line-audit.json"
    line_audit = json.loads(audit_path.read_text())
    assert line_audit["run"] == name and line_audit["tests"] == manifest["tests"]
    assert len(line_audit["native"]) == 1
    native = line_audit["native"][0]
    assert native["dut"] == "load_queue_rar" and native["closure_line_hit"] == native["closure_line_total"] == 5320
    assert native["line_hit"] == native["line_total"] == 3898 and not native["uncovered"]
    assert all(not dep["uncovered"] for dep in native["dependencies"])
    native_ids = {a["build"]["build_id"] for a in manifest["artifacts"] if a["kind"] == "native"}
    assert native_ids == {native["build_id"]}
    functional = json.loads((run / "execution/functional-coverage.json").read_text())
    groups = {group["instance"].rsplit(".", 1)[-1]: group for group in functional["groups"]}
    assert set(groups) == {"reached", "checked"}
    for group in groups.values():
        assert group["collection_complete"] and not group["points"][0]["unknown"] and not group["points"][0]["unmatched"]
    reached, checked = (groups[k]["points"][0]["counts"] for k in ("reached", "checked"))
    assert len(reached) == len(checked) == 55 and all(reached.values())
    assert all(0 <= checked[key] <= reached[key] for key in reached)
    missing = [key for key, count in checked.items() if not count]
    assert set(missing) == set(issue["unpassed_scenarios"])
    journals = sorted((run / "cases").rglob("load_queue_rar.jsonl"))
    assert len(journals) == len(cases)
    rows, failures, allocated_pairs, proven_pairs = [], [], Counter(), Counter()
    for path in journals:
        records = [json.loads(line) for line in path.read_text().splitlines()]
        counters = Counter(records=0, checked=0, reset_edges=0, queries=0, query_fires=0, allocations=0,
                           frees=0, nuke_responses=0, release_inputs=0, redirect_inputs=0, unique_positive_probes=0)
        reset_length, last_tick, previous_fire = 0, None, 0
        nuke_history = deque((0, 0))
        owned, ever_proven, entry_lane = set(), set(), {}
        errors = []
        for index, record in enumerate(records):
            counters["records"] += 1
            assert record["pre_tick"] + 1 == record["post_tick"]
            if last_tick is not None:
                assert record["post_tick"] == last_tick + 2, "globally observed cycle omitted"
            last_tick = record["post_tick"]
            inp, before, after = record["input"], record["before"], record["after"]
            assert inp == record["post_input"], "driver restore must not precede passive sampling"
            if inp["reset"]:
                assert not record["checked"] and "error" not in record
                counters["reset_edges"] += 1
                reset_length += 1
                owned.clear()
                previous_fire, nuke_history = 0, deque((0, 0))
                continue
            if reset_length:
                assert reset_length >= 6
                reset_length = 0
            assert not differences(before, record["expected_before"])
            # These three pipeline checks use actual input/output history,
            # not the model's retained response/perf transaction objects.
            assert [r["valid"] for r in after["responses"]] == [q["valid"] for q in inp["queries"]]
            assert after["perf_fire"] == previous_fire
            assert after["perf_nuke"] == nuke_history.popleft()
            fires = sum(q["valid"] and before["ready"][lane] for lane, q in enumerate(inp["queries"]))
            previous_fire = fires
            nuke_history.append(sum(r["valid"] and r["nuke"] for r in after["responses"]))
            change = record["change"]
            assert {e["uid"] for e in change["before"]} == owned
            freed = {f["item"]["uid"] for f in change["freed"]}
            assert len(freed) == len(change["freed"]) and freed <= owned
            owned.difference_update(freed)
            for entry in change["allocated"]:
                uid, slot = entry["uid"], entry["slot"]
                assert uid not in owned
                owned.add(uid)
                lane = change["accepted"].index(uid)
                entry_lane[uid] = (lane, slot)
                allocated_pairs[(lane, slot)] += 1
            expected_difference = differences(after, record["expected_after"])
            if "error" in record:
                assert index == len(records) - 1 and not record["checked"]
                assert expected_difference == ["response.0.nuke"] and "response.nuke" in record["error"]
                allocations = [(i, e) for i, previous in enumerate(records[:-1]) for e in previous.get("change", {}).get("allocated", [])]
                assert len(allocations) == 1
                alloc_index, entry = allocations[0]
                releases = [i for i, previous in enumerate(records) if previous["input"]["release"]["valid"]]
                assert len(releases) == 1
                allocation = records[alloc_index]
                lane = allocation["change"]["accepted"].index(entry["uid"])
                signature = dict(allocation_lane=lane, distance=alloc_index - releases[0],
                                 expected_nuke=record["expected_after"]["responses"][0]["nuke"],
                                 actual_nuke=after["responses"][0]["nuke"])
                match = [node for node, case in known.items() if all(case[key] == value for key, value in signature.items())]
                # lane1/distance1 has two intentional repros: choose by the
                # actual long parameterized test name retained in pytest's log.
                assert match
                errors.append({**signature, "tick": record["post_tick"], "issue": issue["id"]})
                failures.append({"journal": str(path.relative_to(run)), **errors[-1]})
            else:
                assert record["checked"] and not expected_difference
                counters["checked"] += 1
                for lane, matched in enumerate(change["matches"]):
                    if len(matched) == 1 and after["responses"][lane]["valid"] and after["responses"][lane]["nuke"]:
                        uid = matched[0]
                        if uid not in ever_proven:
                            ever_proven.add(uid)
                            proven_pairs[entry_lane[uid]] += 1
                        counters["unique_positive_probes"] += 1
            counters["queries"] += sum(q["valid"] for q in inp["queries"])
            counters["query_fires"] += fires
            counters["allocations"] += len(change["allocated"])
            counters["frees"] += len(change["freed"])
            counters["nuke_responses"] += sum(r["valid"] and r["nuke"] for r in after["responses"])
            counters["release_inputs"] += inp["release"]["valid"]
            counters["redirect_inputs"] += inp["redirect"]["valid"]
        rows.append({"journal": str(path.relative_to(run)), "sha256": sha(path), "errors": errors, **dict(counters)})
    assert len(failures) == 7
    signatures = Counter((f["allocation_lane"], f["distance"], f["expected_nuke"], f["actual_nuke"]) for f in failures)
    assert signatures == Counter((c["allocation_lane"], c["distance"], c["expected_nuke"], c["actual_nuke"]) for c in known.values())
    assert set(allocated_pairs) == set(proven_pairs) == {(lane, slot) for lane in range(3) for slot in range(96)}
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/coverage_audit.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool), "do not overwrite historical auditor"
        else:
            shutil.copy2(tool, dest)
        auditors[str(dest.relative_to(run))] = sha(dest)
    report = {"run": name, "status": "evidence_audited_with_failures", "dut_acceptance": "NOT_PASS",
              "issue": issue["id"], "tests": manifest["tests"], "manifest_sha256": sha(manifest_path),
              "line_audit_sha256": sha(audit_path), "source_snapshot_files": len(source["files"]),
              "reached": 55, "checked": 52, "unpassed_scenarios": missing, "auditors": auditors,
              "scope": "all committed hashes, continuous public-pin journals, strict comparisons, response/perf input-history and recorded ownership; known failures not waived",
              "totals": {key: sum(row[key] for row in rows) for key in counters},
              "allocation_lane_slot_pairs": len(allocated_pairs), "uniquely_proven_lane_slot_pairs": len(proven_pairs),
              "failures": failures, "cases": rows}
    output = run / "trace-audit.json"
    if output.exists():
        assert json.loads(output.read_text()) == report, "refusing to overwrite a different audit"
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("cases", "failures")}, indent=2, ensure_ascii=False))
    print("failure/case details:", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
