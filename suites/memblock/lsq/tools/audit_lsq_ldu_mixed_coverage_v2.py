#!/usr/bin/env python3
"""Per-line mixed gaps including RAR coherence-vector capture, not just uops.

Preserve v1's rejected narrower RAR-context assumption and every raw DA line.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import re
import shutil

from audit_lq_gaps import locate as load_locate
from audit_lsq_gaps import load_features, locate_store
from audit_lsq_normal_coverage_v1 import sources
from audit_sq_initial import ROOT, sha, verify_common


def classify(native):
    result=copy.deepcopy(native)
    counts=Counter()
    for entry in(result,*result["dependencies"]):
        file=Path(entry["source"]).name
        lines=(ROOT/entry["source"]).read_text().splitlines()
        for gap in entry["uncovered"]:
            n=gap["line"]
            assert gap["text"]==lines[n-1].strip()
            context="\n".join(lines[max(0,n-4):n+3])
            if file=="LoadQueueRAR.sv":
                if "matchMask" in context:
                    features=["LSQ-RAR.current_release","LSQ-RAR.previous_release","LSQ-RAR.revoke"]
                    why="coherence release匹配向量变化时捕获/保持的缺少情形；补同line/异line连续release、同/前拍分配和原reader回收后的负查询。它不是ROB/LQ保存分支，也不是新整类功能遗漏"
                elif re.search(r"uop_\d+_",context):
                    features=["LDU-RAR.full_pool","LSQ-RAR.head_reclaim","LSQ-RAR.revoke"]
                    why="原8种子停止前缀未访问此RAR记录/入口的原ROB/LQ保存情形；补正常全池、多入口、真实nuke/回收及同槽新UID。独立定向3898/3898不挪作本目录分子"
                else:
                    original,why=load_locate(file,gap)
                    features=[v for f in original for v in load_features(f)]
            elif file=="LqPAddrModule.sv":
                features=["LDU-RAR.full_pool","LSQ-RAR.current_release","LSQ-RAR.head_reclaim"]
                why="真实RAR CAM的记录/入口写入缺少情形；需正常全96记录与各入口、原PA查询及release/head回收证明，不以保存行命中当完整语义"
            elif file in("VirtualStoreQueue.sv","PhysicalStoreQueue.sv"):
                if file=="VirtualStoreQueue.sv":
                    features=["LSQ-ALLOC.all_lanes","LSQ-ALLOC.sq_capacity","LSQ-ALLOC.multi_flow","LSQ-ALLOC.sq_wrap","LSQ-RECOVER.partial"]
                    why="虚拟槽ROB/flow/exclusive-end或恢复保存缺情形；补128虚拟与当前64物理窗口、真实执行/ROB退休/副作用/连续释放，CBO按正常许可分阶段"
                elif "cboType" in context or "cboSetVec" in context:
                    features=["LSQ-RETIRE.cbo","LSQ-RETIRE.zero_ownership","LSQ-EXCEPTION.cache_wb"]
                    why="具体PSQ槽/STA入口的CBO属性保存尚未访问；须QB包、NoSpec/BlockBack、原Cache/zero/WB/SQ完成，不能由普通Store行命中替代或抵消失败"
                else:
                    features=["LSQ-ALLOC.sq_capacity","LSQ-ALLOC.sq_wrap","LSQ-FORWARD.youngest","LSQ-RETIRE.ordinary"]
                    why="具体PSQ槽/入口的数据或控制保存缺情形；补原STA/S2/STD次序、最年轻PA字节和Sbuffer/SQ原UID完成"
            elif file in("ForwardModule.sv","DeqModule.sv","EnterSbufferQueue.sv","UnalignQueue.sv"):
                features,why=locate_store(file,gap)
                if file=="ForwardModule.sv":why="非零head低年龄优先分组未激活；须真实SQ回绕和完整SQ代、当前最年轻PA字节，不能借接口绿色或叶子分子"
                if file=="UnalignQueue.sv":why="Store跨页第二PA两项保存/消费/取消缺情形；本轮18次Load head/tail不替代Store UQ首末STA和第二页Sbuffer字节"
            else:
                original,why=load_locate(file,gap)
                features=[v for f in original for v in load_features(f)]
                if file=="LoadQueueRAW.sv":why="RAW记录/入口/候选或CAM流水缺情形；须真实老STA对应56池Load字节、双store恢复/训练；fullSQ exclusive128先核对合同/最小例，不能 blanket 放宽年龄"
                elif file=="LoadQueueReplay.sv":why="120池slot/入口/原因、依赖或标签保存/选择缺情形；补原slot grant/反馈及真实SQ/TLB/refill/特殊模式；C_WF=false不伪造正常cause7也不删除接口UT"
                elif file=="VirtualLoadQueue.sv":why="LQ槽/稀疏入口/多flow/跨120保存或恢复分支缺情形；补正常满LQ与完整恢复原UID，不以两种子公平成功替代容量"
                elif file.startswith("FreeList"):why="真实父池的回收批次/通道/尾对齐及再分配缺情形；需本层完成/取消、同槽新UID再次完成，不借叶子行覆盖"
                elif file.startswith("UncacheEntry") or file=="LoadQueueUncache.sv":why="真实16原entry的排序/请求/确认回包/NC-MMIO再执行、异常或取消缺情形；补SID真实resp后复用、三bypass原错误字节和外部job清理；guarded defaults留原分母"
            assert features
            gap.update(features=sorted(set(features)),classification="missing_scenario_of_existing_feature",semantic_gap=why,reachability="not_excluded",
                       original_context=[dict(line=k,text=lines[k-1]) for k in range(max(1,n-2),min(len(lines),n+2)+1)],
                       scope="THIS_8_SEED_LDU_MIXED_OWN_NATIVE_DA_NOT_INTERFACE_OR_LEAF_UNION")
            counts[file]+=1
    assert sum(counts.values())==native["closure_line_total"]-native["closure_line_hit"]
    return result,counts


def audit(name):
    assert name=="lsq-ldu-mixed-02"
    run=ROOT/"results"/name
    manifest,source,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":2,"FAIL":6}
    native,tables=sources(run)
    mapped,counts=classify(native)
    assert sum(counts.values())==20833 and native["closure_line_hit"]==38769 and native["closure_line_total"]==59602
    rar=next(d for d in mapped["dependencies"] if d["source"].endswith("LoadQueueRAR.sv"))
    assert next(g for g in rar["uncovered"] if g["line"]==9172)["text"]=="matchMask_r_0}) begin"
    evidence=json.loads((run/"ldu-mixed-audit-v1.json").read_text())
    assert evidence["actually_complete_seeds"]==[28929,28933] and evidence["counts"]["allocated"]==746
    old,a=sources(ROOT/"results/lsq-serialized-mixed-01")
    added=lost=0
    for file,b in tables.items():
        assert a[file].keys()==b.keys()
        added+=sum(not a[file][n] and bool(b[n]) for n in b)
        lost+=sum(bool(a[file][n]) and not b[n] for n in b)
    assert added-lost==38769-old["closure_line_hit"]
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_lsq_ldu_mixed_coverage_v1.py",ROOT/"tools/audit_lsq_ldu_rar_coverage_v1.py"):
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    report=dict(run=name,status="OWN_8_SEED_DA_GAPS_INDIVIDUALLY_CLASSIFIED_RETAIN_6_FAILS_NOT_WHOLE_SCOPE_SIGNOFF",tests=manifest["tests"],snapshot_files=len(source),
                own_hit=38769,original_denominator=59602,raw_remaining=20833,missing_by_source=dict(counts),native_classified=mapped,
                prior_different_producer=dict(run="lsq-serialized-mixed-01",own_hit=old["closure_line_hit"],new_only_hits=added,prior_only_hits=lost,monotone_improvement_claim=False),
                preserved_v1_rejection="v1 reused the small directed RAR classifier and rejected line9172 matchMask_r_0 because its context is coherence-vector capture, not a uop identity write. v2 explicitly maps that existing release/match scenario; all raw DA/gaps retained and no normal-domain or functional gate weakened.",
                auditors=hashes,limits="Original53-source own DA only, per-line text/context/features retained. Different producer sequences are not a monotone coverage comparison. Two actual full-seed passes/148 same-slot witnesses do not replace six strict failures, remaining legal joint capacity/CBO stages, exact128, late local reset or final full-request audit. No leaf/interface numerator merge, DA exclusions, retroactive checked or goal completion.")
    out=run/"ldu-mixed-coverage-audit-v2.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="native_classified"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
