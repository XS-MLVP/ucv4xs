#!/usr/bin/env python3
"""Audit first real-parent round, preserving every original missing RTL line.

Directed evidence only, NOT a complete PSQ model or module acceptance. No
lsqverify/reference/DUT-internal imports; raw pins and original producer data.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def ptr(pins, prefix):
    return pins[prefix + "first_flag"] * 128 + pins[prefix + "second_flag"] * 64 + pins[prefix + "value"]


def classify(native):
    result = copy.deepcopy(native)
    text = (ROOT / "rtl/physical_store_queue/PhysicalStoreQueue.sv").read_text().splitlines()
    for gap in result["uncovered"]:
        line = gap["line"]
        if 1596 <= line <= 1598 or line == 4553:
            features, why = ["PSQ-CAPACITY", "PSQ-REUSE"], "虚拟占用/有效前缀距离跨first_flag计算尚未激活，补虚拟128边界和真实四圈写出，不以物理64替代虚拟域"
        elif 12108 <= line <= 12116:
            features, why = ["PSQ-RECOVER"], "真实VSQ redirect输入寄存与完整恢复身份尚未运行，补取消后缀、在途写/回绕与新UID复用"
        else:
            nearby = []
            for index in range(max(0, line - 13), min(len(text), line + 12)):
                for match in re.finditer(r"(?:dataEntries|ctrlEntries)_(\d+)_", text[index]):
                    nearby.append((abs(index + 1 - line), int(match[1])))
            assert nearby, (line, gap)
            nearest = min(distance for distance, slot in nearby)
            slots = sorted({slot for distance, slot in nearby if distance == nearest})
            gap["nearest_original_entry_slots"] = slots
            excerpt = "\n".join(text[max(0, line - 6):line + 5])
            if "cboType" in excerpt or "cboSetVec" in excerpt:
                features, why = ["PSQ-WRITE", "PSQ-SPECIAL", "PSQ-REUSE"], "该物理槽的CBO子类型/属性保存路径缺少CBO真实输入与WB/zero消费见证，补各slot CBO四类，不把普通写入命中当操作已验"
            else:
                features, why = ["PSQ-WRITE", "PSQ-STAGE", "PSQ-READY", "PSQ-REUSE"], "首轮只访问slot0/1，附近物理槽的STA/S2/STD数据/控制写路径缺失；补全部64slot、两lane/先后顺序和多圈重用，须经真实forward/Sbuffer/WB观察原身份和字节"
            gap["original_context"] = excerpt
        gap.update(features=features, classification="missing_scenario_of_existing_feature", semantic_gap=why)
    for dep in result["dependencies"]:
        source = Path(dep["source"]).name
        for gap in dep["uncovered"]:
            if source == "DeqModule.sv":
                features, why = ["PSQ-SPECIAL"], "真实下级NC/MMIO整条请求/确认或响应/WB路径首轮未执行，补父级真实S1/S2属性与完成反馈"
            elif source == "EnterSbufferQueue.sv":
                features, why = ["PSQ-DEQ", "PSQ-REUSE"], "真实下级奇数尾位置保存/第二入口复用缺失，补连续单/双出入并核验原字节和SQ信用"
            elif source == "ForwardModule.sv":
                assert gap["line"] in (4675, 6736, 8797)
                features, why = ["PSQ-FORWARD", "PSQ-WRITE"], "真实下级低年龄候选优先编码中间分组未访问，补全部64槽三lane实际查询，不借用叶子DA"
            else:
                assert source == "UnalignQueue.sv"
                features, why = ["PSQ-BYTE", "PSQ-RECOVER", "PSQ-REUSE"], "真实UQ两槽第二页保存、消费和恢复未运行，补跨页首末请求、正确完整SQ及取消后重用"
            gap.update(features=features, classification="missing_scenario_of_existing_feature", semantic_gap=why)
    return result


def audit(name):
    run = ROOT / "results" / name
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["cleanup_complete"] and manifest["coverage_complete"]
    assert manifest["tests"] == {"PASS": 16, "FAIL": 5}
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            assert all(sha(Path(path)) == digest for path, digest in artifact["build"]["files"].items())
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    end = json.loads((run / "end-source-check.json").read_text())
    assert end["all_current_launch_files_match_snapshot"] and end["files"] == source
    tests = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert len(tests) == 21 and all(test.find("error") is None and test.find("skipped") is None for test in tests)
    nodes = {test.attrib["classname"].replace(".", "/") + ".py::" + test.attrib["name"]: test.find("failure") is not None for test in tests}
    paths = sorted((run / "cases").rglob("physical_store_queue.jsonl"))
    assert len(paths) == 21
    counts, witnesses, reports, seen = Counter(), [], [], set()
    for path in paths:
        trace = rows(path)
        node, last = trace[0]["nodeid"], None
        assert node in nodes and node not in seen
        seen.add(node)
        by_tick, sb_fires, credits = {}, 0, 0
        for row in trace:
            tick, inp, before = row["post_tick"], row["input"], row["before"]
            assert row["nodeid"] == node and inp == row["post_input"]
            assert row["pre_tick"] + 1 == tick and (last is None or last + 2 == tick)
            assert len(inp) == 119 and len(before) == len(row["after"]) == 333
            by_tick[tick], last = row, tick
            counts["continuous_records"] += 1
            if not inp["reset"]:
                sb_fires += sum(before[f"io_writeToSbuffer_req_{lane}_valid"] and inp[f"io_writeToSbuffer_req_{lane}_ready"] for lane in range(2))
                credits += before["io_sqDeq_bits"] if before["io_sqDeq_valid"] else 0
        failed = []
        for check in rows(path.with_name("psq_checks.jsonl")):
            pins = by_tick[check["tick"]][check["phase"]]
            assert check["actual"] == {key: pins[key] for key in check["expected"]}
            diff = {key: [pins[key], want] for key, want in check["expected"].items() if (pins[key] ^ want) & check["bit_masks"].get(key, -1)}
            assert check["passed"] == (not diff)
            counts["directed_checks"] += 1
            if diff:
                failed.append({"tick": check["tick"], "phase": check["phase"], "difference": diff})
        assert bool(failed) == nodes[node] and len(failed) <= 1
        if "test_real_write_order_forward" in node:
            assert (sb_fires, credits) == (1, 1)
            assert ptr(trace[-1]["after"], "io_sqDeqPtr_") == 1
            address = next(row["input"] for row in trace if any(row["input"][f"io_fromStoreUnit_storeAddrIn_{lane}_valid"] for lane in range(2)))
            lane = next(lane for lane in range(2) if address[f"io_fromStoreUnit_storeAddrIn_{lane}_valid"])
            pa = address[f"io_fromStoreUnit_storeAddrIn_{lane}_bits_paddr"]
            data_in = next(row["input"] for row in trace if row["input"][f"io_storeDataIn_{lane}_valid"])
            original = data_in[f"io_storeDataIn_{lane}_bits_data"]
            for index, row in enumerate(trace):
                before, inp = row["before"], row["input"]
                if before["io_writeToSbuffer_req_0_valid"] and inp["io_writeToSbuffer_req_0_ready"]:
                    assert before["io_writeToSbuffer_req_0_bits_addr"] == pa // 16 * 16
                    assert before["io_writeToSbuffer_req_0_bits_mask"] == 0xFF00 and before["io_writeToSbuffer_req_0_bits_wline"] == 0
                    assert before["io_writeToSbuffer_req_0_bits_data"] >> 64 == original
                    counts["independent_normal_store_completions"] += 1
                for load_lane in range(3):
                    prefix = f"io_forward_{load_lane}_s2Resp_"
                    # ForwardModule has no reset port. Only responses to this
                    # case's actually accepted S0 query are new-UID obligations;
                    # early reset pipeline values are not legitimate answers.
                    if index and trace[index - 1]["input"][f"io_forward_{load_lane}_s0Req_valid"]:
                        pins = row["after"]
                        assert pins[prefix + "valid"]
                        assert not any(pins[prefix + "bits_" + key] for key in ("forwardInvalid", "matchInvalid", "addrInvalid_valid", "dataInvalid_valid"))
                        assert all(pins[prefix + f"bits_forwardMask_{byte}"] == int(byte >= 8) for byte in range(16))
                        assert all(pins[prefix + f"bits_forwardData_{byte}"] == original >> (8 * (byte - 8)) & 255 for byte in range(8, 16))
                        counts["independent_forward_responses"] += 1
        if nodes[node]:
            final = trace[-1]
            if "cache_error" in node:
                arrival = next(row for row in trace if row["input"]["io_toDCache_resp_valid"] and row["before"]["io_toDCache_resp_ready"])
                request = next(row for row in trace if row["before"]["io_toDCache_req_valid"] and row["input"]["io_toDCache_req_ready"])
                assert request["post_tick"] < arrival["post_tick"] < final["post_tick"]
                assert final["before"]["io_writeBack_valid"] and final["input"]["io_writeBack_ready"]
                for bit, field in ((7, "denied"), (19, "corrupt")):
                    want = arrival["input"]["io_toDCache_resp_bits_" + field]
                    assert arrival["after"][f"io_writeBack_bits_exceptionVec_{bit}"] == want
                    assert final["before"][f"io_writeBack_bits_exceptionVec_{bit}"] == 0
                issue = "DEQ-WB-001"
                counts["real_parent_lost_error_wb_fires"] += 1
            else:
                assert "split_tail_actual_fire" in node
                source_row = next(row for row in trace if row["input"]["io_fromStoreUnit_storeAddrIn_0_valid"])
                src = source_row["input"]
                assert src["io_fromStoreUnit_storeAddrIn_0_bits_cross16Byte"] and not src["io_fromStoreUnit_storeAddrIn_0_bits_isLastRequest"]
                assert src["io_fromStoreUnit_storeAddrIn_1_bits_uop_fuOpType"] == 7
                assert ptr(final["input"], "io_fromVirtualStoreQueue_preCommitPtr_bits_") == 1
                assert ptr(final["input"], "io_fromVirtualStoreQueue_physicalQueueEnqPtr_") == 2
                data = src["io_storeDataIn_0_bits_data"]
                pa = src["io_fromStoreUnit_storeAddrIn_0_bits_paddr"]
                assert sb_fires == 2
                pins = final["before"]
                assert pins["io_writeToSbuffer_req_1_bits_addr"] == pa // 16 * 16 + 16
                assert pins["io_writeToSbuffer_req_1_bits_mask"] == 0xF and pins["io_writeToSbuffer_req_1_bits_data"] & 0xFFFFFFFF == data >> 32 & 0xFFFFFFFF
                assert pins["io_writeToSbuffer_req_1_bits_wline"] == 1
                issue = "DEQ-SPLIT-WLINE-001"
                counts["real_parent_bad_wline_sbuffer_fires"] += 1
            witnesses.append({"nodeid": node, "issue": issue, "actual_fire_tick": final["post_tick"], "journal": str(path.relative_to(run)), "sha256": sha(path), "failed_check": failed[0]})
        counts["actual_sbuffer_fires"] += sb_fires
        counts["actual_dequeue_credit_sum"] += credits
        reports.append({"nodeid": node, "journal": str(path.relative_to(run)), "sha256": sha(path), "records": len(trace), "sbuffer_fires": sb_fires, "sq_deq_sum": credits})
    assert seen == set(nodes) and counts["independent_normal_store_completions"] == 12 and counts["independent_forward_responses"] == 36
    line_audit = json.loads((run / "line-audit.json").read_text())
    native = line_audit["native"][0]
    assert (native["line_hit"], native["line_total"], native["closure_line_hit"], native["closure_line_total"]) == (3733, 5396, 4113, 5817)
    classified = copy.deepcopy(line_audit)
    classified["native"][0] = classify(native)
    gaps = len(native["uncovered"]) + sum(len(dep["uncovered"]) for dep in native["dependencies"])
    assert gaps == 1704
    classified["classification_summary"] = {"missing_scenario_of_existing_feature": gaps, "missing_whole_feature": 0,
                                              "excluded_or_denominator_removed": 0, "note": "所有DA缺口保留原source/line逐项分类；原合同已定义父级未实现的整路径，后续必须补例，不据此排除可达行"}
    out = run / "line-audit-classified.json"
    if out.exists():
        assert json.loads(out.read_text()) == classified
    else:
        out.write_text(json.dumps(classified, indent=2, ensure_ascii=False) + "\n")
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report = {"run": name, "status": "first_real_parent_directed_history_and_all_missing_lines_audited", "dut_acceptance": "NOT_PASS", "tests": manifest["tests"],
              "counts": dict(counts), "missing_rtl_lines_classified": gaps, "snapshot_files": len(source), "manifest_sha256": sha(run / "execution/manifest.json"),
              "auditor_sha256": sha(dest), "classified_line_audit_sha256": sha(out), "witnesses": witnesses, "cases": reports,
              "limits": "Actual PSQ contains all four real child modules, and public VSQ/STA/STD/bus inputs reach two child faults. Actual VSQ/StoreQueue/Backend legality and system effects remain unproved. Only first directed PSQ round, not a full lifecycle reference, all slots, recovery or module signoff."}
    output = run / "initial-audit.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key not in ("cases", "witnesses")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
