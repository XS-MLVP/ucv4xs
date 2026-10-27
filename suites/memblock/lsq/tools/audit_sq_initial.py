#!/usr/bin/env python3
"""Independent raw external history audit for the first real VSQ/PSQ round."""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from audit_psq_initial import ROOT, classify as classify_physical, ptr, rows, sha


def masked_difference(actual, expected, masks):
    return {key: [actual[key], want] for key, want in expected.items() if (actual[key] ^ want) & masks.get(key, -1)}


def classify(native):
    result = copy.deepcopy(native)
    assert not result["uncovered"], "review any new top-level gap explicitly"
    for dep in result["dependencies"]:
        name = Path(dep["source"]).name
        if name == "PhysicalStoreQueue.sv":
            classified = classify_physical({"uncovered": dep["uncovered"], "dependencies": []})["uncovered"]
            for gap in classified:
                gap["features"] = [feature.replace("PSQ-", "SQ-", 1) for feature in gap["features"]]
                gap["semantic_gap"] = "真实StoreQueue必须经dispatch/ROB/redirect及释放闭环激活，不能直驱VSQ许可；" + gap["semantic_gap"]
            dep["uncovered"] = classified
            continue
        for gap in dep["uncovered"]:
            line = gap["line"]
            if name == "VirtualStoreQueue.sv":
                if 5900 <= line <= 14274:
                    features, why = ["SQ-DISPATCH", "SQ-RECOVER", "SQ-CREDIT"], "虚拟槽1..127的ROB/flow/end快照保存，首轮只用一个虚拟uop；补八dispatch lane、128槽/回绕和多flow，须在本层真实preCommit/退休/恢复及实际flow写出后检查身份"
                elif line >= 15870:
                    features, why = ["SQ-DISPATCH", "SQ-CAPACITY"], "稀疏dispatch中间lane作为最后有效分配项的exclusive tail选择；补lane1..6不同稀疏组合与flow数，经真实后续写出证明"
                elif 15848 <= line <= 15857:
                    features, why = ["SQ-RECOVER", "SQ-RETIRE"], "存在已退休前缀时redirect先release再walk；补真实ROB前进/dispatch历史并保留物理未消费项，检查恢复end和幸存字节"
                else:
                    assert 14280 <= line <= 14338 or 15830 <= line <= 15832 or 15858 <= line <= 15861, (name, gap)
                    features, why = ["SQ-RECOVER", "SQ-REUSE"], "真实ROB redirect寄存、取消后last/end快照和physical tail回退；补部分/全取消、前拍dispatch、跨flags及同槽新UID完成"
            elif name == "DeqModule.sv":
                features, why = ["SQ-SPECIAL", "SQ-PERMIT"], "NC/IO的真实S2属性→VSQ ROB头许可→Uncache请求/方向确认或响应/WB→PSQ释放反馈整路径首轮未运行"
            elif name == "EnterSbufferQueue.sv":
                features, why = ["SQ-WRITE", "SQ-CREDIT"], "奇数尾的单/双入保存和压紧路径；首轮有限1/3 flow固定顺序未遍历，补并发单双消费与多圈原字节/释放"
            elif name == "ForwardModule.sv":
                assert line in (4675, 6736, 8797)
                features, why = ["SQ-FORWARD", "SQ-WRITE"], "低年龄候选反转优先组未激活；需真实写出使head非零并跨low/high窗口，尤其低域slot48..63，三lane查询后完整排空"
            else:
                assert name == "UnalignQueue.sv"
                features, why = ["SQ-WRITE", "SQ-RECOVER", "SQ-REUSE"], "两项跨页第二PA真实保存、消费和redirect取消尚未运行；补首末STA/UQ及取消后同槽新页实际写出"
            gap.update(features=features, classification="missing_scenario_of_existing_feature", semantic_gap=why)
    return result


def verify_common(run):
    manifest = json.loads((run / "execution/manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"] and manifest["cleanup_complete"]
    for artifact in manifest["artifacts"]:
        assert sha(Path(artifact["path"])) == artifact["sha256"]
        if artifact["kind"] == "native":
            assert all(sha(Path(path)) == digest for path, digest in artifact["build"]["files"].items())
    source = json.loads((run / "source-evidence.json").read_text())["files"]
    assert all(sha(run / "verification-source" / path) == digest for path, digest in source.items())
    end = json.loads((run / "end-source-check.json").read_text())
    assert end["files"] == source and end["all_current_launch_files_match_snapshot"]
    tests = list(ET.parse(run / "pytest.xml").iter("testcase"))
    assert all(test.find("error") is None and test.find("skipped") is None for test in tests)
    nodes = {test.attrib["classname"].replace(".", "/") + ".py::" + test.attrib["name"]: test.find("failure") is not None for test in tests}
    return manifest, source, nodes


def initial_replay(trace):
    owners, consumed, completed, counts = {}, set(), set(), Counter()
    head = end = 0
    for index, row in enumerate(trace):
        inp, pre, post, tick = row["input"], row["before"], row["after"], row["post_tick"]
        if inp["reset"]:
            assert not owners
            continue
        assert ptr(pre, "io_sqDeqPtr_") == head % 256
        for lane in range(8):
            p = f"io_enq_req_{lane}_"
            if inp[p + "valid"] and inp[p + "bits_needAlloc"]:
                assert not inp["io_redirect_valid"]
                count = inp[p + "bits_uop_numLsElem"]
                for pos in range(end, end + count):
                    assert pos not in owners
                    owners[pos] = {"last_fire": None, "rob": inp[p + "bits_uop_robIdx_value"]}
                end += count
                assert ptr(inp, p + "bits_reqEndPtr_sqIdx_") == end % 256
                counts["dispatched_virtual_uops"] += 1
        for lane in range(2):
            p = f"io_fromStoreUnit_storeAddrIn_{lane}_"
            if inp[p + "valid"]:
                position = head + (inp[p + "bits_uop_sqIdx_value"] - head) % 64
                owner = owners[position]
                assert "va" not in owner and inp[p + "bits_isLastRequest"] and not inp[p + "bits_cross16Byte"]
                owner.update(va=inp[p + "bits_vaddr"], pa=inp[p + "bits_paddr"], size=inp[p + "bits_size"])
            p = f"io_storeDataIn_{lane}_"
            if inp[p + "valid"]:
                position = head + (inp[p + "bits_sqIdx_value"] - head) % 64
                assert "data" not in owners[position]
                owners[position]["data"] = inp[p + "bits_data"]
        for lane in range(2):
            p = f"io_writeToSbuffer_req_{lane}_"
            if pre[p + "valid"] and inp[p + "ready"]:
                position = next(pos for pos in sorted(owners) if pos not in consumed)
                owner = owners[position]
                assert inp["io_fromRob_robHeadPtr_value"] >= owner["rob"]
                va, pa = owner["va"] // 16 * 16, owner["pa"] // 16 * 16
                offset, length = owner["va"] % 16, 1 << owner["size"]
                assert pre[p + "bits_vaddr"] == va and pre[p + "bits_addr"] == pa and not pre[p + "bits_wline"]
                assert pre[p + "bits_mask"] == ((1 << length) - 1) << offset
                bits = ((1 << (8 * length)) - 1) << (8 * offset)
                assert not ((pre[p + "bits_data"] ^ owner["data"] << (8 * offset)) & bits)
                consumed.add(position)
                owner["last_fire"] = tick
                counts["independent_actual_sbuffer_fires"] += 1
        if index:
            previous = trace[index - 1]["input"]
            for lane in range(3):
                p = f"io_forward_{lane}_"
                if not previous[p + "s0Req_valid"]:
                    continue
                va, pa = previous[p + "s0Req_bits_vaddr"], inp[p + "s1Req_paddr"]
                owner = next(owner for pos, owner in owners.items() if pos >= head and owner.get("va") == va and owner.get("pa") == pa)
                assert post[p + "s2Resp_valid"] and not any(post[p + "s2Resp_bits_" + flag] for flag in ("matchInvalid", "forwardInvalid", "dataInvalid_valid", "addrInvalid_valid"))
                for byte in range(16):
                    active = owner["va"] % 16 <= byte < owner["va"] % 16 + (1 << owner["size"])
                    assert post[p + f"s2Resp_bits_forwardMask_{byte}"] == int(active)
                    if active:
                        assert post[p + f"s2Resp_bits_forwardData_{byte}"] == owner["data"] >> (8 * (byte - owner["va"] % 16)) & 255
                counts["independent_actual_forward_responses"] += 1
        delta = (ptr(post, "io_sqDeqPtr_") - head) % 256
        assert delta <= 2 and post["io_toLsqEnqCtrl_sqDeq_valid"] == int(bool(delta))
        if delta:
            assert post["io_toLsqEnqCtrl_sqDeq_bits"] == delta
        for pos in range(head, head + delta):
            assert pos in consumed and pos not in completed and owners[pos]["last_fire"] + 2 == tick
            completed.add(pos)
        head += delta
    assert consumed == completed == set(owners) and trace[-1]["after"]["io_sqEmpty"]
    counts["independent_completed_flows"] = len(completed)
    return counts


def audit(name):
    run = ROOT / "results" / name
    manifest, source, nodes = verify_common(run)
    assert manifest["tests"] == {"PASS": 9} and len(nodes) == 9 and not any(nodes.values())
    counts, seen = Counter(), set()
    cases = []
    for path in sorted((run / "cases").rglob("store_queue.jsonl")):
        trace = rows(path)
        node, last = trace[0]["nodeid"], None
        assert node in nodes and node not in seen
        seen.add(node)
        by_tick = {}
        for row in trace:
            tick = row["post_tick"]
            assert row["nodeid"] == node and row["input"] == row["post_input"] and row["pre_tick"] + 1 == tick
            assert last is None or last + 2 == tick
            assert len(row["input"]) == 182 and len(row["before"]) == len(row["after"]) == 338 and row["checked"]
            assert not masked_difference(row["before"], row["expected_before"], row["masks_before"])
            assert not masked_difference(row["after"], row["expected_after"], row["masks_after"])
            counts["continuous_full_reference_records"] += 1
            by_tick[tick], last = row, tick
        for check in rows(path.with_name("sq_checks.jsonl")):
            pins = by_tick[check["tick"]][check["phase"]]
            assert check["actual"] == {key: pins[key] for key in check["expected"]} and check["passed"]
            assert not masked_difference(pins, check["expected"], check["bit_masks"])
            counts["explicit_directed_checks"] += 1
        replay = initial_replay(trace)
        counts.update(replay)
        cases.append({"nodeid": node, "journal": str(path.relative_to(run)), "sha256": sha(path), "raw_replay_counts": dict(replay)})
    assert seen == set(nodes) and counts["independent_completed_flows"] == 16 and counts["dispatched_virtual_uops"] == 8
    assert counts["independent_actual_forward_responses"] == 24
    audit = json.loads((run / "line-audit.json").read_text())
    n = audit["native"][0]
    assert (n["line_hit"], n["line_total"], n["closure_line_hit"], n["closure_line_total"]) == (26, 26, 5504, 8968)
    classified = copy.deepcopy(audit)
    classified["native"][0] = classify(n)
    missing = sum(len(dep["uncovered"]) for dep in n["dependencies"])
    assert missing == 3464
    classified["classification_summary"] = {"missing_scenario_of_existing_feature": missing, "missing_whole_feature": 0, "excluded_or_denominator_removed": 0}
    auditors = {}
    for tool in (Path(__file__), ROOT / "tools/audit_psq_initial.py"):
        dest = run / "evidence-auditors" / tool.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():
            assert sha(dest) == sha(tool)
        else:
            shutil.copy2(tool, dest)
        auditors[tool.name] = sha(dest)
    report = {"run": name, "status": "initial_real_vsq_psq_interconnect_audited_not_signoff", "tests": manifest["tests"], "counts": dict(counts),
              "snapshot_files": len(source), "remaining_rtl_lines_classified": missing, "auditors": auditors, "cases": cases,
              "limits": "Only first 9 tests/16 normal flows and 24 forward responses independently replayed. Top 26/26 DA does not cover the 8968-line real closure or remaining 39 semantic obligations. No child failure is waived; recovery, special paths, full UID lifecycle and stress remain required."}
    for file, value in (("line-audit-classified.json", classified), ("initial-audit.json", report)):
        output = run / file
        if output.exists():
            assert json.loads(output.read_text()) == value
        else:
            output.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
