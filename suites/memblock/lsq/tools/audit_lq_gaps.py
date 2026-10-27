#!/usr/bin/env python3
"""Per-DA first-round LoadQueue closure inventory; never excludes a raw line."""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path

from audit_sq_initial import ROOT, sha


def locate(name, gap):
    line, text = gap["line"], gap["text"]
    if name == "VirtualLoadQueue.sv":
        if "Cancel" in text or "Redirect" in text or "lastNeed" in text or "flipped_new_ptr" in text:
            return ["LQ-RECOVER.partial", "LQ-RECOVER.all", "LQ-RECOVER.reuse"], "共享redirect的取消历史/恢复指针路径；补部分/全取消、回绕和同槽新UID实际完成"
        return ["LQ-ALLOC.capacity", "LQ-ALLOC.wrap", "LQ-HEAD.rollover"], "未访问虚拟slot或更长完成前缀/回绕保存路径；补120项满池、全部8入口、多flow及跨120边界实际消费，不以写入计完成"
    if name == "LoadQueueRAR.sv":
        if "release" in text.lower():
            return ["LQ-RAR.release", "LQ-RAR.previous_release"], "release完整line窗口及hash记录标记在本层缺情形；补当前/前拍和负对照，原严格失败仍保留"
        return ["LQ-RAR.all_slots", "LQ-RAR.revoke", "LQ-HEAD.rar_release"], "真实RAR槽的三入口身份保存/撤销/回收缺情形；补96槽及入口轮换，以nuke及VLQ自动回收后负查询检查"
    if name == "LoadQueueRAW.sv":
        if 7821 <= line <= 7933 or line >= 17128:
            return ["LQ-RAW.dual_store", "LQ-RAW.all_slots", "LQ-RAW.train"], "另一store入口和候选选择组/恢复元信息路径；补两个store及56槽最老选择，核对RAW恢复与MDP训练各自load/store身份"
        return ["LQ-RAW.all_slots", "LQ-RAW.negative", "LQ-RAW.revoke"], "真实RAW槽dataValid/ROB/SQ/FTQ/checkpoint保存及两拍撤销路径；补三load入口×56槽，字节/年龄/PA负对照和实际恢复"
    if name == "LoadQueueReplay.sv":
        if 10191 <= line <= 10592:
            return ["LQ-HEAD.replay_priority", "LQ-HEAD.rollover"], "真实VLQ head/头后候选优先选择缺情形；通过真实S3完成改变head，不允许直驱ldWbPtr"
        if 33684 <= line <= 35363:
            return ["LQ-STORE.address", "LQ-STORE.data", "LQ-STORE.strict", "LQ-STORE.disabled"], "每slot依赖身份/strict保存或store wake路径；补SQ指针位图与STA/STD有效/禁用反例，不放宽原strict合同"
        if 35973 <= line <= 37406 or 58800 <= line <= 58827:
            return ["LQ-HINT.refill", "LQ-HINT.l2", "LQ-HINT.tlb", "LQ-HINT.fast_tlb", "LQ-UNCACHE.wake"], "MSHR/TLB标签与refill/hint/内部Uncache wake历史；补真实两channel标签正反与阶段边沿，不能伪造内部wake"
        if line in (38165, 38168, 61615, 61616, 61617):
            return ["LQ-SPECIAL.threshold", "LQ-SPECIAL.head_change"], "ROB下一head的eligible等待/2048阈值及身份保存缺失；补精确边界与head改变"
        return ["LQ-CAPACITY.replay_pool", "LQ-REPLAY.causes", "LQ-REPLAY.update", "LQ-REPLAY.metadata"], "未访问Replay slot/入口及完整load元信息或原因状态保存；补120 owner×三入口、原因0..11、真实输出后同slot反馈更新/释放，不借叶子覆盖替代"
    if name == "LoadQueueUncache.sv":
        if 2758 <= line <= 3556:
            return ["LQ-UNCACHE.bypass", "LQ-UNCACHE.errors", "LQ-UNCACHE.all_entries"], "三bypass通道选择真实entry地址/数据/错误；补16 entry×NC/MMIO×三lane，六条guarded default保留原分母并另作结构证明"
        if 7450 <= line <= 7982:
            return ["LQ-UNCACHE.errors", "LQ-UNCACHE.all_entries"], "消费时异常元信息汇聚选择高entry，补所有真实entry的fullva/gpaddr/错误比较和同时消费优先"
        if 3566 <= line <= 3609:
            return ["LQ-UNCACHE.full", "LQ-RECOVER.sent_uncache"], "真实Uncache池拒绝/rollback及历史redirect路径；补满16、部分拒绝、已发总线取消与回包后复用"
        return ["LQ-UNCACHE.nc", "LQ-UNCACHE.mmio", "LQ-UNCACHE.all_entries", "LQ-UNCACHE.sid_reuse"], "本层首轮尚无完整Uncache事务，真实排序/分配/路由保存缺测试；补NC/MMIO总线→内部wake→Replay→bypass消费及SID返回后复用"
    if name.startswith("UncacheEntry"):
        return ["LQ-UNCACHE.nc", "LQ-UNCACHE.mmio", "LQ-UNCACHE.errors", "LQ-RECOVER.sent_uncache"], "真实ID特化entry的请求/回执/回包/wake/数据消费和取消状态迁移缺业务；必须经本层共享S3与bus、Replay再执行激活并核验原UID"
    if name.startswith("FreeList"):
        features = {"FreeList.sv": ["LQ-CAPACITY.rar_wake", "LQ-RAR.all_slots"],
                    "FreeList_1.sv": ["LQ-CAPACITY.raw_wake", "LQ-RAW.all_slots"],
                    "FreeList_2.sv": ["LQ-CAPACITY.replay_pool", "LQ-REPLAY.update"],
                    "FreeList_3.sv": ["LQ-UNCACHE.full", "LQ-UNCACHE.all_entries"]}[name]
        return features, "实际业务父队列的回收通道、批次写回或池指针路径；按所属RAR/RAW/Replay/Uncache填满并实际回收后重新分配检查，不用独立FreeList覆盖替代"
    if name.startswith(("LqPAddrModule", "LqMaskModule")):
        return ["LQ-RAR.all_slots" if name == "LqPAddrModule.sv" else "LQ-RAW.all_slots"], "真实CAM各槽位从三load入口的bank写入/流水使能路径；补父块全槽、不同地址/mask并经真实RAR nuke或RAW恢复读回证明"
    assert name in ("FastArbiter_2.sv", "PipelineRegModule.sv", "TwoLevelRRArbiter_1.sv"), (name, gap)
    return ["LQ-UNCACHE.all_entries", "LQ-UNCACHE.nc", "LQ-UNCACHE.mmio", "LQ-UNCACHE.full"], "真实Uncache仲裁与弹性请求流水缺外部事务；补16 entry、两组竞争、总线背压及同拍替换，检查原UID/地址且最终实际消费"


def audit(name):
    run = ROOT / "results" / name
    raw = run / "line-audit.json"
    report = copy.deepcopy(json.loads(raw.read_text()))
    assert len(report["native"]) == 1 and report["native"][0]["dut"] == "load_queue"
    native = report["native"][0]
    assert not native["uncovered"]
    counts = Counter()
    for dep in native["dependencies"]:
        for gap in dep["uncovered"]:
            features, why = locate(Path(dep["source"]).name, gap)
            gap.update(features=features, classification="missing_scenario_of_existing_feature", semantic_gap=why,
                       reachability="not_excluded", scope="real_LoadQueue_closure_not_leaf_substitution")
            counts[Path(dep["source"]).name] += 1
    report.update(raw_line_audit_sha256=sha(raw), classification_counts=dict(counts),
                  missing_lines=sum(counts.values()), note="All missing DA retained individually. All mapped obligations existed in the pre-test LoadQueue contract; no newly discovered whole behavior is silently added. This is a stimulus-gap inventory, not an unreachability or semantic-success proof.")
    assert report["missing_lines"] == native["closure_line_total"] - native["closure_line_hit"]
    out = run / "line-audit-classified.json"
    if out.exists():
        assert json.loads(out.read_text()) == report
    else:
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: report[k] for k in ("run", "tests", "missing_lines", "classification_counts", "raw_line_audit_sha256", "note")}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    audit(parser.parse_args().name)
