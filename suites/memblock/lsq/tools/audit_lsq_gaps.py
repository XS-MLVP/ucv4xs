#!/usr/bin/env python3
"""Per-line first real wrapper closure gap inventory, not a leaf-coverage merge."""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil

from audit_lq_gaps import locate as locate_load
from audit_psq_initial import classify as classify_physical
from audit_sq_initial import ROOT, sha


def load_features(feature):
    group, case = feature.split(".", 1)
    if group == "LQ-ALLOC":
        return ["LSQ-ALLOC." + {"capacity": "lq_capacity", "wrap": "lq_wrap"}.get(case, case)]
    if group == "LQ-HEAD":
        return [{"rar_release": "LSQ-RAR.head_reclaim", "replay_priority": "LSQ-REPLAY.head", "rollover": "LSQ-ALLOC.lq_wrap"}[case]]
    if group == "LQ-RAR":
        return ["LSQ-RAR." + {"release": "current_release", "all_slots": "nc"}.get(case, case)]
    if group == "LQ-RAW":
        return ["LSQ-RAW." + {"all_slots": "conflict", "collision": "conflict", "negative": "mask_negative", "dual_store": "dual"}.get(case, case)]
    if group == "LQ-CAPACITY":
        return ["LSQ-REPLAY.capacity", "LSQ-STRESS.capacity"]
    if group == "LQ-REPLAY":
        return ["LSQ-REPLAY.head", "LSQ-STRESS.capacity"]
    if group == "LQ-STORE":
        return ["LSQ-REPLAY." + {"address": "sq_address", "data": "sq_data"}.get(case, case)]
    if group == "LQ-HINT":
        return ["LSQ-REPLAY." + ("tlb" if "tlb" in case else "refill")]
    if group == "LQ-UNCACHE":
        return [{"errors": "LSQ-EXCEPTION.load_fault", "bypass": "LSQ-BUS.resp_route", "sid_reuse": "LSQ-BUS.sid_reuse",
                 "full": "LSQ-STRESS.capacity", "wake": "LSQ-BUS.resp_route"}.get(case, "LSQ-BUS.load_only")]
    if group == "LQ-RECOVER":
        return ["LSQ-RECOVER." + ("sent_load" if case == "sent_uncache" else case)]
    if group == "LQ-SPECIAL":
        return ["LSQ-REPLAY.special"]
    raise AssertionError(("unreviewed original Load semantic mapping", feature))


def locate_store(name, gap):
    line = gap["line"]
    if name == "VirtualStoreQueue.sv":
        if 6477 <= line <= 14274:
            return ["LSQ-ALLOC.all_lanes", "LSQ-ALLOC.multi_flow", "LSQ-ALLOC.sq_wrap"], "各虚拟slot的ROB/flow/exclusive SQ end快照未保存；补混合八lane、128虚拟uop/flow与完整flags，真实后续退休/恢复及原字节写出证明"
        return ["LSQ-RECOVER.partial", "LSQ-RECOVER.retired_store", "LSQ-RECOVER.reuse"], "真实VSQ退休前缀/redirect release-walk、稀疏尾部与恢复指针路径；用同一全局ROB及真实PSQ释放反馈激活，取消后同物理SQ新UID完成"
    if name == "PhysicalStoreQueue.sv":
        classified = classify_physical({"uncovered": [copy.deepcopy(gap)], "dependencies": []})["uncovered"][0]
        gap.update({key: value for key, value in classified.items() if key in ("original_context", "nearest_original_entry_slots")})
        if "PSQ-SPECIAL" in classified["features"]:
            return ["LSQ-RETIRE.cbo", "LSQ-RETIRE.zero_ownership", "LSQ-EXCEPTION.cache_wb"], classified["semantic_gap"] + "；本层必须由真实VSQ和全局ROB许可，不能直驱preCommit"
        if "PSQ-RECOVER" in classified["features"]:
            return ["LSQ-RECOVER.partial", "LSQ-RECOVER.reuse"], classified["semantic_gap"] + "；同一redirect同时影响真实Load分支及外部总线义务"
        return ["LSQ-ALLOC.sq_capacity", "LSQ-ALLOC.sq_wrap", "LSQ-FORWARD.youngest", "LSQ-RETIRE.ordinary"], classified["semantic_gap"] + "；保留真实SQ→Load依赖反馈，不借独立PSQ行覆盖"
    if name == "DeqModule.sv":
        return ["LSQ-RETIRE.nc", "LSQ-RETIRE.io", "LSQ-BUS.store_only", "LSQ-BUS.ack_route", "LSQ-BUS.resp_route"], "真实Store特殊项尚未经过共享Uncache接受、方向确认/响应、实际WB与SQ完成；补NC/IO与Load竞争，分开副作用和外部未回响应义务"
    if name == "EnterSbufferQueue.sv":
        return ["LSQ-RETIRE.ordinary", "LSQ-RETIRE.multi_flow", "LSQ-ALLOC.sq_wrap"], "真实Sbuffer队列第二入口/奇偶尾/双出入压紧未遍历；补混合多flow写出与变长消费，逐UID原PA字节和credit守恒"
    if name == "ForwardModule.sv":
        return ["LSQ-FORWARD.youngest", "LSQ-FORWARD.alias", "LSQ-FORWARD.range", "LSQ-FORWARD.wrap", "LSQ-FORWARD.page"], "本层尚无实际Load forward查询；补真实STA/STD形成全64槽原始字节，再由三个Load阶段查询检查最年轻PA来源、缺就绪、别名/范围/完整SQ身份及跨页，而不是仅计保存或沿用叶子DA"
    assert name == "UnalignQueue.sv", name
    return ["LSQ-FORWARD.page", "LSQ-RECOVER.reuse", "LSQ-RETIRE.ordinary"], "真实UQ两槽第二PA、完整SQ匹配、消费/取消路径尚未激活；补跨页首末STA与真实Sbuffer第二页字节，取消后同槽新UID完成"


def audit(name):
    run = ROOT / "results" / name
    raw = run / "line-audit.json"
    report = copy.deepcopy(json.loads(raw.read_text()))
    assert len(report["native"]) == 1 and report["native"][0]["dut"] == "lsq_wrapper"
    native = report["native"][0]
    catalog = set()
    for line in (ROOT / "docs/contracts/lsq-wrapper.md").read_text().splitlines():
        if line.startswith("| LSQ-"):
            _, group, cases, *_ = line.split("|")
            catalog.update(group.strip() + "." + case.strip() for case in cases.split("/"))
    assert len(catalog) == 82
    counts = Counter()
    def assign(source, gap, features, explanation):
        assert set(features) <= catalog and features
        gap.update(features=sorted(set(features)), semantic_gap=explanation, classification="missing_scenario_of_existing_feature",
                   reachability="not_excluded", scope="real_LsqWrapper_full_closure_not_independent_leaf_coverage")
        counts[source] += 1
    for gap in native["uncovered"]:
        assert gap["line"] in (1502, 1504, 1505, 1507, 1508)
        features = (["LSQ-BUS.serial", "LSQ-BUS.nc_outstanding"] if gap["line"] == 1504 else
                    ["LSQ-BUS.serial", "LSQ-BUS.resp_route", "LSQ-BUS.cancelled_return"] if gap["line"] >= 1507 else
                    ["LSQ-BUS.load_only", "LSQ-BUS.store_only", "LSQ-BUS.older_load", "LSQ-BUS.older_store"])
        assign("LsqWrapper.sv", gap, features, "共享请求真实fire后串行占用/NC重叠及响应清理路径首轮未运行；必须由两真实队列产生候选，检查ROB年龄仲裁、ack不得提前解锁和原方向/SID响应才完成，不能直驱内部valid或把行命中当路由通过")
    store_sources = {"VirtualStoreQueue.sv", "PhysicalStoreQueue.sv", "DeqModule.sv", "EnterSbufferQueue.sv", "ForwardModule.sv", "UnalignQueue.sv"}
    for dep in native["dependencies"]:
        source = Path(dep["source"]).name
        assert sha(ROOT / dep["source"]) == dep["sha256"]
        for gap in dep["uncovered"]:
            if source in store_sources:
                features, explanation = locate_store(source, gap)
            elif source in ("DelayNWithValid_115.sv", "DelayNWithValid_64.sv", "DelayNWithValid_67.sv"):
                assert gap["line"] == 56
                features, explanation = ["LSQ-RAW.conflict", "LSQ-RAW.dual", "LSQ-RAW.revoke"], "真实RAW mask/partial-PA CAM的bank写地址与数据有效流水未捕获；补实际Load RAW查询接受和两个真实STA冲突，按规定延迟核对原身份/字节与撤销，不以通用Delay叶子代替"
            else:
                original, explanation = locate_load(source, gap)
                features = [mapped for feature in original for mapped in load_features(feature)]
                explanation = "本层不能直驱SQ反馈或用独立LoadQueue覆盖替代；" + explanation
            assign(source, gap, features, explanation)
    assert sum(counts.values()) == native["closure_line_total"] - native["closure_line_hit"]
    dest = run / "evidence-auditors" / Path(__file__).name
    dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        assert sha(dest) == sha(Path(__file__))
    else:
        shutil.copy2(Path(__file__), dest)
    report.update(raw_line_audit_sha256=sha(raw), missing_lines=sum(counts.values()), classification_counts=dict(counts),
                  newly_discovered_whole_features=[], auditor_sha256=sha(dest),
                  note="Every raw top/child DA gap retained individually. All obligations already exist in the pre-test 82-case wrapper contract; first run lacks their concrete cases, not the whole feature definition. No exclusions, numerator/denominator edits or independent-leaf coverage substitution. Mapping is a stimulus plan, NOT a reachability or functional proof.")
    output = run / "line-audit-classified.json"
    if output.exists():
        assert json.loads(output.read_text()) == report
    else:
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: report[key] for key in ("run", "tests", "missing_lines", "classification_counts", "newly_discovered_whole_features", "note")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
