#!/usr/bin/env python3
"""Complete RAW STA delay variants: RVC, FTQ index and offset; all raw DA kept."""
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
STA_DELAYS={
    "DelayNWithValid.sv":({71:"data <= io_in_bits;",73:"data_1 <= data;",75:"res_bits <= data_1;"},"stIsRVC",(20889,20917)),
    "DelayNWithValid_160.sv":({76:"data_flag <= io_in_bits_flag;",77:"data_value <= io_in_bits_value;",80:"data_1_flag <= data_flag;",81:"data_1_value <= data_value;",84:"res_bits_flag <= data_1_flag;",85:"res_bits_value <= data_1_value;"},"stFtqIdx",(20873,20901)),
    "DelayNWithValid_161.sv":({71:"data <= io_in_bits;",73:"data_1 <= data;",75:"res_bits <= data_1;"},"stFtqOffset",(20882,20910)),
}


def classify(native):
    if native["dut"]!="lsq_wrapper":return base_classify(native)
    result=copy.deepcopy(native)
    counts=Counter()
    raw=(ROOT/"rtl/lsq_wrapper/LoadQueueRAW.sv").read_text().splitlines()
    for index,entry in enumerate((result,*result["dependencies"])):
        file=Path(entry["source"]).name
        if index==0:
            for gap in entry["uncovered"]:
                assert gap["line"] in(1502,1504,1505,1507,1508)
                gap.update(features=["LSQ-BUS.serial","LSQ-BUS.resp_route"],classification="missing_scenario_of_existing_feature",
                           semantic_gap="本cached/RAW容量域没有Uncache请求；原UID串行选择、等待返回及响应清忙缺情形，需合法NC/MMIO/IO的真实ack/resp/fire；不能排除或借旧接口覆盖")
        elif file in STA_DELAYS:
            expected,field,instances=STA_DELAYS[file]
            assert all(file.removesuffix(".sv") in raw[n-1] and field in raw[n-1] for n in instances)
            for gap in entry["uncovered"]:
                assert expected[gap["line"]]==gap["text"]
                gap.update(features=["LSQ-RAW.conflict","LSQ-RAW.train"],classification="missing_scenario_of_existing_feature",
                           semantic_gap=f"RAW两条原STA的{field}三拍恢复/训练元信息保存缺情形；LoadQueueRAW{instances}实际实例。需最老原Load rollback与MDP逐字段，不将延时寄存视为不可达或删分母")
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
    for file in(Path(__file__),*(ROOT/"tools"/f"audit_sq_exclusive_coverage_v{i}.py" for i in(2,3))):
        target=run/"evidence-auditors"/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
        hashes[file.name]=sha(file)
    report=dict(status="PASS_ALL_RAW_DA_AND_STA_RVC_FTQ_INDEX_OFFSET_DELAY_VARIANTS",run=name,auditors=hashes,
                preserved_failures=["v1 subset classifier omitted RAW DelayNWithValid","v2 enumerated only first delay assignment71, but real next stages73/75 also missing","v3 covered RVC three stages but omitted FTQ index _160 and offset _161 variants; v4 maps all12 original missing lines with exact original text and real STA instances, retaining v1 exact-set gates and all denominators"],
                full_classified_DA_and_deltas_SHA256=sha(run/"exclusive-coverage-audit-v1.json"))
    out=run/"exclusive-coverage-classifier-v4.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))
