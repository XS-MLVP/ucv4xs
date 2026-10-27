#!/usr/bin/env python3
"""Independent public replay of the added all-slot storage/CBO parent rounds.

No DUT internals or domain-model imports. Not full PSQ/recovery acceptance.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from audit_psq_initial import ROOT, classify, ptr, rows, sha


def word(owner):
    va, pa = owner["va"] // 16 * 16, owner["pa"] // 16 * 16
    mask = data = 0
    for index in range(1 << min(owner["size"], 4)):
        byte = owner["va"] + index - va
        assert 0 <= byte < 16
        mask |= 1 << byte
        data |= (owner["data"] >> (8 * index) & 255) << (8 * byte)
    return {"vaddr": va, "addr": pa, "mask": mask, "data": data, "wline": int(owner["cbo"] == 3)}


def storage_replay(trace, cbo_case):
    owners, consumed, finished, completed = {}, set(), set(), set()
    head = 0
    counts = Counter()
    addr_pairs, data_pairs = set(), set()
    for index, row in enumerate(trace):
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        if inp["reset"]:
            assert not owners
            continue
        assert ptr(pre, "io_sqDeqPtr_") == head % 256
        for lane in range(2):
            prefix = f"io_fromStoreUnit_storeAddrIn_{lane}_"
            if inp[prefix + "valid"]:
                slot = inp[prefix + "bits_uop_sqIdx_value"]
                position = head + (slot - head) % 64
                assert position not in owners
                op = inp[prefix + "bits_uop_fuOpType"]
                owners[position] = {"position": position, "va": inp[prefix + "bits_vaddr"], "pa": inp[prefix + "bits_paddr"], "size": inp[prefix + "bits_size"],
                                    "cbo": (op >> 1 & 7) if op & 1 else None, "data": None, "last_fire": None}
                assert inp[prefix + "bits_isLastRequest"] and not inp[prefix + "bits_tlbMiss"]
                assert (ptr(inp, "io_fromVirtualStoreQueue_physicalQueueEnqPtr_") - head) % 256 <= 128
                addr_pairs.add((slot, lane))
                counts["allocated_owners"] += 1
        for lane in range(2):
            prefix = f"io_storeDataIn_{lane}_"
            if inp[prefix + "valid"]:
                slot = inp[prefix + "bits_sqIdx_value"]
                position = head + (slot - head) % 64
                op = inp[prefix + "bits_fuOpType"]
                owner = owners[position]
                assert owner["data"] is None
                owner["data"] = 0 if op & 1 and op >> 1 & 7 == 3 else inp[prefix + "bits_data"]
                data_pairs.add((slot, lane))
        if pre["io_toDCache_req_valid"] and inp["io_toDCache_req_ready"]:
            owner = owners[head]
            assert owner["cbo"] in (0, 1, 2)
            assert pre["io_toDCache_req_bits_opcode"] == owner["cbo"] and pre["io_toDCache_req_bits_address"] == owner["pa"]
            counts["cache_requests"] += 1
        for lane in range(2):
            prefix = f"io_writeToSbuffer_req_{lane}_"
            if pre[prefix + "valid"] and inp[prefix + "ready"]:
                if cbo_case:
                    owner = owners[head]
                    assert owner["cbo"] == 3
                else:
                    owner = next(owners[position] for position in sorted(owners) if position not in consumed)
                position = owner["position"]
                assert position not in consumed
                expected = word(owner)
                for field, want in expected.items():
                    mask = sum(255 << (8 * byte) for byte in range(16) if expected["mask"] >> byte & 1) if field == "data" else -1
                    assert not ((pre[prefix + "bits_" + field] ^ want) & mask), (tick, position, field)
                consumed.add(position)
                owner["last_fire"] = tick
                counts["actual_sbuffer_fires"] += 1
                counts["actual_sbuffer_bytes"] += expected["mask"].bit_count()
        if pre["io_writeBack_valid"] and inp["io_writeBack_ready"]:
            owner = owners[head]
            assert cbo_case and owner["cbo"] is not None and head not in finished
            if owner["cbo"] == 3:
                assert head in consumed and owner["last_fire"] < tick
            assert not pre["io_writeBack_bits_exceptionVec_7"] and not pre["io_writeBack_bits_exceptionVec_19"]
            assert pre["io_writeBack_bits_robIdx_value"] == head % 160
            assert pre["io_writeBack_bits_robIdx_isFormer"] == head % 2
            finished.add(head)
            owner["last_fire"] = tick
            counts["actual_writeback_fires"] += 1
        if index:
            previous = trace[index - 1]["input"]
            for lane in range(3):
                prefix = f"io_forward_{lane}_"
                if previous[prefix + "s0Req_valid"]:
                    assert not cbo_case and post[prefix + "s2Resp_valid"]
                    query_va, query_pa = previous[prefix + "s0Req_bits_vaddr"], inp[prefix + "s1Req_paddr"]
                    candidate = [owner for position, owner in owners.items() if position >= head and owner["va"] // 16 == query_va // 16 and owner["pa"] // 16 == query_pa // 16]
                    assert len(candidate) == 1
                    owner = candidate[0]
                    expected = word(owner)
                    for byte in range(16):
                        active = expected["mask"] >> byte & 1
                        assert post[prefix + f"s2Resp_bits_forwardMask_{byte}"] == active
                        if active:
                            assert post[prefix + f"s2Resp_bits_forwardData_{byte}"] == expected["data"] >> (8 * byte) & 255
                    assert not any(post[prefix + "s2Resp_bits_" + flag] for flag in ("forwardInvalid", "matchInvalid", "addrInvalid_valid", "dataInvalid_valid"))
                    counts["actual_forward_responses"] += 1
        delta = (ptr(post, "io_sqDeqPtr_") - head) % 256
        assert delta <= 2
        assert post["io_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert post["io_sqDeq_bits"] == delta
        for position in range(head, head + delta):
            owner = owners[position]
            assert position not in completed and owner["last_fire"] is not None and owner["last_fire"] + 2 == tick
            assert position in (finished if cbo_case else consumed)
            completed.add(position)
        head += delta
    assert len(completed) == len(owners) == (128 if cbo_case else 256)
    assert len(addr_pairs) == len(data_pairs) == 128
    counts.update(completed_owners=len(completed), address_lane_slot_pairs=len(addr_pairs), data_lane_slot_pairs=len(data_pairs))
    if cbo_case:
        assert counts["actual_writeback_fires"] == 128 and counts["cache_requests"] == 96 and counts["actual_sbuffer_fires"] == 32
    else:
        assert counts["actual_sbuffer_fires"] == 256 and counts["actual_forward_responses"] == 768
    return dict(counts)


def audit(name):
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["cleanup_complete"] and manifest["coverage_complete"]
    assert manifest["tests"] == {"PASS": 18, "FAIL": 5}
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            assert all(sha(Path(path)) == digest for path, digest in artifact["build"]["files"].items())
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    end = json.loads((run / "end-source-check.json").read_text())
    assert end["all_current_launch_files_match_snapshot"] and end["files"] == source
    tests = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert len(tests) == 23 and all(test.find("error") is None and test.find("skipped") is None for test in tests)
    nodes = {test.attrib["classname"].replace(".", "/") + ".py::" + test.attrib["name"]: test.find("failure") is not None for test in tests}
    seen, counts, storage, failures = set(), Counter(), [], []
    for path in sorted((run / "cases").rglob("physical_store_queue.jsonl")):
        trace = rows(path)
        node, last = trace[0]["nodeid"], None
        assert node in nodes and node not in seen
        seen.add(node)
        by_tick = {}
        for row in trace:
            tick = row["post_tick"]
            assert row["nodeid"] == node and row["input"] == row["post_input"]
            assert row["pre_tick"] + 1 == tick and (last is None or last + 2 == tick)
            by_tick[tick], last = row, tick
            counts["continuous_records"] += 1
        differences = []
        for check in rows(path.with_name("psq_checks.jsonl")):
            pins = by_tick[check["tick"]][check["phase"]]
            assert check["actual"] == {key: pins[key] for key in check["expected"]}
            diff = {key: [pins[key], want] for key, want in check["expected"].items() if (pins[key] ^ want) & check["bit_masks"].get(key, -1)}
            assert check["passed"] == (not diff)
            counts["directed_checks"] += 1
            if diff:
                differences.append(diff)
        assert bool(differences) == nodes[node]
        if differences:
            assert len(differences) == 1
            pins = set(differences[0])
            final = trace[-1]
            if "cache_error" in node:
                assert all("exceptionVec_" in pin for pin in pins) and final["before"]["io_writeBack_valid"] and final["input"]["io_writeBack_ready"]
                issue = "DEQ-WB-001"
            else:
                assert pins == {"io_writeToSbuffer_req_1_bits_wline"} and final["before"]["io_writeToSbuffer_req_1_valid"] and final["input"]["io_writeToSbuffer_req_1_ready"]
                issue = "DEQ-SPLIT-WLINE-001"
            failures.append({"nodeid": node, "issue": issue, "actual_fire_tick": final["post_tick"], "journal": str(path.relative_to(run)), "sha256": sha(path), "difference": differences[0]})
        if "test_storage_expanded" in node:
            replay = storage_replay(trace, "test_cbo_all_slots" in node)
            counts.update(replay)
            storage.append({"nodeid": node, "journal": str(path.relative_to(run)), "sha256": sha(path), "counts": replay})
    assert seen == set(nodes) and len(storage) == 2 and len(failures) == 5
    assert counts["completed_owners"] == 384
    audit = json.loads((run / "line-audit.json").read_text())
    native = audit["native"][0]
    assert (native["line_hit"], native["line_total"], native["closure_line_hit"], native["closure_line_total"]) == (5387, 5396, 5772, 5817)
    classified = copy.deepcopy(audit)
    classified["native"][0] = classify(native)
    gaps = len(native["uncovered"]) + sum(len(dep["uncovered"]) for dep in native["dependencies"])
    assert gaps == 45
    for dep in classified["native"][0]["dependencies"]:
        for gap in dep["uncovered"]:
            if Path(dep["source"]).name == "ForwardModule.sv":
                gap["semantic_gap"] = "四圈64槽对齐窗口全量查询后仍缺低年龄选择中间分组；需非零deq使物理窗口跨low/high边界及相应候选查询，不以全槽写/普通查询宣称该域已穷尽"
            if Path(dep["source"]).name == "EnterSbufferQueue.sv":
                gap["semantic_gap"] = "剩第二输入写slot0的奇数尾条件；本轮普通双入始终偶数尾，单独zero不会伴第二输入。补先单普通消费再双入或非零head并发，实际检查两owner消费/credit"
    classified["classification_summary"] = {"missing_scenario_of_existing_feature": 45, "missing_whole_feature": 0, "excluded_or_denominator_removed": 0}
    out = run / "line-audit-classified.json"
    if out.exists():
        assert json.loads(out.read_text()) == classified
    else:
        out.write_text(json.dumps(classified, indent=2, ensure_ascii=False) + "\n")
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/audit_psq_initial.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool)
        else:
            shutil.copy2(tool, dest)
        auditors[tool.name] = sha(dest)
    report = {"run": name, "status": "expanded_all_slot_storage_cbo_and_real_completion_audited", "dut_acceptance": "NOT_PASS", "tests": manifest["tests"],
              "counts": dict(counts), "remaining_rtl_lines_classified": 45, "snapshot_files": len(source), "manifest_sha256": sha(run / "execution/manifest.json"),
              "auditors": auditors, "storage_cases": storage, "failures": failures,
              "limits": "Added two directed long streams reconstruct 384 real owners from raw STA/STD and actual public completions, not a full PSQ reference. Recovery/UQ/NC/IO/random/missing semantic points remain required. Full real StoreQueue/VSQ/Backend constraints and architectural effects are not established."}
    output = run / "storage-audit.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("storage_cases", "failures")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
