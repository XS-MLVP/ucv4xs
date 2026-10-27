#!/usr/bin/env python3
"""Post-epoch per-line gaps: do not call exercised slots still unvisited.

Compact CSV + original RTL hashes gives every missing source/line its current
functional rationale without duplicating thousands of source context blocks.
"""
import argparse
from collections import Counter
from copy import deepcopy
import csv
import json
from pathlib import Path
import shutil

from audit_lsq_ldu_mixed_coverage_v2 import classify as child_classify
from audit_progress_run_v10 import coverage_signature
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name=="lsq-s4-precise-03"
    run=ROOT/"results"/name
    manifest,source,_=verify_common(run)
    semantic=json.loads((run/"s4-precise-summary-audit-v3.json").read_text())
    assert semantic["tests"]==manifest["tests"]=={"PASS":84} and semantic["validated_completed_programs"]==1161
    native=json.loads((run/"line-audit.json").read_text())["native"][0]
    entries=[deepcopy(native)];entries[0]["dependencies"]=[]
    for child in native["dependencies"]:
        single=deepcopy(child);single["dependencies"]=[]
        single["closure_line_total"],single["closure_line_hit"]=child["line_total"],child["line_hit"]
        mapped,_=child_classify(single);entries.append(mapped)
    reasons={};reason_ids={};rows=[];counts=Counter();denominators=[]
    for entry in entries:
        file=Path(entry["source"]).name;path=ROOT/entry["source"];lines=path.read_text().splitlines()
        denominators.append(dict(source=entry["source"],SHA256=sha(path),original_denominator=entry["line_total"],own_hit=entry["line_hit"]))
        for g in entry["uncovered"]:
            n=g["line"];assert g["text"]==lines[n-1].strip()
            context="\n".join(lines[max(0,n-10):n+10])
            features=g["features"];why=g["semantic_gap"]
            if entry is entries[0]:
                assert n in(1502,1504,1505,1507,1508)
                features=["LSQ-BUS.serial","LSQ-BUS.ack_route","LSQ-BUS.resp_route"]
                why="本批cached S4不发Uncache请求；共享串行仲裁、响应归空缺实际总线情况。local-only reset的新NC程序需真实req/ack/旧响应归原UID另行补查，不把旧总线分子并入本目录。"
            elif file=="LoadQueueRAR.sv":
                assert "matchMask" in context or "release2Cycle" in context
                features=["LSQ-RAR.current_release","LSQ-RAR.previous_release","LSQ-RAR.revoke"]
                why="真实代际已覆盖RAR记录保存；剩行为coherence release的匹配向量捕获/保持与两拍release PA。本批无release输入，仍须同/异line连续release、原读者重查/nuke与revoke原UID负对照，不误标为没访问过RAR物理槽。"
            elif file=="LoadQueueRAW.sv":
                features=["LSQ-RAW.conflict","LSQ-RAW.dual","LSQ-RAW.train"]
                why="RAW记录及入口保存已真实跨代，剩为最老违例rollback选择和元信息寄存。本批老Store与Load PA非冲突，缺真实较老STA同字节正违例、双Store最老选择/训练，不能把负查询或flags遍历当正恢复检查。"
            elif file=="PhysicalStoreQueue.sv":
                assert "cbo" in context or "Cbo" in context
                features=["LSQ-RETIRE.cbo","LSQ-RETIRE.zero_ownership","LSQ-EXCEPTION.cache_wb"]
                why="全部64物理Store槽和256编码普通数据已实际消费；剩320行是CBO类型保存/选择。补QB包、NoSpec独占和BlockBack直到退休/取消、真实Cache/zero/WB及SQ释放；普通Store不能替代或抵消原CBO FAIL。"
            elif file=="VirtualLoadQueue.sv":
                if n<13000:
                    features=["LSQ-RETIRE.finish_prefix","LSQ-RETIRE.multi_flow"]
                    why="原已完成前缀批释放只出现1/2；剩decode对应3..8笔完成前缀。补真实多Load完成后解除原blocker，使VLQ自然一次释放3..8，不用外部改head。"
                elif "lastEnqCancel" in context:
                    features=["LSQ-RECOVER.concurrent","LSQ-ALLOC.filters"]
                    why="缺redirect前拍分配/取消计数的真实相邻时序；本流先派发后执行再精确trap，未给所有合法dispatch与redirect相邻窗口。仍遵守真实producer同拍互斥，不为DA伪造非法同拍dispatch/redirect。"
                else:
                    features=["LSQ-ALLOC.all_lanes","LSQ-ALLOC.sparse","LSQ-ALLOC.multi_flow"]
                    why="所有240编码已访问，但每程序仅3Load/最多4lane，剩为具体槽的八dispatch入口/多flow和稀疏选择，不是未访问物理槽。补源正确八lane/多flow后的原UID完成/取消同槽新UID关系。"
            elif file=="VirtualStoreQueue.sv":
                if 15848<=n<=15857 or n==14330:
                    features=["LSQ-RECOVER.partial","LSQ-RECOVER.retired_store"]
                    why="每代老Store均幸存且先完成再进入下一代；缺实际取消Store后缀时VSQ退休前缀walk与last-valid end选择。保留已退休但Sbuffer未消费原字节，再真实恢复/同SQ槽新UID消费。"
                else:
                    features=["LSQ-ALLOC.all_lanes","LSQ-ALLOC.sparse","LSQ-ALLOC.multi_flow"]
                    why="360个真实Store只用dispatch lane0；剩31行的一部分是其他稀疏入口的exclusive-end选择，补八lane/多flow，不能用256编码已遍历替代入口选择。"
            elif file=="LoadQueueReplay.sv":
                features=list(features)+["S4P-CACHE-JOBS","S4P-EPOCH"]
                why="516次真实原slot grant/反馈与474原Cache job/refill已完成；剩具体入口/slot的MSHR、TLB tag、strict依赖、blockSq、wake/hint和special计时等缺情形。须实际SQ/TLB/NC/容量生产者关系，不把S4的nack/miss遍历冒称全原因或全入口覆盖。"+why
            elif file.startswith("FreeList"):
                why="原父池持续代际完成/恢复已执行，仍缺实际回收批次宽度、通道、尾对齐或满池的组合情况；不能再称所有物理槽未访问，也不把独立叶子全覆盖并入本目录。"+why
            features=sorted(set(features));assert features
            key=(tuple(features),why)
            if key not in reason_ids:
                identity="R"+str(len(reason_ids)+1);reason_ids[key]=identity
                reasons[identity]=dict(features=features,reason=why,classification="missing_scenario_of_existing_feature",reachability="not_excluded")
            rows.append((file,n,reason_ids[key],"|".join(features)));counts[file]+=1
    assert len(rows)==native["closure_line_total"]-native["closure_line_hit"]==9720
    csv_path=run/"s4-precise-uncovered-v2.csv"
    expected_rows=[["source","original_line","rationale_ID","features"],*[[str(v) for v in row] for row in rows]]
    if not csv_path.exists():
        with csv_path.open("x",newline="") as f:csv.writer(f).writerows(expected_rows)
    with csv_path.open() as f:assert list(csv.reader(f))==expected_rows
    old=json.loads((ROOT/"results/lsq-s4-precise-02/line-audit.json").read_text())["native"][0]
    a,b=coverage_signature(old),coverage_signature(native);assert a.keys()==b.keys()
    delta={}
    for file,(h,lines) in b.items():
        before_h,before_lines=a[file];before=dict(before_lines)
        assert before_h==h and before.keys()==dict(lines).keys()
        delta[Path(file).name]=dict(added=sum(bool(hit) and not before[n] for n,hit in lines),lost=sum(before[n] and not hit for n,hit in lines))
    assert sum(d["added"] for d in delta.values())==22888 and sum(d["lost"] for d in delta.values())==0
    dest=run/"evidence-auditors";dest.mkdir(exist_ok=True);target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(status="EVERY_POST_EPOCH_GAP_CLASSIFIED_NOT_WHOLE_SCOPE_SIGNOFF",run=name,tests=manifest["tests"],snapshot_files=len(source),
                own_hit=native["closure_line_hit"],original_denominator=native["closure_line_total"],remaining=len(rows),missing_by_source=dict(counts),
                previous_run="lsq-s4-precise-02",previous_hit=old["closure_line_hit"],added=22888,lost=0,exact_line_set_delta_by_source=delta,
                gaps_csv=csv_path.name,gaps_csv_SHA256=sha(csv_path),rationale_dictionary=reasons,original_source_denominators=denominators,
                whole_relation_vs_situations="Precise ROB-head trap and retained external Cache jobs were missing whole cross-block source relations, now tested for the stated S4 profile. Remaining per-line slot/input/width/wake/feature branches are missing situations of existing LSQ functions, none excluded.",
                limits="Real53 source universe and own native DA only. No old/leaf numerator union; original denominator retained. 84PASS is not eight-type random signoff; original failures, other128/old-generation, local-only response and final full request audit remain.",auditor_SHA256=sha(Path(__file__)))
    out=run/"s4-precise-coverage-audit-v2.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in("rationale_dictionary","original_source_denominators")},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("name");audit(p.parse_args().name)
