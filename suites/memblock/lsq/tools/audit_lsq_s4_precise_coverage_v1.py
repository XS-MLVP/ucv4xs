#!/usr/bin/env python3
"""Compact exact per-line gap classification for the precise S4 native runs.

CSV retains each original source/line and functional mapping; shared rationale
dictionary avoids repeating large source contexts tens of thousands of times.
Original line-audit/RTL SHA and denominator remain unchanged, no exclusions.
"""
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
    assert name in("lsq-s4-precise-01","lsq-s4-precise-02","lsq-s4-precise-03")
    run=ROOT/"results"/name
    manifest,source,_=verify_common(run)
    native=json.loads((run/"line-audit.json").read_text())["native"][0]
    mapped=[]
    for child in native["dependencies"]:
        single=deepcopy(child);single["dependencies"]=[]
        single["closure_line_total"],single["closure_line_hit"]=child["line_total"],child["line_hit"]
        result,_=child_classify(single);mapped.append(result)
    top=deepcopy(native);top["dependencies"]=[]
    for gap in top["uncovered"]:
        assert gap["line"] in(1502,1504,1505,1507,1508)
        gap.update(features=["LSQ-BUS.serial","LSQ-BUS.ack_route","LSQ-BUS.resp_route"],classification="missing_scenario_of_existing_feature",
                   semantic_gap="本目录仅普通cached S4，不产生Uncache请求/总线响应；串行仲裁/归空是已有共享总线功能缺情况，不由本体其他行或其他目录分子代替")
    reasons={};rows=[];counts=Counter();file_specs=[]
    for entry in(top,*mapped):
        file=Path(entry["source"]).name
        path=ROOT/entry["source"];lines=path.read_text().splitlines()
        file_specs.append(dict(source=entry["source"],SHA256=sha(path),original_denominator=entry["line_total"],own_hit=entry["line_hit"]))
        for gap in entry["uncovered"]:
            assert gap["text"]==lines[gap["line"]-1].strip()
            features=list(gap["features"]);why=gap["semantic_gap"]
            if file in("VirtualLoadQueue.sv","VirtualStoreQueue.sv") or file.startswith("FreeList") or file.startswith("Lq"):
                features.append("S4P-EPOCH")
                why="已有分配/身份/恢复功能缺slot/lane/flag/原UID代际情形；小S4程序仅前三个LQ与一个Store，下一补连续真实完成/精确陷入/同槽重用并跨120/64物理、240/256编码及ROB640，不预置指针。原子语义仍需独立检查。"+why
            elif file=="LoadQueueReplay.sv":
                features.extend(("S4P-EPOCH","S4P-CACHE-JOBS"))
                why="原S4少数nack/miss owner不足覆盖120池各保存/选择入口；先补源正确双miss/各job真实refill与原grant/反馈，再补真实连续代际，其他strict/容量/TLB等仍保留整体要求。"+why
            elif file in("LoadQueueRAR.sv","LoadQueueRAW.sv"):
                features.extend(("S4P-EPOCH","S4E-REVOKE"))
                why="原双段query/revoke/ROB头恢复仍缺具体记录与代际/冲突情况；补真实较老Store、blocker/目标/年轻victim连续推进，公开signature不虚构RAW slot。"+why
            features=sorted(set(features));key=(tuple(features),why)
            identity=next((k for k,v in reasons.items() if v["features"]==features and v["reason"]==why),None)
            if identity is None:
                identity="R"+str(len(reasons)+1)
                reasons[identity]=dict(features=features,reason=why,kind="missing_scenario_of_existing_feature",reachability="not_excluded")
            rows.append((file,gap["line"],identity,"|".join(features)))
            counts[file]+=1
    assert len(rows)==native["closure_line_total"]-native["closure_line_hit"]==sum(counts.values())
    csv_path=run/"s4-precise-uncovered-v1.csv"
    if not csv_path.exists():
        with csv_path.open("x",newline="") as f:
            w=csv.writer(f);w.writerow(("source","original_line","rationale_ID","features"));w.writerows(rows)
    with csv_path.open() as f:assert len(list(csv.reader(f)))-1==len(rows)
    comparison={}
    if name!="lsq-s4-precise-01":
        previous=ROOT/"results"/("lsq-s4-precise-01" if name.endswith("02") else "lsq-s4-precise-02")
        old=json.loads((previous/"line-audit.json").read_text())["native"][0]
        a,b=coverage_signature(old),coverage_signature(native);assert a.keys()==b.keys()
        details={}
        for file,(h,lines) in b.items():
            assert a[file][0]==h and dict(a[file][1]).keys()==dict(lines).keys()
            before=dict(a[file][1]);details[Path(file).name]=dict(added=sum(hit and not before[n] for n,hit in lines),lost=sum(before[n] and not hit for n,hit in lines))
        comparison=dict(previous=previous.name,previous_hit=old["closure_line_hit"],added=sum(v["added"] for v in details.values()),lost=sum(v["lost"] for v in details.values()),by_source=details)
        assert comparison["added"]-comparison["lost"]==native["closure_line_hit"]-old["closure_line_hit"]
    result=dict(status="PRECISE_S4_OWN_NATIVE_DA_EVERY_GAP_CLASSIFIED_NOT_FINAL_SIGNOFF",run=name,tests=manifest["tests"],snapshot_files=len(source),
                own_hit=native["closure_line_hit"],original_denominator=native["closure_line_total"],remaining=len(rows),missing_by_source=dict(counts),
                gaps_csv=csv_path.name,gaps_csv_SHA256=sha(csv_path),rationale_dictionary=reasons,source_denominators=file_specs,comparison=comparison,
                distinction="Old early-trap and unreturned tail Cache job were omitted whole cross-block source relationships; concrete slots/entries/flags/lane/epoch saving gaps are missing situations of existing functions. Bus/NC/CBO etc are already defined whole-LSQ functions not exercised by this cached-only local batch.",
                limits="All actual native line sets retained. No old59595/53098 or leaf numerator merge, no exclusions or completion from body line hits. Source/UID semantic checks must pass independently; other random/128/local-only/full request audit remain.",auditor_SHA256=sha(Path(__file__)))
    output=run/"s4-precise-coverage-audit-v1.json"
    if output.exists():assert json.loads(output.read_text())==result
    else:output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in("rationale_dictionary","source_denominators")},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("name");audit(p.parse_args().name)
