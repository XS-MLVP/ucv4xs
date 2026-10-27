#!/usr/bin/env python3
"""Normal subset's OWN full Wrapper DA inventory and real gap-driven delta."""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil

from audit_lq_gaps import locate as load_locate
from audit_lsq_gaps import load_features, locate_store
from audit_sq_initial import ROOT, sha, verify_common
from coverage_audit import lcov


def classify(native):
    result=copy.deepcopy(native)
    counts=Counter()
    store_sources={"VirtualStoreQueue.sv","PhysicalStoreQueue.sv","DeqModule.sv","EnterSbufferQueue.sv","ForwardModule.sv","UnalignQueue.sv"}
    for item in (result,*result.get("dependencies",[])):
        source=Path(item["source"]).name
        lines=(ROOT/item["source"]).read_text().splitlines()
        for gap in item["uncovered"]:
            if source in store_sources:
                features,_=locate_store(source,gap)
            else:
                original,_=load_locate(source,gap)
                features=[mapped for feature in original for mapped in load_features(feature)]
            if source=="PhysicalStoreQueue.sv":
                behavior="正常CBO在各真实物理槽/STA入口保存其opcode与原UID；14例只访问少数CBO槽，须新512槽×CBO×STA经实际cache/zero16/WB/释放完成，不以旧size3接口保存算正常命中"
            elif source=="ForwardModule.sv":
                behavior="非零head回绕的低年龄高槽优先选择还未命中本行；需真实Load从三个入口读取当前年轻Store的PA字节及完整依赖代，不能合入独立Forward叶子行"
            elif source=="VirtualLoadQueue.sv":
                behavior="新正常域本轮尚未访问该行对应的稀疏高dispatch入口/多flow/跨120保存或变长取消；须真实原Load完成/恢复到同槽新UID完成，不以单flow联合峰值替代该枚举"
            elif source=="LoadQueueReplay.sv":
                behavior="新正常域未激活该行的候选优先/原因/依赖/标签或slot元信息保存情形；已有语义映射如下，须原slot实际grant/反馈，不能把正常CBO修正或半环端点审计当全Replay遍历"
            elif source.startswith("FreeList"):
                behavior="真实父池变长回收批次与返回尾对齐未访问本行；需本层原UID真实完成/取消、重新分配并完成，不借对应独立FreeList DA"
            elif source=="LoadQueueRAR.sv":
                behavior="本轮少量RAR回收后重新分配的具体入口×slot身份保存尚缺；实际nuke/释放正反和原Load完成检查仍必需，release已知FAIL不抵消"
            elif source=="LoadQueueRAW.sv":
                behavior="本轮RAW部分槽的入口/metadata更新或高选择组未命中；需真实STA的byte/wline冲突、原rollback/MDP字段和shared恢复，不以零冲突联合正条件代替"
            elif source=="LoadQueueUncache.sv":
                behavior="本轮未遍历16个entry到三bypass/异常汇聚的全部地址/数据/错误选择；补原响应/SID及时复用、各消费入口与错误。guarded defaults仍留原分母，未在此小范围冒称全部可达或窄证明完成"
            elif source.startswith("UncacheEntry"):
                behavior="取消时该真实ID entry的请求/返回状态迁移未访问本行；需原外部job真正偿还、同mid/物理槽新UID完成，不以共同reset中止当原响应"
            elif source=="UnalignQueue.sv":
                behavior="两项真实第二物理页与完整SQ身份的分配/消费/取消尚未覆盖本行；需实际跨页split首尾、共享恢复及第二页字节，正常对齐CBO不覆盖该情形"
            else:
                raise AssertionError((source,gap))
            gap.update(features=sorted(set(features)),classification="missing_scenario_of_existing_feature",semantic_gap=behavior,
                       reachability="not_excluded",scope="THIS_NORMAL_SUBSET_own_real53_file_Wrapper_DA_not_old_interface_or_leaf_union",
                       original_context=[dict(line=n,text=lines[n-1]) for n in range(max(1,gap["line"]-2),min(len(lines),gap["line"]+2)+1)])
            assert features
            counts[source]+=1
    assert sum(counts.values())==native["closure_line_total"]-native["closure_line_hit"]
    return result,counts


def sources(run):
    native=json.loads((run/"line-audit.json").read_text())["native"]
    assert len(native)==1 and native[0]["dut"]=="lsq_wrapper"
    n=native[0]
    tables=lcov(ROOT/n["lcov"])
    result={}
    for entry in(n,*n["dependencies"]):
        assert sha(ROOT/entry["source"])==entry.get("sha256",entry.get("source_sha256"))
        counts=tables.get(str(ROOT/entry["source"]),{})
        assert len(counts)==entry["line_total"] and sum(bool(v) for v in counts.values())==entry["line_hit"]
        result[entry["source"]]=counts
    assert len(result)==53 and sum(map(len,result.values()))==59602
    return n,result


def audit(name):
    assert name=="lsq-normal-cbo-03"
    run,prior=ROOT/"results"/name,ROOT/"results/lsq-normal-cbo-01"
    manifest,source,nodes=verify_common(run)
    before,a=sources(prior)
    after,b=sources(run)
    assert set(a)==set(b) and before["closure_line_hit"]==56989
    classified,missing=classify(before)
    remaining,current_missing=classify(after)
    gaps={e["source"]:{g["line"]:g for g in e["uncovered"]} for e in(classified,*classified["dependencies"])}
    additions,by_file=[],Counter()
    for file in sorted(a):
        assert a[file].keys()==b[file].keys()
        old_hits={line for line,hits in a[file].items() if hits}
        new_hits={line for line,hits in b[file].items() if hits}
        assert not old_hits-new_hits, "no previous native DA hit may be lost"
        for line in sorted(new_hits-old_hits):
            g=gaps[file][line]
            additions.append(dict(source=file,line=line,text=g["text"],features=g["features"],semantic_gap=g["semantic_gap"],
                                  classification=g["classification"],before_hits=0,actual_after_hits=b[file][line]))
            by_file[Path(file).name]+=1
    assert len(additions)==after["closure_line_hit"]-56989 and sum(missing.values())==2613
    endpoint=json.loads((run/"sq-endpoint-audit-v2.json").read_text())
    normal=json.loads((run/"normal-cbo-audit-v5.json").read_text())
    assert endpoint["allocated_and_completed_original_UIDs"]==2313 and normal["completed_normal_CBO_slot_opcode_STA_combinations"]==512
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    for file in(Path(__file__),ROOT/"tools/audit_lsq_gaps.py",ROOT/"tools/audit_lq_gaps.py"):
        target=dest/file.name
        if target.exists():assert sha(file)==sha(target)
        else:shutil.copy2(file,target)
    report=dict(run=name,status="normal_subset_2613_gaps_individually_mapped_and_actual_native_delta_not_full_coverage_acceptance",
                tests=manifest["tests"],snapshot_files=len(source),prior=prior.name,prior_hit=56989,current_hit=after["closure_line_hit"],original_denominator=59602,
                newly_hit=len(additions),lost_hits=0,raw_remaining=59602-after["closure_line_hit"],prior_missing_by_source=dict(missing),new_hit_by_source=dict(by_file),
                current_missing_by_source=dict(current_missing),prior_native_classified=classified,current_native_classified=remaining,new_dynamic_lines=additions,
                classification="all_gaps_are_missing_cases_of_existing_features_no_whole_feature_removed_or_silently_invented",
                auditor_sha256=sha(dest/Path(__file__).name),
                limits="Actual native53-source DA universe unchanged. This package-correct subset owns its raw numerator; NOT59595 by borrowing old317 cases/independent leaves. Baseline2613 gaps retain source/text/context/features, mapping missing cases not unreachability. CBO serialization-v2 separately REJECTS full normal PROGRAM admission despite correct package fields; these CBO hits are interface coverage until serialized producer reruns. The18 correctly retired CBO-free endpoint cases have separate2313UID proof, and12 old normal02 premature-ROB green histories remain refused. Remaining gaps/failed semantics still require complete scope; no STRESS checked/full random/goal completion claim.")
    out=run/"normal-coverage-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in("prior_native_classified","current_native_classified","new_dynamic_lines")},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
