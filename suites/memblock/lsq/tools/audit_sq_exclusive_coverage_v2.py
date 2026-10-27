#!/usr/bin/env python3
"""Keep v1's DelayNWithValid gap rejection; classify that real RAW STA metadata.

Unchanged native LCOV/set-delta gates from v1. No DA is hidden or excluded.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil

import audit_sq_exclusive_coverage_v1 as core
from audit_lsq_ldu_mixed_coverage_v2 import classify as wrapper_cases
from audit_sq_initial import ROOT, sha


original_classify=core.classify


def classify(native):
    if native["dut"]!="lsq_wrapper":return original_classify(native)
    result=copy.deepcopy(native)
    counts=Counter()
    for index,entry in enumerate((result,*result["dependencies"])):
        file=Path(entry["source"]).name
        if index==0:
            for gap in entry["uncovered"]:
                assert gap["line"] in(1502,1504,1505,1507,1508)
                gap.update(features=["LSQ-BUS.serial","LSQ-BUS.resp_route"],classification="missing_scenario_of_existing_feature",
                           semantic_gap="cached/RAW容量域没有外部Uncache请求；尚缺原UID的串行选择、待返回与响应清忙，须合法NC/MMIO/IO实际ack/resp/fire，不能排除或借旧接口覆盖")
        elif file=="DelayNWithValid.sv":
            for gap in entry["uncovered"]:
                assert gap["line"]==71 and gap["text"]=="data <= io_in_bits;"
                gap.update(features=["LSQ-RAW.conflict","LSQ-RAW.train"],classification="missing_scenario_of_existing_feature",
                           semantic_gap="真实RAW两条STA的stIsRVC选择流水尚未写入元信息；LoadQueueRAW20889/20917实例。补原STA并发、原Load最老恢复与MDP逐字段，不能把valid延时寄存当未定义或不可达")
        else:
            piece=copy.deepcopy(entry)
            piece.update(dependencies=[],closure_line_hit=piece["line_hit"],closure_line_total=piece["line_total"])
            mapped,_=wrapper_cases(piece)
            entry["uncovered"]=mapped["uncovered"]
        lines=(ROOT/entry["source"]).read_text().splitlines()
        for gap in entry["uncovered"]:
            n=gap["line"]
            assert gap["text"]==lines[n-1].strip() and gap["features"] and gap["classification"]=="missing_scenario_of_existing_feature"
            gap.update(original_context=[dict(line=k,text=lines[k-1]) for k in range(max(1,n-2),min(len(lines),n+2)+1)],
                       reachability="not_excluded",scope="THIS_DUT_RUN_OWN_DA_NO_PRIOR_OR_LEAF_NUMERATOR")
            counts[file]+=1
    assert sum(counts.values())==native["closure_line_total"]-native["closure_line_hit"]
    return result,counts


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    name=p.parse_args().name
    core.classify=classify
    core.audit(name)
    run=ROOT/"results"/name
    source=Path(__file__)
    target=run/"evidence-auditors"/source.name
    if target.exists():assert sha(target)==sha(source)
    else:shutil.copy2(source,target)
    report=dict(status="PASS_ALL_RAW_DA_RETAINED_EXPLICIT_RAW_STA_RVC_PIPELINE_CLASSIFIER",run=name,
                preserved_v1_rejection="v1 inherited a subset classifier missing DelayNWithValid.sv:71 data<=io_in_bits; actual instance is RAW stIsRVC STA selection metadata. v2 classifies the existing conflict/train scenario explicitly; original DA counts/context and v1 exact-set gates unchanged.",
                classifier_SHA256=sha(source),core_SHA256=sha(ROOT/"tools/audit_sq_exclusive_coverage_v1.py"),full_classified_DA_and_deltas_SHA256=sha(run/"exclusive-coverage-audit-v1.json"))
    out=run/"exclusive-coverage-classifier-v2.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))
