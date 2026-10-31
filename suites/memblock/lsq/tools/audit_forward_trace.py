#!/usr/bin/env python3
'Independent staged public-query audit. No lsqverify or DUT internal imports.'
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


def number(ptr):
    assert 0 <= ptr["value"] < 64
    return 128 * ptr["first"] + 64 * ptr["second"] + ptr["value"]


def pointer(n):
    n %= 256
    return {"first": bool(n & 128), "second": bool(n & 64), "value": n % 64}


def after(left, right):
    distance = (number(left) - number(right)) % 256
    assert distance != 128
    return 0 < distance < 128


def length(size):
    assert 0 <= size <= 7
    return 2 ** min(size, 4)


def pa(store):
    return store["page"] * 4096 + store["vaddr"] % 4096


def select(job, inp):
    if job is None or inp["translations"][job["lane"]]["kill"]:
        return None
    q, bank = job["query"], inp["stores"]
    address = inp["translations"][job["lane"]]["paddr"]
    assert address % 4096 == q["vaddr"] % 4096
    virtual, candidates = [], []
    for slot, identity in job["older"]:
        store = bank[slot]
        same_word = q["vaddr"] // 16 == store["vaddr"] // 16
        next_word = store["cross_word"] and q["vaddr"] // 4096 == store["vaddr"] // 4096 and q["vaddr"] // 16 == store["vaddr"] // 16 + 1
        same_line = store["cache_operation"] and q["vaddr"] // 64 == store["vaddr"] // 64
        load_start = q["vaddr"] % 16 + 16 * next_word
        load_end = load_start + length(q["size"]) - 1
        store_start = store["vaddr"] % 16
        overlaps = max(load_start, store_start) <= min(load_end, store_start + length(store["size"]) - 1)
        if store["address_ready"] and overlaps:
            candidates.append(slot)
            if same_word or next_word or same_line:
                virtual.append(slot)
    chosen = virtual[-1] if virtual else None
    selected_sq = next((identity for slot, identity in job["older"] if slot == chosen), None)
    return {"job": job, "source": chosen, "source_sq": selected_sq, "virtual": set(virtual), "candidates": set(candidates), "bank": bank, "paddr": address,
            "strict_wait": job["outside"] or any(not bank[slot]["address_ready"] for slot, _ in job["older"]),
            "uq_hit": any(page["valid"] and after(q["sq"], page["sq"]) and page["paddr"] // 16 == address // 16 for page in inp["second_pages"])}


def expected(stage2, inp, edges):
    if edges < 2:
        return {}
    out = {}
    for lane, answer in enumerate(stage2):
        prefix = f"io_query_{lane}_s2Resp_"
        out[prefix + "valid"] = int(answer is not None)
        if answer is None:
            continue
        q = answer["job"]["query"]
        chosen = answer["source"]
        store = answer["bank"][chosen] if chosen is not None else None
        start, end = q["vaddr"] % 16, q["vaddr"] % 16 + length(q["size"]) - 1
        full = store is not None and store["vaddr"] % 16 <= start and store["vaddr"] % 16 + length(store["size"]) - 1 >= end
        safe = len(answer["virtual"]) <= 1 or full
        data_invalid = store is not None and (not store["data_ready"] or store["cache_operation"] and store["cbo"] != 3)
        physical = set()
        for slot in answer["candidates"]:
            current = inp["stores"][slot]
            if pa(current) // 16 == answer["paddr"] // 16 or current["cross_word"] and pa(current) // 16 + 1 == answer["paddr"] // 16 or current["cache_operation"] and pa(current) // 64 == answer["paddr"] // 64:
                physical.add(slot)
        precise = q["wait"] and not after(inp["dequeue"], q["wait_sq"]) and (not after(inp["upper"], q["wait_sq"]) or not inp["stores"][q["wait_sq"]["value"]]["address_ready"])
        address_invalid = answer["strict_wait"] if q["strict"] else precise
        out.update({prefix + "bits_forwardInvalid": int(not safe or store is not None and store["cache_operation"] and store["cbo"] != 3 or answer["uq_hit"]),
                    prefix + "bits_matchInvalid": int(physical != answer["virtual"] and safe), prefix + "bits_dataInvalid_valid": int(data_invalid), prefix + "bits_addrInvalid_valid": int(address_invalid)})
        def put_pointer(suffix, ptr):
            out.update({prefix + suffix + "first_flag": int(ptr["first"]), prefix + suffix + "second_flag": int(ptr["second"]), prefix + suffix + "value": ptr["value"]})
        if data_invalid:
            put_pointer("bits_dataInvalid_bits_", answer["source_sq"])
        if address_invalid:
            put_pointer("bits_addrInvalid_bits_", pointer(number(q["sq"]) - 1) if q["strict"] else q["wait_sq"])
        for byte in range(16):
            index = (byte - store["vaddr"] % 16) % 16 if store else 0
            active = store is not None and start <= byte <= end and bool(store["mask"] >> index & 1)
            out[prefix + f"bits_forwardMask_{byte}"] = int(active)
            if active and not data_invalid:
                out[prefix + f"bits_forwardData_{byte}"] = store["data"] >> (8 * index) & 255
    return out


def differences(actual, want):
    return {key: [actual[key], value] for key, value in want.items() if actual[key] != value}


def physical_bytes(stage2, inp, actual):
    """Full PA intervals, deliberately independent of the VA-relative domain."""
    failures, checked = [], []
    for lane, answer in enumerate(stage2):
        if answer is None or answer["bank"] != inp["stores"]:
            continue
        prefix = f"io_query_{lane}_s2Resp_"
        if any(actual[prefix + suffix] for suffix in ("bits_forwardInvalid", "bits_matchInvalid", "bits_addrInvalid_valid", "bits_dataInvalid_valid")):
            continue
        for byte in range(16):
            if not actual[prefix + f"bits_forwardMask_{byte}"]:
                continue
            address = answer["paddr"] // 16 * 16 + byte
            sources = []
            for slot, identity in answer["job"]["older"]:
                store = answer["bank"][slot]
                offset = address - pa(store)
                hit = address // 64 == pa(store) // 64 if store["cache_operation"] else 0 <= offset < length(store["size"]) and bool(store["mask"] >> offset & 1)
                if store["address_ready"] and hit:
                    sources.append((slot, identity, store, offset))
            if not sources:
                failures.append({"uid": answer["job"]["uid"], "lane": lane, "byte": byte, "reason": "no physical source"})
                continue
            slot, identity, store, offset = sources[-1]
            byte_value = store["data"] >> (8 * (offset % 16)) & 255
            valid_data = store["data_ready"] and (not store["cache_operation"] or store["cbo"] == 3)
            if slot != answer["source"] or not valid_data or actual[prefix + f"bits_forwardData_{byte}"] != byte_value:
                failures.append({"uid": answer["job"]["uid"], "lane": lane, "byte": byte, "producer_slot": slot, "producer_sq": identity,
                                 "actual_byte": actual[prefix + f"bits_forwardData_{byte}"], "expected_byte": byte_value, "producer_data_ready": valid_data})
            else:
                checked.append((answer["job"]["uid"], slot, byte))
    return failures, checked


def frozen_counts(snapshot):
    expected_tests = Counter()
    for path in (snapshot / "tests/forward").glob("test_*.py"):
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not node.name.startswith("test_"):
                continue
            count = 1
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "parametrize":
                    values = decorator.args[1]
                    if isinstance(values, ast.Call) and isinstance(values.func, ast.Name) and values.func.id == "range":
                        count *= len(range(*(ast.literal_eval(arg) for arg in values.args)))
                    else:
                        count *= len(ast.literal_eval(values))
            expected_tests[f"tests/forward/{path.name}::{node.name}"] = count
    return expected_tests


def audit(name, require_semantic_obligations=False):
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            assert all(sha(Path(path)) == digest for path, digest in artifact["build"]["files"].items())
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    command = json.loads((run / "command.json").read_text())["command"]
    assert "tests/forward" in command and "-k" not in command and not any(arg.startswith("--deselect") for arg in command)
    cases = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert not any(case.find("skipped") is not None or case.find("error") is not None for case in cases)
    nodes = [case.attrib["classname"].replace(".", "/") + ".py::" + case.attrib["name"] for case in cases]
    assert len(nodes) == len(set(nodes)) and Counter(node.split("[", 1)[0] for node in nodes) == frozen_counts(run / "verification-source")
    failed_nodes = {node for node, case in zip(nodes, cases, strict=True) if case.find("failure") is not None}
    assert manifest["tests"] == {"PASS": len(cases) - len(failed_nodes), "FAIL": len(failed_nodes)}
    native = json.loads((run / "line-audit.json").read_text())["native"]
    assert len(native) == 1 and native[0]["dut"] == "forward_module" and native[0]["line_hit"] == native[0]["line_total"] == 253
    groups = {group["instance"].rsplit(".", 1)[-1]: group for group in json.loads((run / "execution/functional-coverage.json").read_text())["groups"]}
    assert set(groups) == {"reached", "checked"} and all(group["collection_complete"] for group in groups.values())
    reached, checked = (groups[key]["points"][0]["counts"] for key in ("reached", "checked"))
    assert set(reached) == set(checked) and all(0 <= count <= reached[key] for key, count in checked.items())
    assert all(not group["points"][0]["unknown"] and not group["points"][0]["unmatched"] for group in groups.values())
    missing = [key for key, count in checked.items() if not count]
    if require_semantic_obligations:
        issues = {item["id"]: item for item in json.loads((run / "verification-source/manifest/known-issues.json").read_text())["issues"] if item["dut"] == "forward_module"}
        assert set(issues) == {"FWD-ALIAS-001", "FWD-SQID-001", "FWD-RANGE-001"} and all(item["not_a_waiver"] for item in issues.values())
        assert failed_nodes == {node for item in issues.values() for node in item["failure_cases"]}
        assert len(checked) == 64 and all(reached.values()) and set(missing) == {key for item in issues.values() for key in item["unpassed_scenarios"]}
    files = sorted((run / "cases").rglob("forward_module.jsonl"))
    assert len(files) == len(cases)
    totals, per_case, error_rows, tuples, seen_nodes, semantic_samples = Counter(), [], [], {}, set(), {}
    for path in files:
        stage1, stage2, edges, sequence, tick = [None] * 3, [None] * 3, 0, 0, None
        accepted, killed, responses, successful, counts = set(), set(), set(), set(), Counter()
        history = {}
        journal_sha = sha(path)
        records = [json.loads(line) for line in path.read_text().splitlines()]
        nodeid = records[0]["nodeid"]
        assert nodeid in nodes and nodeid not in seen_nodes
        seen_nodes.add(nodeid)
        for index, row in enumerate(records):
            assert row["nodeid"] == nodeid
            counts["records"] += 1
            assert row["pre_tick"] + 1 == row["post_tick"] and (tick is None or tick + 2 == row["post_tick"])
            tick = row["post_tick"]
            inp = row["input"]
            assert inp == row["post_input"]
            want = expected(stage2, inp, edges)
            assert row["expected_before"] == want
            pre_diff = differences(row["before"], want)
            pre_unsafe, pre_bytes = physical_bytes(stage2, inp, row["before"])
            assert not pre_diff and not pre_unsafe, "unexpected failure before edge requires explicit review"
            next_stage2 = [select(job, inp) for job in stage1]
            expected_kills = [job for lane, job in enumerate(stage1) if job and inp["translations"][lane]["kill"]]
            expected_accepts = []
            for lane, query in enumerate(inp["queries"]):
                if not query["valid"]:
                    continue
                age = (number(query["sq"]) - number(inp["dequeue"])) % 256
                limit = (number(inp["upper"]) - number(inp["dequeue"])) % 256
                assert age < 128 and limit <= 64
                sequence += 1
                job = {"uid": sequence, "lane": lane, "query": query, "outside": age > limit,
                       "older": [[(number(inp["dequeue"]) + offset) % 64, pointer(number(inp["dequeue"]) + offset)] for offset in range(min(age, limit))]}
                expected_accepts.append(job)
            change = row["change"]
            assert change["accepted"] == expected_accepts and change["killed"] == expected_kills
            stage1 = [next((job for job in expected_accepts if job["lane"] == lane), None) for lane in range(3)]
            stage2, edges = next_stage2, edges + 1
            assert change["responses"] == [{"uid": answer["job"]["uid"], "lane": answer["job"]["lane"], "selected": answer["source"],
                                            "virtual": sorted(answer["virtual"]), "potential": sorted(answer["candidates"]),
                                            "strict_wait": answer["strict_wait"], "page_hazard": answer["uq_hit"], "paddr": answer["paddr"],
                                            "source": answer["bank"][answer["source"]] if answer["source"] is not None else None} for answer in stage2 if answer]
            accepted.update(job["uid"] for job in expected_accepts)
            killed.update(job["uid"] for job in expected_kills)
            want = expected(stage2, inp, edges)
            assert row["expected_after"] == want
            post_diff = differences(row["after"], want)
            post_unsafe, post_bytes = physical_bytes(stage2, inp, row["after"])
            counts["warmup_unchecked"] += edges < 2
            counts["physical_safe_bytes"] += len(pre_bytes) + len(post_bytes)
            counts["live_bank_observations"] += sum(answer is not None and answer["bank"] != inp["stores"] for answer in stage2)
            if post_diff or post_unsafe:
                assert index == len(records) - 1 and "error" in row and not row["checked"]
                if post_unsafe:
                    assert not post_diff
                    if all(item.get("reason") == "no physical source" for item in post_unsafe):
                        issue = "FWD-RANGE-001"
                    else:
                        assert all(item.get("actual_byte") == 0x11 and item.get("expected_byte") == 0x22 and item.get("producer_slot") == 1 for item in post_unsafe)
                        issue = "FWD-ALIAS-001"
                else:
                    assert len(post_diff) == 2 and all("bits_dataInvalid_bits_" in key for key in post_diff)
                    answer = next(answer for answer in stage2 if answer and not answer["bank"][answer["source"]]["data_ready"])
                    prefix = f"io_query_{answer['job']['lane']}_s2Resp_bits_dataInvalid_bits_"
                    assert post_diff == {prefix + "first_flag": [1, 0], prefix + "second_flag": [0, 1]}
                    assert answer["source_sq"] == pointer(112) and number(answer["job"]["query"]["sq"]) in (128, 129)
                    assert row["after"][prefix + "value"] == 48
                    issue = "FWD-SQID-001"
                if require_semantic_obligations:
                    assert nodeid in issues[issue]["failure_cases"]
                domain = "UNIT-INTERFACE-mask-holes" if "test_seeded_in_window_nonalias" in nodeid else "producer-domain"
                error_rows.append({"nodeid": nodeid, "journal": str(path.relative_to(run)), "sha256": journal_sha, "tick": tick, "issue": issue, "domain": domain,
                                   "differences": post_diff, "physical_byte_failures": post_unsafe})
                counts["failed_edges"] += 1
            else:
                assert "error" not in row and row["checked"] == (edges >= 2)
                counts["checked_edges"] += edges >= 2
            for answer in stage2:
                if answer is None:
                    continue
                job = answer["job"]
                assert job["uid"] not in responses and job["uid"] not in killed
                responses.add(job["uid"])
                counts["valid_responses"] += 1
                if not post_diff and not post_unsafe and answer["source"] is not None:
                    key = f"{job['lane']}:{answer['source']}"
                    tuples.setdefault(key, {"uid": job["uid"], "tick": tick, "journal": str(path.relative_to(run)), "sha256": journal_sha})
                if not post_diff and not post_unsafe:
                    successful.add(job["uid"])
            assert not killed & responses
            history[tick] = {"successful": set(successful), "killed": set(killed), "accepted": set(accepted),
                             "checked": row["checked"], "drained": not any(stage1) and not any(stage2)}
        inflight = {job["uid"] for job in stage1 if job}
        assert accepted == killed | responses | inflight and len(accepted) == len(killed) + len(responses) + len(inflight)
        has_error = "error" in records[-1]
        if not has_error:
            assert not inflight and not any(stage2), "successful case has not drained the two-stage pipeline"
        assert has_error == (nodeid in failed_nodes)
        counts.update(accepted=len(accepted), killed=len(killed), checked_responses=len(successful), inflight_at_end=len(inflight), failed_or_concurrent_responses=len(responses - successful))
        proof_path = path.with_name("forward_semantics.json")
        proof = json.loads(proof_path.read_text())
        assert proof["nodeid"] == nodeid
        for event in proof["events"]:
            at = history[event["tick"]]
            assert event["scenario"] in checked
            key = (event["checked"], nodeid, event["scenario"])
            semantic_samples.setdefault(key, []).append(event["tick"])
            if event["checked"]:
                assert at["checked"]
                if event["uids"]:
                    assert set(event["uids"]) <= at["successful"]
                else:
                    assert event["scenario"] == "FWD-IDLE.quiet" and at["drained"]
                if event["scenario"] == "FWD-CONCURRENT.seeded":
                    assert not has_error and at["drained"] and set(event["uids"]) == at["successful"]
                    assert at["accepted"] == at["successful"] | at["killed"]
        for reuse in proof["kill_reuse"]:
            assert set(reuse["killed_uids"]) <= history[reuse["tick"]]["killed"] and set(reuse["new_uids"]) <= successful
            assert not set(reuse["killed_uids"]) & set(reuse["new_uids"])
            counts["killed_then_new_uid_completed"] += len(reuse["killed_uids"])
        totals.update(counts)
        per_case.append({"nodeid": nodeid, "journal": str(path.relative_to(run)), "sha256": journal_sha, "semantic_proof_sha256": sha(proof_path), "has_error": has_error, **dict(counts)})
    assert seen_nodes == set(nodes)
    for kind, group in groups.items():
        point, provenance = group["points"][0], group["points"][0]["provenance"]
        for scenario, count in point["counts"].items():
            origins = provenance.get(scenario, {})
            assert sum(item["count"] for item in origins.values()) == count
            reconstructed = []
            for origin, item in origins.items():
                nodeid = group["origins"][origin]["metadata"]["test"]
                ticks = semantic_samples.get((kind == "checked", nodeid, scenario), [])
                assert len(ticks) == item["count"] and min(ticks) == item["first"]["tick"] and max(ticks) == item["last"]["tick"]
                reconstructed.extend(ticks)
            assert len(reconstructed) == sum(len(values) for (is_checked, _, name), values in semantic_samples.items() if is_checked == (kind == "checked") and name == scenario)
    assert len(error_rows) == len(failed_nodes)
    assert set(tuples) == {f"{lane}:{slot}" for lane in range(3) for slot in range(64)}
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = {"run": name, "status": "public_staged_history_audited_with_failures", "dut_acceptance": "NOT_PASS", "tests": manifest["tests"],
              "scope": "independent public staged SQ/byte/data/replay checks, UID/kill conservation, stable-bank PA-byte safety; no internal signals or model imports; dynamic banks receive staged checks, not a fictitious atomic-bank guarantee",
              "snapshot_files": len(source), "manifest_sha256": sha(run / "execution/manifest.json"), "line_audit_sha256": sha(run / "line-audit.json"), "auditor_sha256": sha(dest),
              "totals": dict(totals), "reached": sum(bool(count) for count in reached.values()), "checked": sum(bool(count) for count in checked.values()),
              "semantic_total": len(checked), "unpassed_scenarios": missing, "required_semantic_obligations": require_semantic_obligations,
              "failure_issues": dict(Counter(item["issue"] for item in error_rows)),
              "failure_domains": dict(Counter(item["domain"] for item in error_rows)),
              "successful_lane_slot_tuples": len(tuples), "witnesses": tuples, "failures": error_rows, "cases": per_case}
    out = run / "trace-audit.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("cases", "witnesses", "failures")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--require-semantic-obligations", action="store_true")
    args = parser.parse_args()
    audit(args.name, args.require_semantic_obligations)
