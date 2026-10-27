#!/usr/bin/env python3
"""Current original8 mixed subset's own DA and explicit remaining semantic gaps."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_ldu_rar_coverage_v1 import classify
from audit_lsq_normal_coverage_v1 import sources
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name=="lsq-ldu-mixed-02"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":2,"FAIL":6}
    native,tables=sources(run)
    mapped,counts=classify(native)
    for entry in(mapped,*mapped["dependencies"]):
        file=Path(entry["source"]).name
        for gap in entry["uncovered"]:
            if file in("LoadQueueRAR.sv","LqPAddrModule.sv"):
                why="本8种子实际停止前缀缺少此RAR记录/入口的原ROB/LQ保存情形；补正常全池、各入口、原nuke与真实head/revoke/redirect回收及同槽新UID。正常LDU定向已有3898/3898但属于独立目录，不挪用其分子"
            elif file=="LoadQueueRAW.sv" or file.startswith(("LqPAddrModule_1","LqMaskModule")):
                why="本轮未命中的RAW记录/入口/候选选择或CAM流水情形；须真实较老STA对应56池各Load身份/字节、双store恢复和训练。满SQ exclusive128先核对RAW合同和参考，不能无证放宽通用年龄函数"
            elif file=="LoadQueueReplay.sv":
                why="本轮少量重放原slot尚未访问此120池/入口/原因或依赖标签保存与选择情形；补真实原slot grant/反馈、SQ就绪及TLB/refill/特殊模式。固定LDU C_WF=false，不把接口cause7伪造为正常生产者或删除独立Replay接口义务"
            elif file=="VirtualLoadQueue.sv":
                why="原8种子及取消同槽cleanup尚未访问此LQ槽/稀疏入口/多flow/跨120保存或恢复分支；须正常满LQ及完整恢复原UID，不以两种子公平成功替代完整容量"
            elif file=="VirtualStoreQueue.sv":
                why="尚缺此虚拟SQ槽的ROB/flow/exclusive end、稀疏末项或退休/恢复情形；补128虚拟占用与当前64物理窗口、真实执行/ROB退休/副作用/连续释放，CBO仍按正常串行分阶段"
            elif file=="PhysicalStoreQueue.sv":
                why="本轮未遍历此PSQ槽/STA入口的数据、控制或CBO属性保存；补真实原STA/S2/STD与各槽opcode、Forward PA字节/Sbuffer/Cache/WB/SQ释放。原Cache held-WB、flush和非法释放FAIL保留"
            elif file.startswith("FreeList"):
                why="所属真实父池的回收批次/通道/尾部对齐和再分配仍缺此情形；需正常池容量、真实完成/取消、同槽新UID并再次完成，不借独立FreeList行覆盖"
            elif file.startswith("UncacheEntry") or file in("LoadQueueUncache.sv","FastArbiter_2.sv","PipelineRegModule.sv","TwoLevelRRArbiter_1.sv"):
                why="本轮未遍历全部16原entry的排序/弹性请求/确认回包/NC-MMIO再执行/异常汇聚或取消情形；需原SID真实响应后复用、三bypass及原错误/字节、未返回job清理。guarded defaults继续保留原分母和单独窄证明边界"
            elif file=="ForwardModule.sv":
                why="本轮未激活对应非零head/完整SQ代的低年龄优先分组；补真实SQ窗口回绕与当前最年轻原PA字节，不以原源错误的接口绿色提升正常域"
            elif file=="UnalignQueue.sv":
                why="Store跨页第二PA的真实两项保存/消费/取消未遍历此行；本轮Load的18次head/tail不替代Store UQ首末STA和第二页Sbuffer字节检查"
            elif file in("DeqModule.sv","EnterSbufferQueue.sv"):
                why="真实Store消费/奇偶尾/双入口或特殊状态未遍历此行；补正常普通/NC/IO/串行CBO与老已退休Sbuffer条件。保留3WB错误、2flush相位和1非法SQ释放，不用局部通过抵消"
            else:raise AssertionError((file,gap))
            gap["semantic_gap"]=why
            gap["scope"]="THIS_8_SEED_LDU_MIXED_OWN_NATIVE_DA_NOT_PRIOR_INTERFACE_OR_LEAF_UNION"
    assert sum(counts.values())==native["closure_line_total"]-native["closure_line_hit"]==20833
    assert native["closure_line_hit"]==38769 and native["line_hit"]==114
    evidence=json.loads((run/"ldu-mixed-audit-v1.json").read_text())
    assert evidence["actually_complete_seeds"]==[28929,28933] and evidence["counts"]["allocated"]==746
    # Compare exact sets without calling different producer histories monotone.
    old,prior_tables=sources(ROOT/"results/lsq-serialized-mixed-01")
    added=lost=0
    for file,counts_now in tables.items():
        a,b=prior_tables[file],counts_now
        assert a.keys()==b.keys()
        added+=sum(not a[n] and bool(b[n]) for n in b)
        lost+=sum(bool(a[n]) and not b[n] for n in b)
    assert added-lost==38769-old["closure_line_hit"]
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_lsq_ldu_rar_coverage_v1.py"):
        copy=dest/file.name
        if copy.exists():assert sha(copy)==sha(file)
        else:shutil.copy2(file,copy)
        hashes[file.name]=sha(file)
    report=dict(run=name,status="OWN_8_SEED_DA_GAPS_INDIVIDUALLY_CLASSIFIED_NOT_FULL_RANDOM_OR_WRAPPER_COVERAGE_SIGNOFF",tests=manifest["tests"],snapshot_files=len(source),
                own_hit=38769,original_denominator=59602,raw_remaining=20833,missing_by_source=dict(counts),native_classified=mapped,
                prior_different_producer=dict(run="lsq-serialized-mixed-01",own_hit=old["closure_line_hit"],new_only_hits=added,prior_only_hits=lost,
                                              monotone_coverage_improvement_claim=False,reason="fixed LDU scheduling changes actual kind/alias/backpressure interleaving; all prior eight FAILs and raw DA stay separate"),
                classification="remaining lines are missing cases of already defined full-Wrapper semantics; earlier wrong LDU routing/revoke was an actual producer-feature omission, separately corrected before these tests",
                auditors=hashes,limits="All raw53-source DA retained with original text/context and existing feature IDs. This run's two fair/restore passes do not replace six strict failure prefixes, legal joint capacity/CBO phases, exact128 review, other required scenarios or final request/evidence audit. No old317/leaf numerators, exclusions, retroactive checked bits or whole-goal completion.")
    out=run/"ldu-mixed-coverage-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="native_classified"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
