#!/usr/bin/env python3
"""Local-reset own-DA gaps, exact source/line + compact shared rationales."""
import argparse
from collections import Counter
from copy import deepcopy
import csv
import json
from pathlib import Path

from audit_lsq_ldu_mixed_coverage_v2 import classify as child_classify
from audit_progress_run_v10 import coverage_signature
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name in("lsq-local-reset-retained-01","lsq-local-reset-retained-02")
    run=ROOT/"results"/name
    manifest,source,_=verify_common(run)
    native=json.loads((run/"line-audit.json").read_text())["native"][0]
    entries=[]
    for entry in(native,*native["dependencies"]):
        single=deepcopy(entry);single["dependencies"]=[]
        file=Path(entry["source"]).name
        if entry is not native and not file.startswith("DelayNWithValid"):
            single["closure_line_total"],single["closure_line_hit"]=entry["line_total"],entry["line_hit"]
            single,_=child_classify(single)
        entries.append(single)
    counts=Counter();reasons={};ids={};rows=[];sources=[]
    for entry in entries:
        file=Path(entry["source"]).name;path=ROOT/entry["source"];lines=path.read_text().splitlines()
        sources.append(dict(source=entry["source"],SHA256=sha(path),own_hit=entry["line_hit"],original_denominator=entry["line_total"]))
        for g in entry["uncovered"]:
            n=g["line"];assert lines[n-1].strip()==g["text"]
            features=g["features"];why=g["semantic_gap"]
            if entry is entries[0]:
                features=["LSQ-BUS.serial","LSQ-BUS.older_store","LSQ-RESET.pending_store"]
                why="本批NC outstanding不占共享串行owner；剩串行Load/Store请求仲裁/等待/归空情形，需原SID/方向的回包和Store实际副作用另测，不能从NC本地reset推断serial安全。"
            elif file.startswith("DelayNWithValid"):
                features=["LSQ-RAW.dual","LSQ-RAW.train"]
                why=("RAW的Store FTQ/isRVC/offset有效流水未激活，本批无STA；核LoadQueueRAW20873-20923实例接线，需真实老Store地址与原恢复/训练身份。"
                     if file in("DelayNWithValid.sv","DelayNWithValid_160.sv","DelayNWithValid_161.sv") else
                     "RAW CAM bank地址/数据有效流水未激活；核LqMaskModule997-1405/LqPAddrModule_1 999-1407接线，本批SQ空故RAW不分配，需真实未决Store/Load PA/mask和正负冲突读回。")
            elif file=="LoadQueueUncache.sv" or file.startswith("UncacheEntry"):
                features=list(features)+["LRESET-RETAIN","LRESET-RETAIN.full16"]
                why=("首12例只用两entry，遗漏全16在途SID保留时逐笔真实旧回包归还、同池新MID及每原LQ槽新UID完成的具体容量情况；先补16池三lane，不把返旧SID前提前复用或把外部job直接abort当通过。" if name.endswith("01") else
                     "已补全16旧/新NC原owner及SID保留/真实返回；剩为具体NC/MMIO/取消/错误/仲裁或guarded default情形，原行保留，不能因16池都完成就把这些分支排除。")+why
            elif file=="LoadQueueReplay.sv":
                why="本批仅真实NC原因及少数LQ/slot，原grant/反馈不替代120池全原因、依赖/标签/优先选择与special计时情况。"+why
            elif file=="VirtualLoadQueue.sv":
                why="本批局部reset/少数或16Load不覆盖全240编码/八lane/多flow/全部完成前缀宽度，须真实dispatch/完成与同槽新UID，不借precise03的分子。"+why
            features=sorted(set(features));assert features
            key=(tuple(features),why)
            if key not in ids:
                identity="R"+str(len(ids)+1);ids[key]=identity
                reasons[identity]=dict(features=features,reason=why,classification="missing_scenario_of_existing_feature",reachability="not_excluded")
            rows.append([file,str(n),ids[key],"|".join(features)]);counts[file]+=1
    assert len(rows)==native["closure_line_total"]-native["closure_line_hit"]
    path=run/"local-reset-uncovered-v1.csv"
    expected=[["source","original_line","rationale_ID","features"],*rows]
    if not path.exists():
        with path.open("x",newline="") as f:csv.writer(f).writerows(expected)
    with path.open() as f:assert list(csv.reader(f))==expected
    delta={}
    if name.endswith("02"):
        old=json.loads((ROOT/"results/lsq-local-reset-retained-01/line-audit.json").read_text())["native"][0]
        a,b=coverage_signature(old),coverage_signature(native);assert a.keys()==b.keys()
        for file,(h,lines) in b.items():
            before_h,before_lines=a[file];before=dict(before_lines)
            assert h==before_h and before.keys()==dict(lines).keys()
            delta[Path(file).name]=dict(added=sum(bool(hit) and not before[n] for n,hit in lines),lost=sum(before[n] and not hit for n,hit in lines))
    report=dict(status="EVERY_LOCAL_RESET_OWN_DA_GAP_CLASSIFIED_NO_EXCLUSIONS_NOT_WHOLE_GOAL_SIGNOFF",run=name,tests=manifest["tests"],snapshot_files=len(source),
                own_hit=native["closure_line_hit"],original_denominator=native["closure_line_total"],remaining=len(rows),missing_by_source=dict(counts),
                rationale_dictionary=reasons,gaps_csv=path.name,gaps_csv_SHA256=sha(path),source_denominators=sources,
                delta_from_initial=dict(added=sum(v["added"] for v in delta.values()),lost=sum(v["lost"] for v in delta.values()),by_source=delta) if delta else None,
                distinction="Retaining external ownership across local reset is an omitted whole cross-block relationship. Full16 and concrete entries/lane/flags/width branches are missing situations of existing LSQ functions, not new bit enumeration features.",
                limits="Every original line retained, no old/leaf/S4 numerator merge. Local-only external profile does not prove native SoC reset or late old ack. Existing ordinary FAILs and complete random/128/recovery/final request audit remain.",auditor_SHA256=sha(Path(__file__)))
    out=run/"local-reset-coverage-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in("rationale_dictionary","source_denominators")},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("name");audit(p.parse_args().name)
