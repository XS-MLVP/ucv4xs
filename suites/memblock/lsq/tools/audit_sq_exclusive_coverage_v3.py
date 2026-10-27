#!/usr/bin/env python3
"""All three real STA-RVC delay stages, preserving v1/v2 narrow-classifier failures."""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import shutil

import audit_sq_exclusive_coverage_v1 as core
from audit_lsq_ldu_mixed_coverage_v2 import classify as wrapper_cases
from audit_sq_initial import ROOT, sha


base_classify=core.classify


def classify(native):
    if native["dut"]!="lsq_wrapper":return base_classify(native)
    result=copy.deepcopy(native)
    counts=Counter()
    expected={71:"data <= io_in_bits;",73:"data_1 <= data;",75:"res_bits <= data_1;"}
    for index,entry in enumerate((result,*result["dependencies"])):
        file=Path(entry["source"]).name
        if index==0:
            for gap in entry["uncovered"]:
                assert gap["line"] in(1502,1504,1505,1507,1508)
                gap.update(features=["LSQ-BUS.serial","LSQ-BUS.resp_route"],classification="missing_scenario_of_existing_feature",
                           semantic_gap="本cached/RAW容量域无外部Uncache请求；需原UID串行选择/待返回/响应清忙及合法NC/MMIO/IO真实ack/resp/fire，不能排除或借旧接口分子")
        elif file=="DelayNWithValid.sv":
            for gap in entry["uncovered"]:
                assert expected[gap["line"]]==gap["text"]
                gap.update(features=["LSQ-RAW.conflict","LSQ-RAW.train"],classification="missing_scenario_of_existing_feature",
                           semantic_gap="RAW两STA的stIsRVC三拍选择元信息尚未随真实valid保存；原LoadQueueRAW20889/20917实例，补原STA与最老Load恢复/MDP逐字段。三行都保留且归既有流水情形，不称不可达")
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
    hashes={}
    for file in(Path(__file__),ROOT/"tools/audit_sq_exclusive_coverage_v2.py"):
        target=run/"evidence-auditors"/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    report=dict(status="PASS_ALL_DA_EXACT_SETS_AND_THREE_RAW_STA_RVC_PIPELINE_GAPS",run=name,auditors=hashes,
                preserved_failures=["v1 inherited classifier omitted DelayNWithValid71","v2 only enumerated first assignment71; actual old endpoint gaps also include next stages73/75. v3 explicitly retains all3 original line texts and RAW STA-RVC instance relation; no source, denominator or functional gate weakened."],
                full_classified_DA_and_deltas_SHA256=sha(run/"exclusive-coverage-audit-v1.json"))
    out=run/"exclusive-coverage-classifier-v3.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))
