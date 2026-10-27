#!/usr/bin/env python3
"""Exact own DA, top serial gaps and child per-line semantic classification."""
import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shutil

from audit_lsq_ldu_mixed_coverage_v2 import classify as child_classifier
from audit_progress_run_v10 import coverage_signature
from audit_sq_initial import ROOT, sha, verify_common


WHY={
    "LoadQueueRAR.sv":"本容量没有coherence release/nuke；缺具体记录的release匹配向量、原读者状态与取消/回收情形，96静态占用不代替原RAR flushAfter功能。",
    "LoadQueueRAW.sv":"已有56原记录与向前exclusive128，但当前PA互不相交；缺较老STA字节冲突、双store选择/训练与候选变化。逐公开signature核验，不虚构记录slot。",
    "LoadQueueReplay.sv":"已满120并原slot反馈，但主原因限首次NC与RAR/RAW容量；缺TLB/cache/strict/data依赖和入口/标签保存/真实wake情形，不以全slot计数替代。",
    "VirtualLoadQueue.sv":"三代满LQ与恢复已执行，单flow和固定类型未激活每种lane/flow/异常/回绕保存关系；补源正确分配、原完成前缀及恢复，不借旧接口分子。",
    "VirtualStoreQueue.sv":"虚拟128单flow已跨代，剩退休前缀walk/多flow/恢复end选择缺情形；须真实未消费老Store、退休状态和恢复指针。",
    "PhysicalStoreQueue.sv":"普通128窗口与独立CBO0..3已执行；缺具体PSQ槽/STA lane的CBO、跨页、部分数据和副作用关系；仍须NoSpec/BlockBack，老Sbuffer/zero/WB失败不排除。",
    "ForwardModule.sv":"当前多为唯一非别名PA，缺非零head的反转年龄优先组与真实最年轻字节查询情形；旧Forward失败和该目录命中分开。",
    "UnalignQueue.sv":"当前Store不跨页；缺首末STA、第二PA保存/消费/取消与同槽新UID的真实跨页情况，不以Load S4替代。",
    "DeqModule.sv":"本容量以普通Store和独立CBO为主；缺真实串行NC/IO或对应读写/响应/完成顺序情况，须实际总线/WB/SQ副作用，不能只翻开关。",
}


def classify(native):
    mapped=deepcopy(native)
    counts=Counter()
    # Classify each real child using its OWN unchanged line totals; old mixed
    # classifier has no Wrapper top mapping. Never alter DA to bypass it.
    for index,entry in enumerate(native["dependencies"]):
        one=deepcopy(entry)
        one["dependencies"]=[]
        one["closure_line_total"],one["closure_line_hit"]=entry["line_total"],entry["line_hit"]
        classified,_=child_classifier(one)
        mapped["dependencies"][index]["uncovered"]=classified["uncovered"]
    for entry in (mapped,*mapped["dependencies"]):
        file=Path(entry["source"]).name
        lines=(ROOT/entry["source"]).read_text().splitlines()
        for gap in entry["uncovered"]:
            n=gap["line"]
            assert lines[n-1].strip()==gap["text"]
            if file=="LsqWrapperDut.v":
                assert n in (1505,1507,1508)
                gap.update(features=["LSQ-BUS.serial","LSQ-BUS.ack_route","LSQ-BUS.resp_route"],
                           semantic_gap="outstanding=false串行pendingstate仲裁/原响应归空缺情形；补五种正常特殊Load/Store×三入口，真实总线/源S3或WB/SQ完成。",
                           original_context=[dict(line=k,text=lines[k-1]) for k in range(max(1,n-2),min(len(lines),n+2)+1)])
            elif file in WHY:gap["semantic_gap"]=WHY[file]
            elif file.startswith("FreeList"):
                gap["semantic_gap"]="父池满/恢复已执行，仍缺回收批次、bank、尾对齐与再分配组合；须原义务偿还与同槽新UID完成，不能借叶子行满。"
            elif file=="LoadQueueUncache.sv" or file.startswith("UncacheEntry"):
                gap["semantic_gap"]="容量以clean NC为主；缺正常串行NC/MMIO/IO、原SID数据/错误/取消与16 entry情况。guarded defaults保留分母，period1反例和period8正条件分列。"
            gap.update(classification="missing_scenario_of_existing_feature",scope="THIS_PHASED_RUN_OWN_NATIVE_DA_NOT_OLD_INTERFACE_OR_LEAF_UNION",reachability="not_excluded")
            assert gap["features"] and gap["semantic_gap"]
            counts[file]+=1
    assert sum(counts.values())==native["closure_line_total"]-native["closure_line_hit"]
    return mapped,counts


def audit(name):
    assert name in ("lsq-ldu-joint-phases-03","lsq-ldu-joint-phases-04","lsq-ldu-joint-phases-05")
    run=ROOT/"results"/name
    manifest,source,_=verify_common(run)
    native=json.loads((run/"line-audit.json").read_text())["native"][0]
    mapped,counts=classify(native)
    comparison={}
    if not name.endswith("03"):
        prior=ROOT/"results"/("lsq-ldu-joint-phases-04" if name.endswith("05") else "lsq-ldu-joint-phases-03")
        old=json.loads((prior/"line-audit.json").read_text())["native"][0]
        before,after=coverage_signature(old),coverage_signature(native)
        assert before.keys()==after.keys()
        per_source={}
        for file,(digest,lines) in after.items():
            assert before[file][0]==digest and dict(before[file][1]).keys()==dict(lines).keys()
            a=dict(before[file][1])
            per_source[Path(file).name]=dict(added=sum(hit and not a[n] for n,hit in lines),lost=sum(a[n] and not hit for n,hit in lines))
        added=sum(v["added"] for v in per_source.values())
        lost=sum(v["lost"] for v in per_source.values())
        assert not lost and native["closure_line_hit"]==old["closure_line_hit"]+added
        comparison=dict(prior_run=prior.name,prior_own_hit=old["closure_line_hit"],new_only=added,old_only=lost,by_source=per_source)
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_lsq_ldu_joint_coverage_v1.py",ROOT/"tools/audit_lsq_ldu_mixed_coverage_v2.py"):
        target=dest/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    report=dict(run=name,status="OWN_PHASED_DA_ALL_GAPS_CLASSIFIED_NOT_GOAL_SIGNOFF",tests=manifest["tests"],snapshot_files=len(source),own_hit=native["closure_line_hit"],original_denominator=native["closure_line_total"],
                own_top_hit=native["line_hit"],own_top_total=native["line_total"],remaining=sum(counts.values()),missing_by_source=dict(counts),comparison=comparison,native_classified=mapped,auditors=hashes,
                preserved_v1_rejection="v1 passed Wrapper top1505 to a LoadQueue-only mapper and rejected it. v2 separately classifies original child DA with each unchanged own denominator, then explicit top serial cases. No line/hit/source text excluded or rewritten.",
                whole_relationship_vs_missing_situation="Old joint source timing/revoke/CBO admission was a missing whole cross-block relationship, now the phased contract. Top1505/1507/1508 serial mode is a missing situation of existing bus ownership functionality, motivating fifteen actual full-effect supplements; other lines each retain original source/context/features and remain unproven if not hit.",
                limits="No old59595/leaf numerator merge, DA exclusions or unreachable claim. Required period1 SID failures remain; positive cadence/serial do not replace full8 mixed/error/alias/split, other exact128 recovery, local-only late responses or final complete request audit. No STRESS/goal acceptance.")
    out=run/"ldu-joint-coverage-audit-v2.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="native_classified"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
