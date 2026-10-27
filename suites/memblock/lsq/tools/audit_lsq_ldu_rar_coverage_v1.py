#!/usr/bin/env python3
"""Exact own native DA sets, per-line semantic gaps and two real iterations.

The full96 programs fill identity paths, not the entire Wrapper. No earlier
interface/leaf numerator, source exclusion or successful subcase hides a FAIL.
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
    store={"VirtualStoreQueue.sv","DeqModule.sv","EnterSbufferQueue.sv","ForwardModule.sv","UnalignQueue.sv"}
    for entry in(result,*result["dependencies"]):
        name=Path(entry["source"]).name
        lines=(ROOT/entry["source"]).read_text().splitlines()
        for gap in entry["uncovered"]:
            number,text=gap["line"],gap["text"]
            assert text==lines[number-1].strip()
            context="\n".join(lines[max(0,number-4):number+3])
            if name=="LsqWrapperDut.v":
                assert number in(1502,1504,1505,1507,1508)
                features=["LSQ-BUS.serial","LSQ-BUS.nc_outstanding","LSQ-BUS.ack_route","LSQ-BUS.resp_route"]
                why="本正常cached子集无外部bus请求；本行是共享串行状态保存/响应清理，仍须NC/MMIO/Store真实请求、方向ack/resp及SID身份完成，不能从RAR定向排除该功能"
            elif name=="LoadQueueRAR.sv":
                assert re.search(r"uop_\d+_",context), (number,text)
                features=["LDU-RAR.full_pool","LSQ-RAR.head_reclaim","LSQ-RAR.revoke"]
                why="真实RAR记录从另一个Load入口保存原ROB/LQ身份的情形；首轮只访问少数记录，第二轮每记录仅一种入口。补正常完整97-Load程序的三种入口轮换，原96个年轻UID保留到老Load完成后真实dequeue；不能只写入即宣称身份正确"
            elif name=="LqPAddrModule.sv":
                features=["LDU-RAR.full_pool","LSQ-RAR.current_release","LSQ-RAR.head_reclaim"]
                why="真实RAR地址CAM未访问的记录/入口写入；用96个唯一PA的真实年轻Load、固定S2/S3时序、正常老Load与真实head回收补全写入。全槽地址nuke负对照仍需独立功能证据，不能把写行提升为全部RAR语义"
            elif name=="PhysicalStoreQueue.sv":
                if "cboType" in context or "cboSetVec" in context:
                    features=["LSQ-RETIRE.cbo","LSQ-RETIRE.zero_ownership","LSQ-EXCEPTION.cache_wb"]
                    why="真实PSQ的CBO opcode/属性记录未被本cached子集访问；须保持正常包与NoSpec/BlockBack，以原cache/zero16/WB/SQ释放核对，已有串行CBO普通FAIL不被本批抵消"
                elif 12108<=number<=12116:
                    features=["LSQ-RECOVER.partial","LSQ-RECOVER.reuse"]
                    why="真实Store分支恢复身份保存未被只有Load受害者的本例激活；补未退休Store取消、幸存已退休字节及同SQ槽新UID真实消费"
                else:
                    features=["LSQ-ALLOC.sq_capacity","LSQ-ALLOC.sq_wrap","LSQ-FORWARD.youngest","LSQ-RETIRE.ordinary"]
                    why="本cached/STA-nuke子集只执行普通Store槽0，未访问本行的PSQ数据/控制或完整虚拟年龄保存。须真实64物理/128虚拟窗口、STA/S2/STD次序、Forward原PA字节及Sbuffer/SQ原UID完成"
            elif name=="VirtualStoreQueue.sv" and 5900<=number<=14274:
                features=["LSQ-ALLOC.all_lanes","LSQ-ALLOC.multi_flow","LSQ-ALLOC.sq_wrap","LSQ-RETIRE.finish_prefix"]
                why="本子集只分配一个普通Store，未访问各虚拟槽的ROB/flow/exclusive-end保存分支；补完整混合dispatch/多flow与128虚拟占用，经实际执行、ROB退休和连续SQ原UID释放核对，不能将未写槽误分为恢复不可达"
            elif name=="ForwardModule.sv":
                features=["LSQ-FORWARD.youngest","LSQ-FORWARD.wrap","LSQ-FORWARD.sqid"]
                why="虽有真实S0/S1查询，本行的非零dequeue低年龄高槽优先选择未激活；须真实Store多圈写出形成对应窗口，再由Load取当前最年轻PA字节及完整SQ代并实际完成，不是整个Forward功能遗漏"
            elif name=="DeqModule.sv" and "cbo" in context.lower():
                features=["LSQ-RETIRE.cbo","LSQ-RETIRE.zero_ownership","LSQ-EXCEPTION.cache_wb"]
                why="本普通cached/STA子集不分配CBO；真实CBO状态与flush/WB/zero归属缺少本子集刺激，仍须正常NoSpec/BlockBack和原副作用检查，不把既有真实串行FAIL抹掉"
            elif name in store:
                features,why=locate_store(name,gap)
                why="本次正常LDU子集的剩余情形，不是整体不可达："+why
            else:
                original,why=load_locate(name,gap)
                features=[mapped for f in original for mapped in load_features(f)]
                if name=="FreeList.sv":
                    features=["LDU-RAR.full_pool","LSQ-RAR.head_reclaim","LSQ-RECOVER.reuse"]
                why="本次正常LDU子集的剩余情形，不借叶子/旧接口流覆盖："+why
            assert features
            gap.update(features=sorted(set(features)),classification="missing_scenario_of_existing_feature",semantic_gap=why,
                       reachability="not_excluded",original_context=[dict(line=n,text=lines[n-1]) for n in range(max(1,number-2),min(len(lines),number+2)+1)])
            counts[name]+=1
    assert sum(counts.values())==native["closure_line_total"]-native["closure_line_hit"]
    return result,counts


def audit(name):
    assert name=="lsq-ldu-rar-routing-03"
    runs=[ROOT/"results"/f"lsq-ldu-rar-routing-{n:02}" for n in range(1,4)]
    inventories=[]
    for run in runs:
        manifest,source,nodes=verify_common(run)
        native,tables=sources(run)
        classified,counts=classify(native)
        assert native["closure_line_total"]==59602
        inventories.append(dict(run=run.name,tests=manifest["tests"],source_files=len(source),native=native,tables=tables,
                                classified=classified,counts=counts))
    deltas=[]
    for old,new in zip(inventories,inventories[1:]):
        assert old["tables"].keys()==new["tables"].keys()
        missing={e["source"]:{g["line"]:g for g in e["uncovered"]} for e in(old["classified"],*old["classified"]["dependencies"])}
        newly,per_source=[],Counter()
        for file in old["tables"]:
            a,b=old["tables"][file],new["tables"][file]
            assert a.keys()==b.keys()
            hits_a={n for n,h in a.items() if h}
            hits_b={n for n,h in b.items() if h}
            assert not hits_a-hits_b, (file,"previous DA hit lost")
            for n in sorted(hits_b-hits_a):
                gap=missing[file][n]
                newly.append(dict(source=file,line=n,text=gap["text"],features=gap["features"],classification=gap["classification"],
                                   before_hits=0,actual_after_hits=b[n],original_context=gap["original_context"]))
                per_source[Path(file).name]+=1
        assert len(newly)==new["native"]["closure_line_hit"]-old["native"]["closure_line_hit"]
        deltas.append(dict(prior=old["run"],current=new["run"],newly_hit=len(newly),lost=0,new_hit_by_source=dict(per_source),new_dynamic_lines=newly))
    run=runs[-1]
    semantic=json.loads((run/"ldu-rar-routing-audit-v2.json").read_text())
    assert semantic["full_pool_original_UIDs_completed"]==291 and semantic["counts"]["same_physical_slot_new_UID_completion"]==3
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    auditor_hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_lq_gaps.py",ROOT/"tools/audit_lsq_gaps.py",ROOT/"tools/audit_lsq_normal_coverage_v1.py"):
        copy=dest/file.name
        if copy.exists():assert sha(copy)==sha(file)
        else:shutil.copy2(file,copy)
        auditor_hashes[file.name]=sha(file)
    summaries=[dict(run=x["run"],tests=x["tests"],snapshot_files=x["source_files"],closure_hit=x["native"]["closure_line_hit"],closure_total=59602,
                    RAR_hit=next(d["line_hit"] for d in x["native"]["dependencies"] if d["source"].endswith("LoadQueueRAR.sv")),RAR_total=3898,
                    raw_remaining=sum(x["counts"].values()),missing_by_source=dict(x["counts"])) for x in inventories]
    report=dict(run=name,status="NORMAL_CACHED_LDU_GAP_CLASSIFICATION_AND_TWO_NATIVE_COVERAGE_ITERATIONS_NOT_WHOLE_LSQ_SIGNOFF",
                iterations=summaries,deltas=deltas,per_iteration_full_classified_inventories=[dict(run=x["run"],native=x["classified"]) for x in inventories],
                corrected_producer_feature_omissions=["Old Wrapper RAR positive-conflict contract incorrectly prescribed LRQ replay; source-normal original ROB flushAfter, exact S2/S3 revoke and same-slot recovery required a distinct LDU producer feature and tests, even where old RTL DA was already hit."],
                classification="All remaining raw DA gaps map to existing full-Wrapper features or the new pre-test LDU full_pool feature; no gap excluded and no whole behavior removed.",
                auditors=auditor_hashes,limits="Only this normal cached subset's own full53-source native DA. Old317 cases/independent leaf totals are not borrowed. 3 strict previous-release failures and reached-only bin remain. Full body lines, even if hit, do not prove RAR timing or whole normal random. Complete mixed producer, normal joint capacity/CBO staging, remaining exact128 domains and final request/evidence audit still required.")
    out=run/"ldu-rar-coverage-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in("deltas","per_iteration_full_classified_inventories")},indent=2,ensure_ascii=False))
    print(json.dumps([{k:v for k,v in d.items() if k!="new_dynamic_lines"} for d in deltas],indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
