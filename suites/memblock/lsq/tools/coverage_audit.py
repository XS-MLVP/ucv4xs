#!/usr/bin/env python3
"""Audit committed native line tables; retain every missing line and semantic mapping."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def lcov(path):
    tables, current = {}, None
    for row in path.read_text().splitlines():
        if row.startswith("SF:"):
            current = row[3:]
            tables.setdefault(current, {})
        elif row.startswith("DA:"):
            line, hits, *_ = row[3:].split(",")
            table = tables[current]
            table[int(line)] = table.get(int(line), 0) + int(hits)
    return tables


def meaning(line, text, write_region, *, key="", dependency=False):
    if key == "virtual_store_queue":
        if 6477 <= line <= 14274:
            return ["VSQ-ADMIT", "VSQ-INTERVAL", "VSQ-SNAPSHOT", "VSQ-REUSE"], "虚拟slot8..127的ROB/flow数/完整物理end快照保存路径首轮未访问；补全128个虚拟槽和各dispatch入口、双flag与虚拟回绕，必须由后续实际preCommit/退休/恢复输出证明，不能只写入计通过"
        if 15848 <= line <= 15857:
            return ["VSQ-WALK", "VSQ-RETIRE", "VSQ-REDIRECT", "VSQ-RECOVER"], "redirect前存在已退休head时先release再walk的状态路径；补已退休连续前缀、冻结ROB head与年轻取消后缀，检查真实retiredPtr/redirectPtr及完整stall窗口"
        return [], "待人工审查，不能据此排除或缩小功能范围"
    if key == "unalign_queue":
        if 156 <= line <= 159:
            return ["UQ-CAPACITY", "UQ-ORDER", "UQ-PAGE", "UQ-FORWARD"], "第二个物理槽保存跨页第二页号及完整SQ身份尚未激活；补两个有效请求、两个入口/槽及回绕，检查公开forwardValid/页地址和真实head消费"
        if 182 <= line <= 184:
            return ["UQ-REDIRECT", "UQ-REUSE", "UQ-ORDER"], "SQ恢复使尾部回退取消后缀的路径；补取消0/1/2项、完整flags/回绕、连续恢复与幸存head消费，取消后必须同槽新UID实际消费才checked"
        return [], "待人工审查，不据此排除可达行"
    if key == "enter_sbuffer_queue":
        if 131 <= line <= 136 or 147 <= line <= 152:
            return ["ESB-ADMIT", "ESB-ORDER", "ESB-PAYLOAD", "ESB-REUSE"], "第二输入向两个物理槽保存写请求的路径；补双项前缀、奇偶次序回绕和双出双入，比较两个真实输出的完整payload及消费credit，不只计写行"
        if 155 <= line <= 159:
            return ["ESB-ADMIT", "ESB-ORDER", "ESB-PAYLOAD"], "第一输入到另一物理槽的保存路径；补单项消费后继续单/双入的奇数尾位置，实际Sbuffer消费证明未串旧数据"
        return [], "待人工审查，不据此排除可达行"
    if key == "load_queue_replay":
        if dependency and any(s.startswith("module FreeList_2(") for s in text[:70]):
            return ["LRQ-RECYCLE", "LRQ-ADMIT", "LRQ-OWNER"], "父块真实120项预分配FreeList的回收/池写回未激活；补满池真实replay握手后正常反馈、同/跨通道积压、取消与多轮复用，不用独立叶子覆盖替代"
        if 10191 <= line <= 10592:
            return ["LRQ-ORDER", "LRQ-BANK"], "三个bank程序头/头后1至3项候选选择路径；补全部bank、LQ回绕、与高低原因组/入队年龄竞争，比较真实输出UID和完整元信息"
        if 30578 <= line <= 32361:
            return ["LRQ-ADMIT", "LRQ-CAUSE", "LRQ-OWNER", "LRQ-BANK"], "高slot从三个入口保存NC/原因/lastBeat等重放状态；补全部120项和入口轮换、同槽反馈更新，并以实际输出及反馈释放证明"
        if 33684 <= line <= 35363:
            return ["LRQ-STORE", "LRQ-OWNER", "LRQ-ADMIT"], "store地址strict及各入口更新路径；补三lane/120项MA、strict正反/真实ready与wakeup，检查未满足依赖不重放、满足后完成"
        if 35973 <= line <= 37406:
            return ["LRQ-REFILL", "LRQ-TLB", "LRQ-OWNER", "LRQ-CAUSE"], "各slot的MSHR/TLB依赖标签保存路径；补全部入口/slot、不同ID和历史hint/beat、再重放更新，核对真实输出与ID正反唤醒"
        if line in (38165, 38168, 61615, 61616, 61617):
            return ["LRQ-SPECIAL", "LRQ-RESET"], "ROB头eligible等待窗口和特殊模式身份保存；补2048边界、头移动/取消/再反馈不重启及年轻C_TM标记，检查真实specialMode而非内部计数器"
        if 58800 <= line <= 58827:
            return ["LRQ-REFILL", "LRQ-TLB", "LRQ-UNCACHE"], "refill/TLB/MMIO的真实脉冲历史；补两个channel、各到达/过期窗口和LQ/MMIO身份，比较公开重放时序"
        if 45546 <= line <= 58823:
            return ["LRQ-ADMIT", "LRQ-PAYLOAD", "LRQ-OWNER", "LRQ-BANK"], "各slot从不同入口保存原load及vector/vaddr元信息；补120项×三个入口及同槽更新，实际replay逐字段比较、握手后反馈释放，不能只计写入行"
        return [], "待人工审查，不能据此排除或宣称不可达"
    if key == "load_queue_uncache":
        if dependency and any(s.startswith("module FreeList_3(") for s in text[:70]):
            return ["LQU-CAPACITY", "LQU-REUSE", "LQU-ALLOC"], "父块真实16项预分配FreeList的回收/复用缺口；补满池、分通道积压、同拍消费/取消/新分配和预取等待，检查真实bus ID及rollback而非引用叶子覆盖"
        if dependency and any(s.startswith("module UncacheEntry") for s in text[:70]):
            return ["LQU-ALLOC", "LQU-ID", "LQU-WAKE", "LQU-BYPASS", "LQU-FLUSH", "LQU-EXCEPTION"], "真实entry在父块中的活动/取消/元信息路径；补全部16 ID的实际总线、sid、回包、wakeup、bypass和取消，不以独立entry已通过替代集成覆盖"
        if 2460 <= line <= 2729:
            return ["LQU-SORT", "LQU-FILTER", "LQU-ALLOC"], "排序后第1/2项元信息保存未激活；补三lane六排列、稀疏valid/过滤、同龄和跨环，检查真实entry ID及后续数据/rollback身份"
        if 2758 <= line <= 3556:
            return ["LQU-BYPASS", "LQU-ID", "LQU-EXCEPTION"], "三个bypass通道选择不同entry的地址/数据/错误路径；补全部16项和NC/MMIO、三lane、多个并行消费及不匹配反例，检查实际s1/s2结果"
        if 3566 <= line <= 3609:
            return ["LQU-FILTER", "LQU-FLUSH", "LQU-ROLLBACK"], "redirect历史和容量拒绝的恢复身份；补保存/分配窗口取消、满池部分/全部拒绝和历史redirect过滤，比较有效rollback元信息"
        if 7450 <= line <= 7982:
            return ["LQU-EXCEPTION", "LQU-ALLOC", "LQU-BYPASS"], "更高entry索引的异常信息汇聚路径；补全部ID真实消费、错误/元信息及多消费优先选择，不能宣称多个事件被单输出全数上报"
        return [], "待人工审查，不能据此排除或宣称不可达"
    if key.startswith("uncache_entry_"):
        offset = 0 if key == "uncache_entry_0" else 2
        if line - offset in (252, 253):
            return ["UE-FLUSH", "UE-AGE", "UE-REUSE"], "保存/等待ROB阶段的立即取消路径；补命中/不命中redirect及年龄边界，比较真实flush并以新身份正常完成证明安全重用"
        if line - offset in (263, 264):
            return ["UE-FLUSH", "UE-REQ", "UE-REUSE"], "总线尚未接受时的取消路径；补请求背压下redirect，检查当拍抑制请求、flush及后续重用，不能把未发请求当作已发后提前释放"
        if line - offset in (273, 274):
            return ["UE-FLUSH", "UE-WAKE", "UE-REUSE"], "回包后wakeup阶段的取消路径；补当前redirect与历史取消及ready并发，检查实际可见wakeup边界、后续无数据消费及新事务完成"
        return [], "待人工审查，不能据此排除或宣称不可达"
    if key == "load_queue_raw":
        if dependency and any(s.startswith("module FreeList_1(") for s in text[:70]):
            return ["RAW-DRAIN", "RAW-CAPACITY", "RAW-REVOKE"], "真实预分配FreeList的各通道回收及池写回；补指针/redirect/revoke返回、单通道长积压、跨56项复用与额外预取等待，以父块ready/full和新记录实际rollback检查"
        if dependency and any(s.startswith(("module LqPAddrModule_1(", "module LqMaskModule(")) for s in text[:70]):
            return ["RAW-ALLOC", "RAW-ADDRESS", "RAW-MASK", "RAW-PIPELINE"], "真实地址或mask CAM的槽位写路径；补三个入口各写满56项并逐条store探测，检查紧邻写读、wline和mask，不借用叶子覆盖冒充父块集成"
        # Ranges are reviewed against this pinned generated body, not a
        # reachability exclusion or an attempt to infer semantic correctness.
        if 7205 <= line <= 7540:
            return ["RAW-ALLOC", "RAW-DATA"], "各槽位从不同load入口保存dataValid；补完整池/三个入口、有效与无效数据过滤及复用，检查实际候选和容量"
        if 7821 <= line <= 7933:
            return ["RAW-PIPELINE", "RAW-ORDER", "RAW-ROLLBACK"], "第二个store端口的候选快照未激活；补双store和独立正反冲突，比较两端口完整恢复元信息"
        if 14646 <= line <= 16996:
            return ["RAW-ALLOC", "RAW-ORDER", "RAW-DRAIN", "RAW-ROLLBACK"], "各物理槽位保存ROB/SQ/FTQ/RVC/checkpoint的不同入口路径；补所有入口×56项，以唯一store恢复和精确回收检查身份，不只统计写行"
        if line in (17006, 17015):
            return ["RAW-REVOKE", "RAW-PIPELINE"], "load入口2的真实接受索引历史；补该lane一拍/两拍撤销并检查无历史与新分配隔离"
        if 17128 <= line < 19100:
            return ["RAW-ORDER", "RAW-PIPELINE", "RAW-ROLLBACK"], "最老选择组和第二store端口的有效候选/元信息传递；补每个物理选择组及跨组的乱序年龄，比较N+2恢复身份"
        return [], "待人工审查，不能据此排除或宣称不可达"
    if key == "load_queue_rar":
        if dependency and any(s.startswith("module FreeList(") for s in text[:70]):
            return ["RAR-DRAIN", "RAR-REVOKE", "RAR-CAPACITY", "RAR-RACE"], "真实FreeList的返回/复用路径；补由head、redirect和revoke产生的单/多通道积压、变长回收及全池复用，比较父块ready/full和唯一查询，而不是复用叶子覆盖结果"
        if dependency and any(s.startswith("module LqPAddrModule(") for s in text[:70]):
            return ["RAR-ALLOC", "RAR-HASH", "RAR-RELEASE"], "真实地址CAM的槽位写入；补全部96项/三个入口的父块分配并通过唯一hash查询和release检查保存的数据"
        context = "\n".join(text[max(0, line-7):line+5])
        if "release2Cycle_bits_paddr <=" in text[line-1]:
            return ["RAR-RELEASE", "RAR-RACE"], "前拍完整release地址的捕获；补分配前一拍/同拍release、dataValid和hash碰撞但非完整line相等的反例"
        if re.search(r"uop_\d+_", context):
            return ["RAR-ALLOC", "RAR-AGE", "RAR-DRAIN", "RAR-REVOKE"], "各物理RAR槽位从不同查询入口保存ROB/LQ身份；补三入口全池和环绕，通过年龄查询、head/redirect/revoke释放间接证明，不只看写入行已执行"
        return [], "待人工审查，不能据此排除或宣称不可达"
    if key == "virtual_load_queue":
        context = "\n".join(text[max(0, line-21):line+3])
        current = text[line-1]
        if "lastEnqCancel_next_r <=" in current:
            return ["VLQ-RACE", "VLQ-RECOVER"], "同拍被取消dispatch的预留流计数；补dispatch+redirect重叠，检查恢复尾部并重新使用取消区间"
        if "redirectCancelCount <=" in current:
            return ["VLQ-REDIRECT", "VLQ-RECOVER"], "捕获恢复取消数；补部分/全部/零取消、ROB slot边界与连续恢复，检查实际响应指针"
        if "io_lqRedirect_bits_" in context:
            return ["VLQ-RECOVER", "VLQ-TIMING"], "恢复指针有效响应；补规定多拍stall/响应和释放重叠，比较有效pointer而非无效payload"
        if "flipped_new_ptr" in context and "redirectCancelCount" in context:
            return ["VLQ-RECOVER", "VLQ-REUSE"], "非2幂恢复减法跨物理0号边界；补回绕位置的取消及恢复后完整区间复用"
        if "wire [3:0]   commitCount" in context or "_commitCount_T[4]" in context:
            return ["VLQ-ORDER", "VLQ-TIMING"], "首轮仅释放1至3项，缺少4至8项连续完成前缀；补不同长度前缀并比较计数/指针/非重复报告"
        if "lastNeedCancel_r_" in context:
            return ["VLQ-REDIRECT", "VLQ-RECOVER"], "取消快照的传递/变化；补跨全池的真实年轻项取消，检查保留项释放和恢复尾部"
        if re.search(r"robIdx_\d+_(?:flag|value|isFormer)\s*<=", context):
            return ["VLQ-INTERVAL", "VLQ-REDIRECT", "VLQ-REUSE"], "各槽位选择dispatch的ROB标签；补全部8入口覆盖完整120项，并以含flag/former差异的redirect和幸存项释放间接验证标签，不只写入即计通过"
        return [], "待人工审查，不能据此排除或宣称不可达"
    if key.startswith("cam_"):
        if dependency:
            return ["CAM-TIMING", "CAM-HOLD"], "真实写流水的使能/传递；补充连续写、空拍、禁用payload和规定提交边沿的查询检查"
        context = "\n".join(text[max(0, line-4):line+3])
        if "data_" in context or "WriteEn" in context:
            return ["CAM-WRITE", "CAM-TIMING", "CAM-REUSE"], "目标槽位的写入/提交路径；补齐所有槽位和bank边界、其余写入口、同/跨bank并行与连续覆盖，并通过真实查询验证"
        return [], "待人工审查，不能据此排除或宣称不可达"
    if write_region and write_region[0] <= line <= write_region[1]:
        return ["FL-RETURN", "FL-CONGESTION", "FL-ORDER", "FL-WRAP"], "回收批次实际写回可分配池；补充单/多通道、部分批次、拥塞与跨尾边界的回收并再分配检查"
    context = "\n".join(text[max(0, line-5):line+2])
    if "tailPtr" in context:
        return ["FL-RETURN", "FL-WRAP", "FL-OVERLAP"], "回收推进容量与尾部生命周期；补充延迟回收、尾部回绕和分配重叠"
    if "freeReq" in context or "freeSlotOH" in context:
        return ["FL-RETURN", "FL-CONGESTION"], "回收通道选择/传递批次；补充同通道积压和连续通知"
    return [], "待人工审查，不能据此排除或宣称不可达"


def audit(name, report_name="line-audit.json"):
    if Path(report_name).name != report_name or report_name in (".", ".."):
        raise ValueError("audit output must be one filename under the run")
    execution = ROOT / "results" / name / "execution"
    manifest = json.loads((execution / "manifest.json").read_text())
    assert manifest["state"] == "committed" and manifest["coverage_complete"]
    specs = json.loads((ROOT / "manifest/duts.json").read_text())["duts"]
    native_by_directory = {}
    for row in manifest["artifacts"]:
        p = Path(row["path"])
        assert hashlib.sha256(p.read_bytes()).hexdigest() == row["sha256"], p
        if row["kind"] == "native":
            native_by_directory[p.parent] = row["build"]
    rows = []
    for artifact in manifest["artifacts"]:
        if artifact["kind"] != "lcov":
            continue
        info = Path(artifact["path"])
        build = native_by_directory[info.parent]
        for path, sha in build["files"].items():
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha, path
        matches = [(key, spec) for key, spec in specs.items() if "DUT" + spec["export_name"] == build["name"]]
        assert len(matches) == 1
        key, spec = matches[0]
        tables = lcov(info)
        body = ROOT / "dut" / key / (spec["export_name"] + ".v")
        counts = tables[str(body)]
        pinned = json.loads((ROOT / "rtl" / key / "source.json").read_text())["files"]
        # Picker's renamed filename contains the original unmodified module bytes.
        assert hashlib.sha256(body.read_bytes()).hexdigest() == pinned[spec["top"] + ".sv"]
        text = body.read_text().splitlines()
        writes = [i+1 for i, s in enumerate(text) if re.search(r"freeList_\d+ <= _freeList", s)]
        region = (min(writes)-2, max(writes)+1) if writes else None
        gaps = []
        for line, hits in sorted(counts.items()):
            if hits:
                continue
            features, explanation = meaning(line, text, region, key=key)
            gaps.append({"line": line, "text": text[line-1].strip(), "features": features,
                         "classification": "missing_scenario_of_existing_feature" if features else "needs_review",
                         "semantic_gap": explanation, "reachability": "not_excluded"})
        hits = sum(bool(c) for c in counts.values())
        row = {"dut": key, "top": spec["top"], "source": str(body.relative_to(ROOT)),
                     "source_sha256": hashlib.sha256(body.read_bytes()).hexdigest(),
                     "lcov": str(info.relative_to(ROOT)), "build_id": build["build_id"],
                     "line_hit": hits, "line_total": len(counts),
                     "line_percent": round(100 * hits / len(counts), 4), "uncovered": gaps}
        if len(pinned) > 1:
            dependencies = []
            for source_name, sha in pinned.items():
                if source_name == spec["top"] + ".sv":
                    continue
                path = ROOT / "rtl" / key / source_name
                assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
                table = tables.get(str(path), {})
                dep_text = path.read_text().splitlines()
                missing = []
                for number, count in sorted(table.items()):
                    if count:
                        continue
                    features, explanation = meaning(number, dep_text, None, key=key, dependency=True)
                    missing.append({"line": number, "text": dep_text[number-1].strip(),
                                    "features": features, "classification": "missing_scenario_of_existing_feature" if features else "needs_review",
                                    "semantic_gap": explanation, "reachability": "not_excluded"})
                dependencies.append({"source": str(path.relative_to(ROOT)), "sha256": sha,
                                     "instrumentation": "native_DA" if table else "no_native_DA_records_not_claimed_covered",
                                     "line_hit": sum(bool(c) for c in table.values()), "line_total": len(table), "uncovered": missing})
            row["dependencies"] = dependencies
            row["closure_line_hit"] = hits + sum(d["line_hit"] for d in dependencies)
            row["closure_line_total"] = len(counts) + sum(d["line_total"] for d in dependencies)
        rows.append(row)
    functional = json.loads((execution / "functional-coverage.json").read_text())
    groups = []
    for group in functional["groups"]:
        assert group["collection_complete"]
        point = group["points"][0]
        assert not point["unknown"] and not point["unmatched"]
        counts = point["counts"]
        groups.append({"instance": group["instance"], "hit": sum(bool(c) for c in counts.values()),
                       "total": len(counts), "missing": [k for k,c in counts.items() if not c]})
    report = {"run": name, "pytest_exitstatus": manifest["pytest_exitstatus"],
              "tests": manifest["tests"],
              "scope": "exact_original_DUT_closure_excludes_picker_export_wrappers" if any("dependencies" in r for r in rows) else "exact_original_DUT_body_excludes_picker_export_wrappers",
              "native": sorted(rows, key=lambda r: r["dut"]), "functional": groups}
    assert report["run"] == execution.parent.name
    out = execution.parent / report_name
    if out.exists() and json.loads(out.read_text()) != report:
        raise RuntimeError("refusing to overwrite different historical audit")
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    for row in report["native"]:
        kinds = Counter(g["classification"] for g in row["uncovered"])
        print(f"{row['dut']}: {row['line_hit']}/{row['line_total']} = {row['line_percent']:.2f}% ; missing={len(row['uncovered'])} {dict(kinds)}")
    for group in groups:
        if group["instance"].endswith("checked"):
            print(group["instance"],f"{group['hit']}/{group['total']} checked scenarios", "missing:", ", ".join(group["missing"]))
    print("complete line inventory:", out.relative_to(ROOT))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--report-name", default="line-audit.json")
    args = parser.parse_args()
    audit(args.name, args.report_name)
