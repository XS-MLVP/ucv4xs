#!/usr/bin/env python3
"""Own phased program DA gaps, exact set gain/loss and next semantic cases."""
import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

from audit_lsq_ldu_mixed_coverage_v2 import classify
from audit_progress_run_v10 import coverage_signature
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name in ("lsq-ldu-joint-phases-03","lsq-ldu-joint-phases-04","lsq-ldu-joint-phases-05")
    run=ROOT/"results"/name
    manifest,source,_=verify_common(run)
    native=json.loads((run/"line-audit.json").read_text())["native"][0]
    mapped,counts=classify(native)
    for item in (mapped,*mapped["dependencies"]):
        file=Path(item["source"]).name
        for gap in item["uncovered"]:
            gap["scope"]="THIS_PHASED_NATIVE_RUN_OWN_DA_NOT_FULL_MIXED_OR_LEAF_UNION"
            if file=="LsqWrapperDut.v":
                assert gap["line"] in (1505,1507,1508)
                gap.update(features=["LSQ-BUS.serial","LSQ-BUS.ack_route","LSQ-BUS.resp_route"],
                           semantic_gap="outstanding=false串行pendingstate仲裁与原响应归空缺情形；补五正常NC/MMIO/IO Load与NC/IO Store，真实总线/源S3或WB/SQ完成，不能只翻开关",classification="missing_scenario_of_existing_feature")
            elif file=="LoadQueueRAR.sv":
                gap["semantic_gap"]="本容量程序无coherence release/nuke；缺具体记录的release匹配向量、原读者状态及取消/回收情形。补真实同/前拍release与RAR flushAfter，不以96静态占用作全部功能完成"
            elif file=="LoadQueueReplay.sv":
                gap["semantic_gap"]="已真实满120并原slot反馈，但主原因限首次NC、RAR/RAW容量。缺TLB/cache/strict/data依赖/标签/多入口组合及真实wake/反馈情形；不能以全slot计数替代"
            elif file=="LoadQueueRAW.sv":
                gap["semantic_gap"]="已真实56记录及向前exclusive128，当前PA互不相交；缺真实较老STA字节冲突、双store恢复选择/训练和候选状态变化。按公开完整signature而非虚构内部slot补例"
            elif file=="VirtualLoadQueue.sv":
                gap["semantic_gap"]="三代满LQ/恢复已执行，但单flow分配与固定类型不能激活每种lane/flow/异常/回绕保存关系；补源正确多flow/入口/完成前缀，不借旧interface行分子"
            elif file=="PhysicalStoreQueue.sv":
                gap["semantic_gap"]="普通128窗口及独立CBO0..3已执行；仍缺具体PSQ槽×STA lane的CBO/跨页/部分数据与副作用情形。CBO必须NoSpec/BlockBack，老Sbuffer/zero/WB失败不排除"
            elif file=="VirtualStoreQueue.sv":
                gap["semantic_gap"]="虚拟128单flow跨代已执行，剩真实退休前缀walk/多flow/恢复end选择缺情形；必须保留未消费老Store与实际恢复指针"
            elif file.startswith("FreeList"):
                gap["semantic_gap"]="父池满/恢复已执行，仍缺回收批次、bank、可变尾对齐与再分配组合；须原UID义务及同槽新UID实际完成"
            elif file=="LoadQueueUncache.sv" or file.startswith("UncacheEntry"):
                gap["semantic_gap"]="本容量以clean NC为主；需正常串行NC/MMIO/IO、原SID数据/错误/取消与16 entry情况，guarded defaults仍留分母。period1 SID反例与period8正条件分列"
    previous={}
    if name.endswith("04") or name.endswith("05"):
        prior=ROOT/"results"/("lsq-ldu-joint-phases-03" if name.endswith("04") else "lsq-ldu-joint-phases-04")
        old=json.loads((prior/"line-audit.json").read_text())["native"][0]
        before,after=coverage_signature(old),coverage_signature(native)
        assert before.keys()==after.keys()
        added=lost=0
        per_source={}
        for file,(digest,lines) in after.items():
            assert before[file][0]==digest and dict(before[file][1]).keys()==dict(lines).keys()
            a=dict(before[file][1])
            gain=sum(hit and not a[n] for n,hit in lines)
            loss=sum(a[n] and not hit for n,hit in lines)
            per_source[Path(file).name]=dict(added=gain,lost=loss)
            added+=gain
            lost+=loss
        assert not lost
        previous=dict(run=prior.name,old_own_hit=old["closure_line_hit"],new_only=added,old_only=lost,by_source=per_source)
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(run=name,status="OWN_PHASED_DA_EACH_GAP_CLASSIFIED_NOT_WHOLE_GOAL_SIGNOFF",tests=manifest["tests"],snapshot_files=len(source),
                own_hit=native["closure_line_hit"],original_denominator=native["closure_line_total"],own_top_hit=native["line_hit"],own_top_total=native["line_total"],
                remaining=sum(counts.values()),missing_by_source=dict(counts),comparison=previous,native_classified=mapped,auditor_SHA256=sha(Path(__file__)),
                next_cases="Actual03 top1505/1507/1508 existing serial-ownership scenario missing: five normal special types x three lanes. This classifies a missing situation, not a new whole function. The cross-pool native timing/revoke plus CBO admission relation was the separate whole relationship missing in old joint streams.",
                limits="Original53-file native DA only, all exact source/line/context/features retained; no DA exclusion or leaf/interface numerator merge. Positive cadence does not waive original SID failures or full8 mixed obligations; untested vector/multi-flow/split errors/late local-only reset remain, STRESS and goal not signed off.")
    out=run/"ldu-joint-coverage-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="native_classified"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
