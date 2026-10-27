#!/usr/bin/env python3
"""Compact exact-source missing-line inventory for full mixed attempts."""
import argparse
from collections import Counter
from copy import deepcopy
import csv
import json
from pathlib import Path
import shutil

from audit_lsq_ldu_mixed_coverage_v2 import classify
from audit_progress_run_v10 import coverage_signature
from audit_sq_initial import ROOT,sha,verify_common


def audit(name,prior=None):
    assert name.startswith("lsq-normal-mixed-source-")
    run=ROOT/"results"/name
    manifest,source,_=verify_common(run)
    semantic=json.loads((run/"normal-mixed-summary-audit-v1.json").read_text())
    assert semantic["tests"]==manifest["tests"] and len(semantic["cases"])==8
    native=json.loads((run/"line-audit.json").read_text())["native"][0]
    assert native["closure_line_total"]==59602
    entries=[]
    for entry in(native,*native["dependencies"]):
        single=deepcopy(entry);single["dependencies"]=[]
        single["closure_line_total"],single["closure_line_hit"]=single["line_total"],single["line_hit"]
        mapped,_=classify(single);entries.append(mapped)
    rationales={};ids={};rows=[];missing=Counter();denominators=[]
    for entry in entries:
        path=ROOT/entry["source"];file=path.name;lines=path.read_text().splitlines()
        denominators.append(dict(source=entry["source"],SHA256=sha(path),own_hit=entry["line_hit"],original_denominator=entry["line_total"]))
        for g in entry["uncovered"]:
            n=g["line"];assert lines[n-1].strip()==g["text"]
            features=g["features"];why=g["semantic_gap"]
            if entry is entries[0]:
                features=["LSQ-BUS.serial","LSQ-BUS.ack_route","LSQ-BUS.resp_route"]
                why="共享Uncache串行方向/完成归空分支缺实际情况；须原UID请求/确认/真实响应与ROB头顺序，不能以outstanding=1或本体其他行命中替代。"
            elif file=="LoadQueueReplay.sv":
                why="真实120池的具体slot/入口/原因、MSHR/TLB标签、strict依赖或计时分支缺情况。完整八类型仅运行到当前普通FAIL前缀；须原grant/反馈、外部job真实偿还和公平排空，不能将有界前缀或Cause7接口数据称为正常全域。"
            elif file=="VirtualLoadQueue.sv":
                why="具体LQ保存/八lane稀疏选择、多flow、3..8完成前缀或恢复相邻窗口缺情况；按真实完成/结构释放/ROB头trap分别记账，不能因访问物理槽便认为所有分支已查。"
            elif file=="VirtualStoreQueue.sv":
                why="具体虚拟槽ROB/flow/exclusive-end或walk分支缺情况；须合法128虚拟与当前64物理窗口、retired-old-Sbuffer和恢复同槽新UID，不增加read==head或先清空老Store的限制。"
            elif file=="PhysicalStoreQueue.sv":
                why="具体物理槽/STA入口的数据、属性、CBO或控制保存分支缺情况；须独立STA/S2/STD、最年轻PA字节、真实Cache/zero/WB/Sbuffer与连续释放，不以保存命中代替原UID终态。"
            elif file.startswith("FreeList"):
                why="本父级池的回收批次、通道、尾对齐、满池或真实重新分配分支缺情况；已访问slot不等于所有分配/回收组合，叶子全覆盖不并入此分子。"
            elif file.startswith("UncacheEntry") or file=="LoadQueueUncache.sv":
                why="具体entry/方向/错误/取消或三bypass元信息分支缺情况；必须真实响应后立即允许合法SID复用并核原UID数据/错误，已发取消请求仍回包。guarded defaults保持原分母、未在本批自动排除。"
            why="本目录自身原生DA；未覆盖不等于不可达。"+why
            key=(tuple(sorted(set(features))),why)
            if key not in ids:
                identity="R"+str(len(ids)+1);ids[key]=identity
                rationales[identity]=dict(features=list(key[0]),classification="missing_scenario_of_existing_feature",reason=why,reachability="not_excluded")
            rows.append([file,n,ids[key],"|".join(key[0])]);missing[file]+=1
    assert len(rows)==native["closure_line_total"]-native["closure_line_hit"]
    path=run/"normal-mixed-uncovered-v1.csv"
    expected=[["source","original_line","rationale_ID","features"],*[[str(v) for v in row] for row in rows]]
    if not path.exists():
        with path.open("x",newline="") as f:csv.writer(f).writerows(expected)
    with path.open() as f:assert list(csv.reader(f))==expected
    comparison=None
    if prior:
        old=json.loads((ROOT/"results"/prior/"line-audit.json").read_text())["native"][0]
        a,b=coverage_signature(old),coverage_signature(native);assert a.keys()==b.keys()
        deltas={}
        for file,(h,lines) in b.items():
            before_hash,before_lines=a[file];before=dict(before_lines)
            assert before_hash==h and before.keys()==dict(lines).keys()
            deltas[Path(file).name]=dict(added=sum(bool(hit) and not before[n] for n,hit in lines),lost=sum(before[n] and not hit for n,hit in lines))
        added=sum(x["added"] for x in deltas.values());lost=sum(x["lost"] for x in deltas.values())
        assert added-lost==native["closure_line_hit"]-old["closure_line_hit"]
        comparison=dict(prior_run=prior,prior_hit=old["closure_line_hit"],added=added,lost=lost,per_source=deltas,
                        relation="actual line-set differences, not merged old/leaf numerator or an automatic monotone-improvement claim")
    dest=run/"evidence-auditors";dest.mkdir(exist_ok=True);target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(status="EVERY_OWN_MIXED_DA_GAP_CLASSIFIED_NO_FUNCTIONAL_SIGNOFF",run=name,tests=manifest["tests"],source_files=len(source),
                own_hit=native["closure_line_hit"],original_denominator=native["closure_line_total"],raw_remaining=len(rows),missing_by_source=dict(missing),
                gaps_csv=path.name,gaps_csv_SHA256=sha(path),rationale_dictionary=rationales,original_sources=denominators,comparison=comparison,
                whole_relation_vs_situations="Normal hyper/PBMT producers, independent external Cache/TLB ownership even when replay priority hides a miss, and precise ROB-head faults are cross-block source relationships. Slot/lane/cause/release/width branches in this CSV are missing situations of existing semantic functions, none excluded. A failing prefix does not close those relationships or the full eight-seed domain.",
                limits="Original53-source native DA and unchanged59602 denominator only. No retroactive normal admission, historical FAIL removal, stress checked or goal completion. Initial vector QB route, other128/old generations, local serial reset/late ack and final full-request audit remain.",auditor_SHA256=sha(Path(__file__)))
    output=run/"normal-mixed-coverage-audit-v1.json"
    if output.exists():assert json.loads(output.read_text())==report
    else:output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in("rationale_dictionary","original_sources")},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("name");p.add_argument("--prior");a=p.parse_args();audit(a.name,a.prior)
