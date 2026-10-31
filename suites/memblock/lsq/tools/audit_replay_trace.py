#!/usr/bin/env python3
"""Independent public ownership/packet/feedback, capacity and timer audit.

No import of suites.memblock.lsq or DUT internals. General dependency and arbitration
comparisons are checked from the recorded pre/post expectations, not claimed
as a second independent arbitration implementation or second DUT execution.
"""
import argparse
import ast
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diffs(actual, expected):
    return {key: {"actual": actual[key], "expected": want} for key, want in expected.items() if actual[key] != want}


def younger(a, b):
    def position(ptr):
        assert 0 <= ptr["value"] < 160
        return 2 * (160 * ptr["flag"] + ptr["value"]) + int(not ptr["former"])
    distance = (position(a) - position(b)) % 640
    assert distance != 320
    return 0 < distance < 320


def canceled(uop, red):
    return red["valid"] and (younger(uop["rob"], red["rob"]) or red["flush_self"] and uop["rob"] == red["rob"])


def packet(req, slot, mshr):
    u = req["uop"]
    size = req["aligned_type"] if req["vector"] else u["operation"] // 2 % 8
    mask = req["mask"] if req["vector"] else (((1 << (1 << (size % 4))) - 1) << (req["vaddr"] % 16)) % 65536
    return {"entrance": 2 if req["causes"] & 65 else 8, "accessType_instrType": 2 if req["vector"] else 1,
            "uop_isRVC": int(u["rvc"]), "uop_ftqPtr_flag": int(u["ftq"]["flag"]), "uop_ftqPtr_value": u["ftq"]["value"],
            "uop_ftqOffset": u["offset"], "uop_fuOpType": u["operation"], "uop_rfWen": int(u["integer_write"]),
            "uop_fpWen": int(u["fp_write"]), "uop_vecWen": int(u["vector_write"]), "uop_v0Wen": int(u["v0_write"]),
            "uop_pdest": u["destination"], "uop_robIdx_flag": int(u["rob"]["flag"]), "uop_robIdx_value": u["rob"]["value"],
            "uop_robIdx_isFormer": int(u["rob"]["former"]), "uop_perfDebugInfo_runahead_checkpoint_id": u["checkpoint"],
            "uop_storeSetHit": int(u["store_set_hit"]), "uop_waitSqIdx_first_flag": int(u["wait_sq"]["first"]),
            "uop_waitSqIdx_second_flag": int(u["wait_sq"]["second"]), "uop_waitSqIdx_value": u["wait_sq"]["value"],
            "uop_loadWaitBit": int(u["load_wait"]), "uop_loadWaitStrict": int(u["strict"]),
            "uop_lqIdx_flag": int(u["lq"]["flag"]), "uop_lqIdx_value": u["lq"]["value"],
            "uop_sqIdx_first_flag": int(u["sq"]["first"]), "uop_sqIdx_second_flag": int(u["sq"]["second"]), "uop_sqIdx_value": u["sq"]["value"],
            "vaddr": req["vaddr"], "fullva": req["vaddr"], "size": size, "mask": mask, "mshrId": mshr,
            "replayQueueIdx": slot, "forwardDChannel": int(bool(req["causes"] & 64)), "uncacheReplay": int(bool(req["causes"] & 1)),
            "ncReplay": int(bool(req["causes"] & 1) and req["nc"]), **{f"uop_exceptionVec_{bit}": 0 for bit in (23, 19, 15, 7, 6)}}


def expected_case_counts(snapshot):
    """Validate all frozen test functions AND parameter product, without eval."""
    expected = {}
    for path in sorted((snapshot / "tests/replay").glob("*.py")):
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            count = 1
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute) or decorator.func.attr != "parametrize":
                    continue
                values = decorator.args[1]
                if isinstance(values, (ast.Tuple, ast.List)):
                    count *= len(values.elts)
                elif isinstance(values, ast.Call) and isinstance(values.func, ast.Name) and values.func.id == "range":
                    assert all(isinstance(arg, ast.Constant) and isinstance(arg.value, int) for arg in values.args)
                    count *= len(range(*(arg.value for arg in values.args)))
                else:
                    raise AssertionError("unsupported frozen parameter expression; audit explicitly before widening")
            expected[f"tests/replay/{path.name}::{node.name}"] = count
    return Counter(expected)


def audit(name):
    run = ROOT / "results" / name
    manifest_path = run / "execution/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    assert manifest["pytest_exitstatus"] == 1
    builds = set()
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            builds.add(artifact["build"]["build_id"])
            for path, digest in artifact["build"]["files"].items():
                assert sha(Path(path)) == digest
    assert len(builds) == 1
    source = json.loads((run / "source-evidence.json").read_text())
    for path, digest in source["files"].items():
        assert sha(run / "verification-source" / path) == digest
    command = json.loads((run / "command.json").read_text())["command"]
    assert "tests/replay" in command and "-k" not in command and not any(arg.startswith("--deselect") for arg in command)
    cases = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert not any(case.find("skipped") is not None or case.find("error") is not None for case in cases)
    actual_case_counts, failed = Counter(), set()
    for case in cases:
        node = case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"]
        actual_case_counts[node.split("[", 1)[0]] += 1
        if case.find("failure") is not None:
            failed.add(node)
            assert "'io_replay_0_valid', 1, 0" in case.find("failure").attrib["message"]
    assert actual_case_counts == expected_case_counts(run / "verification-source")
    issue = next(row for row in json.loads((run / "verification-source/manifest/known-issues.json").read_text())["issues"] if row["id"] == "LRQ-STRICT-001")
    assert issue["not_a_waiver"] and failed == set(issue["failure_cases"]) and len(failed) == 4
    assert manifest["tests"] == {"PASS": len(cases) - 4, "FAIL": 4}
    line_path = run / "line-audit.json"
    line_audit = json.loads(line_path.read_text())
    native = line_audit["native"][0]
    assert native["dut"] == "load_queue_replay" and len(line_audit["native"]) == 1 and native["build_id"] in builds
    assert native["line_total"] == 25806 and native["closure_line_total"] == 30500
    assert all(gap["features"] for row in [native, *native["dependencies"]] for gap in row["uncovered"])
    groups = {g["instance"].rsplit(".", 1)[-1]: g for g in json.loads((run / "execution/functional-coverage.json").read_text())["groups"]}
    assert set(groups) == {"reached", "checked"}
    for group in groups.values():
        assert group["collection_complete"] and not group["points"][0]["unknown"] and not group["points"][0]["unmatched"]
    reached, checked = (groups[key]["points"][0]["counts"] for key in ("reached", "checked"))
    assert len(reached) == len(checked) == 84 and all(reached.values())
    assert all(0 <= checked[key] <= reached[key] for key in reached)
    assert {key for key, count in checked.items() if not count} == set(issue["unpassed_scenarios"])
    files = sorted((run / "cases").rglob("load_queue_replay.jsonl"))
    assert len(files) == len(cases)
    witnesses, failures, rows = {}, [], []
    for path in files:
        journal_sha = sha(path)
        counts = Counter(records=0, checked=0, reset_edges=0, allocations=0, output_fires=0, repeated_feedbacks=0,
                         completed_feedbacks=0, canceled=0, reset_owners=0, disabled_feedback_inputs=0,
                         cooldown_edges=0, special_mode_cycles=0, special_mode_entries=0)
        owned, mshr = {}, [0] * 120
        available, advertised, pending_returns, selected_returns = deque(range(120)), 120, [set() for _ in range(4)], []
        sequence = 0
        last_tick = None
        cool, last_fire, perf_old, perf = [0] * 3, [False] * 3, (0,) * 13, (0,) * 13
        special_count, latched, special_head, last_head, special_output = 0, False, None, None, False
        fired_versions = set()
        records = [json.loads(line) for line in path.read_text().splitlines()]
        for index, record in enumerate(records):
            counts["records"] += 1
            assert record["pre_tick"] + 1 == record["post_tick"]
            if last_tick is not None:
                assert record["post_tick"] == last_tick + 2
            last_tick = record["post_tick"]
            inp, pre, post = record["input"], record["before"], record["after"]
            assert inp == record["post_input"]
            if inp["reset"]:
                assert not record["checked"] and "error" not in record
                counts["reset_edges"] += 1
                counts["reset_owners"] += len(owned)
                owned, mshr = {}, [0] * 120
                available, advertised, pending_returns, selected_returns = deque(range(120)), 120, [set() for _ in range(4)], []
                cool, last_fire, perf_old, perf = [0] * 3, [False] * 3, (0,) * 13, (0,) * 13
                special_count, latched, special_head, last_head, special_output = 0, False, None, inp["head"], False
                fired_versions.clear()
                continue
            change = record["change"]
            assert not diffs(pre, record["expected_before"])
            assert {owner["uid"] for owner in change["before"]} == {owner["uid"] for owner in owned.values()}
            assert pre["io_replayAllocate"] == bool(owned) and pre["io_lqFull"] == (not available)
            assert pre["io_specialMode"] == special_output
            assert tuple(pre[f"io_perf_{i}_value"] for i in range(13)) == perf
            fires = [False] * 3
            visible = []
            for bank in range(3):
                prefix = f"io_replay_{bank}_"
                if not pre[prefix + "valid"]:
                    continue
                slot = pre[prefix + "bits_replayQueueIdx"]
                assert slot in owned and slot % 3 == bank
                owner = owned[slot]
                assert not owner["issued"] and not canceled(owner["request"]["uop"], inp["redirect"])
                expected_packet = packet(owner["request"], slot, mshr[slot])
                assert not diffs(pre, {prefix + "bits_" + key: value for key, value in expected_packet.items()})
                visible.append((bank, owner))
                if inp["ready"][bank]:
                    fires[bank] = True
                    key = (owner["uid"], owner["version"])
                    assert key not in fired_versions, "duplicate dispatch before new feedback generation"
                    fired_versions.add(key)
                    owner["issued"] = True
                    counts["output_fires"] += 1
            assert change["fired"] == [owner["uid"] for bank, owner in visible if fires[bank]]
            for bank in range(3):
                cool[bank] = (cool[bank] + 1) % 16 if last_fire[bank] and fires[bank] or cool[bank] >= 12 else 0
            assert change["cooldown"] == cool
            counts["cooldown_edges"] += any(value >= 12 for value in cool)
            events = (sum(req["valid"] and not req["replay_feedback"] for req in inp["enqueues"]), sum(fires),
                      sum(not inp["ready"][bank] for bank, owner in visible), int(not available),
                      *(sum(req["valid"] and not req["replay_feedback"] and bool(req["causes"] >> cause & 1) for req in inp["enqueues"]) for cause in (9, 10, 11, 2, 3, 8, 5, 4, 6)))
            perf, perf_old = perf_old, tuple(events)
            last_fire = fires
            counts["disabled_feedback_inputs"] += sum(not req["valid"] and req["replay_feedback"] and req["slot"] in owned for req in inp["enqueues"])
            freed = {slot for slot, owner in owned.items() if canceled(owner["request"]["uop"], inp["redirect"])}
            completed = set()
            feedback_slots = [req["slot"] for req in inp["enqueues"] if req["valid"] and req["replay_feedback"]]
            assert len(feedback_slots) == len(set(feedback_slots))
            for lane, req in enumerate(inp["enqueues"]):
                if not req["valid"] or not req["replay_feedback"]:
                    continue
                owner = owned[req["slot"]]
                assert owner["issued"] and (owner["uid"], owner["version"]) in fired_versions
                if not req["need_replay"]:
                    completed.add(req["slot"])
                    freed.add(req["slot"])
                    tuple_key = f"{owner['input_lane']}:{owner['slot']}:{owner['slot'] % 3}"
                    witnesses.setdefault(tuple_key, {"journal": str(path.relative_to(run)), "sha256": journal_sha, "uid": owner["uid"],
                                                     "feedback_tick": last_tick, "version": owner["version"]})
                    counts["completed_feedbacks"] += 1
                elif not canceled(req["uop"], inp["redirect"]):
                    owner["request"] = req
                    owner["version"] += 1
                    owner["issued"] = False
                    if req["handled"]:
                        mshr[req["slot"]] = req["mshr"]
                    counts["repeated_feedbacks"] += 1
            assert set(change["completed"]) == {owned[slot]["uid"] for slot in completed}
            assert {owner["slot"] for owner in change["freed"]} == freed
            counts["canceled"] += len(freed - completed)
            for slot in freed:
                del owned[slot]
            allocations = []
            for lane, req in enumerate(inp["enqueues"]):
                if not req["valid"] or req["replay_feedback"] or not req["need_replay"] or canceled(req["uop"], inp["redirect"]):
                    continue
                slot = available.popleft()
                sequence += 1
                assert slot not in owned
                if req["handled"]:
                    mshr[slot] = req["mshr"]
                owner = {"uid": sequence, "slot": slot, "input_lane": lane, "request": req, "version": 0, "issued": False}
                owned[slot] = owner
                allocations.append(owner)
                counts["allocations"] += 1
            assert len(allocations) <= min(3, advertised)
            assert len(change["allocated"]) == len(allocations)
            for actual, expected_owner in zip(change["allocated"], allocations, strict=True):
                assert all(actual[key] == value for key, value in expected_owner.items())
                assert actual["mshr"] == mshr[actual["slot"]]
            advertised = len(available)
            available.extend(selected_returns)
            selected_returns = []
            for bank in pending_returns:
                if bank:
                    slot = min(bank)
                    bank.remove(slot)
                    selected_returns.append(slot)
            for slot in freed:
                pending_returns[slot % 4].add(slot)
            partitions = [set(owned), set(available), set(selected_returns), *pending_returns]
            assert sum(map(len, partitions)) == 120 and set().union(*partitions) == set(range(120))
            next_special = latched and inp["head"] == special_head
            moved = last_head is not None and inp["head"] != last_head
            trigger = any(req["valid"] and req["special_eligible"] and req["uop"]["rob"] == inp["head"] and not canceled(req["uop"], inp["redirect"]) for req in inp["enqueues"])
            if moved:
                special_count, latched = 0, False
            elif not latched and (trigger or special_count):
                if special_count == 2047:
                    latched, special_head = True, inp["head"]
                else:
                    special_count += 1
            last_head = inp["head"]
            assert change["special_count"] == special_count
            counts["special_mode_cycles"] += next_special
            counts["special_mode_entries"] += next_special and not special_output
            special_output = next_special
            assert post["io_replayAllocate"] == bool(owned) and post["io_lqFull"] == (not available)
            assert post["io_specialMode"] == special_output
            assert tuple(post[f"io_perf_{i}_value"] for i in range(13)) == perf
            differences = diffs(post, record["expected_after"])
            if differences:
                assert index == len(records) - 1 and "error" in record and not record["checked"]
                assert differences == {"io_replay_0_valid": {"actual": 1, "expected": 0}}
                slot = post["io_replay_0_bits_replayQueueIdx"]
                owner = owned[slot]
                assert slot == 0 and owner["request"]["causes"] == 4 and owner["request"]["uop"]["strict"]
                assert inp["address_ready"] == {"first": False, "second": False, "value": 0} and not inp["sq_empty"]
                assert inp["address_bits"] >> 7 & 1
                assert not any(w["valid"] for row in records for w in row["input"]["address_wakeups"])
                invalid_lanes = [lane for row in records for lane, req in enumerate(row["input"]["enqueues"])
                                 if not req["valid"] and req["replay_feedback"] and req["slot"] == slot]
                signature = {"kind": "disabled_feedback", "lane": invalid_lanes[0]} if invalid_lanes else {"kind": "full_pool"}
                if not invalid_lanes:
                    assert len(owned) == 120 and pre["io_lqFull"] and not available
                failures.append({"journal": str(path.relative_to(run)), "tick": last_tick, "issue": issue["id"], **signature,
                                 "expected_valid": 0, "actual_valid": 1, "source_strict": True})
            else:
                assert record["checked"] and "error" not in record
                counts["checked"] += 1
            for bank in range(3):
                prefix = f"io_replay_{bank}_"
                if post[prefix + "valid"]:
                    slot = post[prefix + "bits_replayQueueIdx"]
                    assert slot in owned and slot % 3 == bank and not owned[slot]["issued"]
                    expected_packet = packet(owned[slot]["request"], slot, mshr[slot])
                    assert not diffs(post, {prefix + "bits_" + key: value for key, value in expected_packet.items()})
                if pre[prefix + "valid"] and not inp["ready"][bank]:
                    assert post[prefix + "valid"]
                    assert all(pre[key] == post[key] for key in pre if key.startswith(prefix + "bits_"))
        has_failure = any("error" in row for row in records)
        counts["owners_at_end"] = len(owned)
        if not has_failure:
            assert not owned, "a successful testcase leaves no live owner"
        assert counts["allocations"] == counts["completed_feedbacks"] + counts["canceled"] + counts["reset_owners"] + len(owned)
        rows.append({"journal": str(path.relative_to(run)), "sha256": journal_sha, "has_failure": has_failure, **dict(counts)})
    assert Counter((row["kind"], row.get("lane")) for row in failures) == Counter({("full_pool", None): 1, ("disabled_feedback", 0): 1, ("disabled_feedback", 1): 1, ("disabled_feedback", 2): 1})
    assert set(witnesses) == {f"{lane}:{slot}:{slot % 3}" for lane in range(3) for slot in range(120)}
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/coverage_audit.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool), "do not overwrite historical auditor"
        else:
            shutil.copy2(tool, dest)
        auditors[str(dest.relative_to(run))] = sha(dest)
    report = {"run": name, "status": "evidence_audited_with_failures", "dut_acceptance": "NOT_PASS", "issue": issue["id"],
              "tests": manifest["tests"], "manifest_sha256": sha(manifest_path), "line_audit_sha256": sha(line_path),
              "raw_body": [native["line_hit"], native["line_total"]], "raw_closure": [native["closure_line_hit"], native["closure_line_total"]],
              "line_gaps": sum(len(row["uncovered"]) for row in [native, *native["dependencies"]]),
              "source_snapshot_files": len(source["files"]), "reached": sum(bool(v) for v in reached.values()), "checked": sum(bool(v) for v in checked.values()),
              "unpassed_scenarios": [key for key, count in checked.items() if not count], "auditors": auditors,
              "scope": "continuous public inputs/outputs; independent FIFO/UID and feedback generations, packet fields, 13 perf histories, cooldown and 2048-cycle mode history; recorded full pre/post dependency/priority checks are validated, not a second independent arbiter implementation or second RTL execution",
              "totals": {key: sum(row[key] for row in rows) for key in counts}, "successful_input_lane_slot_bank_tuples": len(witnesses),
              "witnesses": witnesses, "failures": failures, "cases": rows}
    output = run / "trace-audit.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("cases", "failures", "witnesses")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
