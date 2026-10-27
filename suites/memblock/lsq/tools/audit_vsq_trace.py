#!/usr/bin/env python3
"""Public-only VSQ lifecycle/permission audit; no reference-model imports.

Reconstructs ordered uops, exclusive physical intervals, two-stage retirement
events, ROB head capture/release/walk, redirect responses and canceled-slot
reuse. It also verifies every recorded detailed pin comparison and every
functional-proof UID/provenance. It does not claim general formal proof.
"""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sq(ptr):
    assert 0 <= ptr["value"] < 64
    return 128 * ptr["first"] + 64 * ptr["second"] + ptr["value"]


def output_sq(pins, prefix):
    return 128 * pins[prefix + "first_flag"] + 64 * pins[prefix + "second_flag"] + pins[prefix + "value"]


def order(ptr, anchor):
    assert 0 <= ptr["value"] < 160
    raw = 2 * (160 * ptr["flag"] + ptr["value"]) + int(not ptr["former"])
    if anchor is None:
        return raw
    values = [raw + 640 * ((anchor - raw) // 640 + offset) for offset in (0, 1)]
    assert abs(values[0] - anchor) != abs(values[1] - anchor)
    return min(values, key=lambda value: abs(value - anchor))


def frozen_tests(snapshot):
    expected = Counter()
    for path in (snapshot / "tests/vsq").glob("test_*.py"):
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            count = 1
            for deco in node.decorator_list:
                if isinstance(deco, ast.Call) and isinstance(deco.func, ast.Attribute) and deco.func.attr == "parametrize":
                    arg = deco.args[1]
                    count *= len(range(*(ast.literal_eval(v) for v in arg.args))) if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) and arg.func.id == "range" else len(ast.literal_eval(arg))
            expected[f"tests/vsq/{path.name}::{node.name}"] = count
    return expected


def audit(name):
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            assert all(sha(Path(path)) == digest for path, digest in artifact["build"]["files"].items())
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    end = json.loads((run / "end-source-check.json").read_text())
    assert end["all_current_launch_files_match_snapshot"] and end["files"] == source
    command = json.loads((run / "command.json").read_text())["command"]
    assert "tests/vsq" in command and "-k" not in command and not any(arg.startswith("--deselect") for arg in command)
    tests = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert all(case.find("error") is None and case.find("skipped") is None for case in tests)
    nodes = [case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"] for case in tests]
    assert len(nodes) == len(set(nodes)) and Counter(node.split("[", 1)[0] for node in nodes) == frozen_tests(run / "verification-source")
    failures = {node for node, case in zip(nodes, tests, strict=True) if case.find("failure") is not None}
    assert manifest["tests"] == {"PASS": len(nodes) - len(failures), "FAIL": len(failures)}
    issues = [issue for issue in json.loads((run / "verification-source/manifest/known-issues.json").read_text())["issues"] if issue["dut"] == "virtual_store_queue"]
    assert len(issues) == 1 and issues[0]["id"] == "VSQ-REDIR-IF-001" and issues[0]["not_a_waiver"]
    assert failures == set(issues[0]["failure_cases"])
    line = json.loads((run / "line-audit.json").read_text())
    assert len(line["native"]) == 1 and line["native"][0]["dut"] == "virtual_store_queue"
    assert line["native"][0]["line_hit"] == line["native"][0]["line_total"] == 3125 and not line["native"][0]["uncovered"]
    functional = json.loads((run / "execution/functional-coverage.json").read_text())
    groups = {group["instance"].rsplit(".", 1)[-1]: group for group in functional["groups"]}
    assert set(groups) == {"reached", "checked"} and all(group["collection_complete"] for group in groups.values())
    reached, checked = (groups[key]["points"][0]["counts"] for key in ("reached", "checked"))
    assert set(reached) == set(checked) and len(checked) == 55 and all(reached.values())
    assert {key for key, count in checked.items() if not count} == {"VSQ-RACE.dispatch_redirect"}
    assert all(count <= reached[key] for key, count in checked.items())
    files = sorted((run / "cases").rglob("virtual_store_queue.jsonl"))
    assert len(files) == len(nodes)
    totals, cases, error_rows, tuples, canceled_reuse, samples, seen = Counter(), [], [], {}, [], {}, set()
    for path in files:
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        nodeid = rows[0]["nodeid"]
        assert nodeid in nodes and nodeid not in seen
        seen.add(nodeid)
        active, all_items, positions, recovered, retired_pending = {}, {}, {}, {}, ()
        allocation_order = []
        allocated, retired, canceled, aborted = set(), set(), set(), set()
        sequence = virtual_head = virtual_tail = physical_end = retired_end = physical_tail = 0
        anchor, rob_head, redirect = None, {"flag": False, "value": 0, "former": True}, {"valid": False}
        state, prior_recovery, latest_precommit = "idle", None, None
        histories, counts, tick, edge, reuse_pending = {}, Counter(), None, 0, []
        for index, row in enumerate(rows):
            edge += 1
            counts["records"] += 1
            assert row["nodeid"] == nodeid and row["input"] == row["post_input"]
            assert row["pre_tick"] + 1 == row["post_tick"] and (tick is None or tick + 2 == row["post_tick"])
            tick, inp, change, post = row["post_tick"], row["input"], row.get("change"), row["after"]
            differences = {phase: {key: [row[phase][key], value] for key, value in row.get(f"expected_{'before' if phase == 'before' else 'after'}", {}).items() if row[phase][key] != value} for phase in ("before", "after")}
            failed = any(differences.values())
            if failed:
                assert index == len(rows) - 1 and nodeid in failures and "error" in row and not row["checked"]
                assert not differences["before"]
                assert differences["after"] == {"io_toPhysicalQueue_redirectPtr_bits_value": [2, 1]}
                error_rows.append({"nodeid": nodeid, "journal": str(path.relative_to(run)), "sha256": sha(path), "tick": tick,
                                   "issue": "VSQ-REDIR-IF-001", "domain": "UNIT-INTERFACE-only", "differences": differences["after"]})
            else:
                assert "error" not in row
                counts["checked_edges"] += row["checked"]
            if inp["reset"]:
                expected_aborted = allocated - retired - canceled - aborted
                assert change["reset_aborted"] == sorted(expected_aborted)
                aborted.update(expected_aborted)
                active, positions, recovered = {}, {}, {}
                allocation_order, retired_pending, prior_recovery, latest_precommit = [], (), None, None
                virtual_head = virtual_tail = physical_end = retired_end = physical_tail = 0
                anchor, rob_head, redirect, state = None, inp["rob_head"], {"valid": False}, "idle"
                assert not change["accepted"] and not change["canceled"] and not change["retired"]
                assert row["before"]["io_empty"] and not row["before"]["io_sqRecoverStall"] and not row["before"]["io_toPhysicalQueue_redirectPtr_valid"]
            else:
                effective = state == "walk" or state == "idle" and redirect["valid"]
                head_order = order(rob_head, anchor)
                head_is_retired = virtual_head in active and active[virtual_head]["order"] < head_order
                next_state = ("release" if inp["redirect"]["valid"] and head_is_retired else "idle") if state == "idle" else (
                    "walk" if not head_is_retired else "release") if state == "release" else "idle"
                prepared = []
                for offset in range(8):
                    item = active.get(virtual_head + offset)
                    if item is None:
                        break
                    consumed = offset < 2 and inp["consumed"] and (sq(inp["physical_deq"]) - item["end"]) % 256 < 128
                    if item["order"] >= head_order and not consumed:
                        break
                    prepared.append(item)
                expected_retired = list(retired_pending)
                assert change["retired"] == expected_retired
                for item in expected_retired:
                    assert item["uid"] not in retired | canceled | aborted
                    retired.add(item["uid"])
                    retired_end += item["flows"]
                    key = f"{item['lane']}:{item['position'] % 128}"
                    tuples.setdefault(key, {"nodeid": nodeid, "uid": item["uid"], "end": item["end"], "tick": tick,
                                            "journal": str(path.relative_to(run)), "sha256": sha(path)})
                    for old in reuse_pending:
                        if old["new_uid"] is None and old["position"] % 128 == item["position"] % 128 and item["uid"] > old["old_uid"]:
                            old.update(new_uid=item["uid"], retire_tick=tick)
                canceled_now = []
                if effective:
                    cutoff = order(redirect["rob"], anchor)
                    canceled_now = [item for pos, item in sorted(active.items()) if item["order"] > cutoff or redirect["flush_self"] and item["order"] == cutoff]
                    assert change["canceled"] == canceled_now
                    for item in canceled_now:
                        assert item["uid"] not in retired | canceled | aborted
                        canceled.add(item["uid"])
                        if not item["uid"] in {prepared_item["uid"] for prepared_item in prepared}:
                            reuse_pending.append({"old_uid": item["uid"], "position": item["position"], "new_uid": None, "cancel_tick": tick})
                    gone = {item["uid"] for item in canceled_now}
                    allocation_order = [item for item in allocation_order if item["uid"] not in gone]
                    virtual_tail -= len(canceled_now)
                    recovered[edge + 2] = allocation_order[-1]["end"] if allocation_order else 0
                else:
                    assert not change["canceled"]
                for item in change["precommitted"]:
                    assert item["position"] in active and item == active[item["position"]] and item["order"] == head_order
                    latest_precommit = item
                for item in (*prepared, *canceled_now):
                    active.pop(item["position"], None)
                virtual_head += len(retired_pending)
                retired_pending = tuple(prepared)
                expected_accepted = []
                for lane, req in enumerate(inp["dispatch"]):
                    if not req["valid"] or not req["need_alloc"] or inp["redirect"]["valid"]:
                        continue
                    assert 0 <= req["flows"] <= 16
                    physical_end += req["flows"]
                    assert sq(req["end"]) == physical_end % 256
                    rob_order = order(req["rob"], anchor)
                    anchor = rob_order if anchor is None else max(anchor, rob_order)
                    sequence += 1
                    item = {"uid": sequence, "position": virtual_tail, "lane": lane, "rob": req["rob"], "order": rob_order, "flows": req["flows"], "end": physical_end}
                    virtual_tail += 1
                    expected_accepted.append(item)
                    active[item["position"]] = item
                    all_items[item["uid"]] = item
                    positions[item["position"]] = item
                    allocation_order.append(item)
                    allocated.add(item["uid"])
                assert change["accepted"] == expected_accepted
                if prior_recovery is not None:
                    physical_end = physical_tail = prior_recovery
                elif expected_accepted:
                    physical_tail = expected_accepted[-1]["end"]
                due = recovered.pop(edge, None)
                assert post["io_toPhysicalQueue_redirectPtr_valid"] == (due is not None)
                if due is not None and not failed:
                    assert output_sq(post, "io_toPhysicalQueue_redirectPtr_bits_") == due % 256
                    counts["recovery_responses"] += 1
                prior_recovery = due
                if state == "idle":
                    rob_head = inp["rob_head"]
                state = next_state
                redirect = inp["redirect"] if inp["redirect"]["valid"] else {**redirect, "valid": False}
            if not failed:
                assert output_sq(post, "io_toPhysicalQueue_retiredPtr_") == retired_end % 256
                assert output_sq(post, "io_toPhysicalQueue_physicalQueueEnqPtr_") == physical_tail % 256
                if post["io_toPhysicalQueue_preCommitPtr_valid"]:
                    assert latest_precommit is not None
                    assert output_sq(post, "io_toPhysicalQueue_preCommitPtr_bits_") == latest_precommit["end"] % 256
                    assert [post["io_toPhysicalQueue_headRobIdx_" + key] for key in ("flag", "value", "isFormer")] == [latest_precommit["rob"][key] for key in ("flag", "value", "former")]
            histories[tick] = {"retired": set(retired), "checked": row["checked"], "empty": bool(post["io_empty"]), "allocated": set(allocated), "canceled": set(canceled), "aborted": set(aborted)}
        outstanding = allocated - retired - canceled - aborted
        assert len(allocated) == len(retired) + len(canceled) + len(aborted) + len(outstanding)
        if nodeid not in failures:
            assert not outstanding and not retired_pending and rows[-1]["after"]["io_empty"] and not rows[-1]["after"]["io_sqRecoverStall"]
        proof_path = path.with_name("vsq_semantics.json")
        proof = json.loads(proof_path.read_text())
        assert proof["nodeid"] == nodeid
        for event in proof["events"]:
            key = (event["checked"], nodeid, event["scenario"])
            samples.setdefault(key, []).append(event["tick"])
            if event["checked"]:
                at = histories[event["tick"]]
                assert at["checked"] and event["scenario"] in checked
                if event["uids"]:
                    assert set(event["uids"]) <= at["retired"]
                else:
                    assert event["scenario"] == "VSQ-IDLE.quiet" and at["empty"]
                if event["scenario"] == "VSQ-CONCURRENT.seeded":
                    assert nodeid not in failures and at["empty"] and at["allocated"] == at["retired"] | at["canceled"] | at["aborted"]
        for witness in reuse_pending:
            if witness["new_uid"] is not None:
                canceled_reuse.append({"nodeid": nodeid, "journal": str(path.relative_to(run)), "sha256": sha(path), **witness})
        if "test_cross_ring_recovery_reuses_every_canceled_virtual_slot" in nodeid:
            assert len(reuse_pending) == 5 and all(witness["new_uid"] is not None for witness in reuse_pending)
            assert {witness["position"] % 128 for witness in reuse_pending} == {127, 0, 1, 2, 3}
        counts.update(allocated=len(allocated), retired=len(retired), canceled=len(canceled), reset_aborted=len(aborted), outstanding_at_failure=len(outstanding))
        totals.update(counts)
        cases.append({"nodeid": nodeid, "journal": str(path.relative_to(run)), "sha256": sha(path), "semantic_proof_sha256": sha(proof_path), **dict(counts)})
    assert seen == set(nodes) and len(error_rows) == len(failures)
    assert set(tuples) == {f"{lane}:{slot}" for lane in range(8) for slot in range(128)}
    assert canceled_reuse
    for kind, group in groups.items():
        point = group["points"][0]
        assert not point["unknown"] and not point["unmatched"]
        for scenario, count in point["counts"].items():
            provenance = point["provenance"].get(scenario, {})
            assert sum(item["count"] for item in provenance.values()) == count
            for origin, item in provenance.items():
                nodeid = group["origins"][origin]["metadata"]["test"]
                ticks = samples[(kind == "checked", nodeid, scenario)]
                assert len(ticks) == item["count"] and min(ticks) == item["first"]["tick"] and max(ticks) == item["last"]["tick"]
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = {"run": name, "status": "public_lifecycle_and_interval_history_audited_with_interface_failures", "dut_acceptance": "NOT_PASS", "tests": manifest["tests"],
              "scope": "independent public uop/flow/end/ROB permission/retirement/recovery/reuse ledger; exact saved pin comparisons and semantic proof provenance checked; not formal or arbitrary-parameter coverage",
              "snapshot_files": len(source), "manifest_sha256": sha(run / "execution/manifest.json"), "line_audit_sha256": sha(run / "line-audit.json"),
              "auditor_sha256": sha(dest), "totals": dict(totals), "reached": 55, "checked": 54, "semantic_total": 55,
              "unpassed_scenarios": ["VSQ-RACE.dispatch_redirect"], "successful_lane_virtual_slot_tuples": len(tuples),
              "witnesses": tuples, "cancel_reuse_witnesses": canceled_reuse, "failures": error_rows, "cases": cases}
    out = run / "trace-audit.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        with out.open("x") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write("\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("witnesses", "cancel_reuse_witnesses", "cases", "failures")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
