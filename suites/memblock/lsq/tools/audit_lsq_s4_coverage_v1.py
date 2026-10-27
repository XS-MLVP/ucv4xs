#!/usr/bin/env python3
"""S4 own native line inventory and exact before/after, no old numerator merge."""
import argparse
import json
from pathlib import Path
import shutil

from audit_lsq_ldu_mixed_coverage_v2 import classify
from audit_progress_run_v10 import coverage_signature
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name in ("lsq-ldu-s4-02","lsq-ldu-s4-03")
    run=ROOT/"results"/name
    manifest,source,_=verify_common(run)
    native=json.loads((run/"line-audit.json").read_text())["native"][0]
    classified,counts=classify(native)
    for entry in(classified,*classified["dependencies"]):
        file=Path(entry["source"]).name
        for gap in entry["uncovered"]:
            gap["scope"]="THIS_SOURCE_CORRECT_S4_NATIVE_RUN_ONLY_NOT_PREVIOUS_DA_OR_LEAF_UNION"
            if file in("VirtualLoadQueue.sv","VirtualStoreQueue.sv") or file.startswith("FreeList") or file.startswith("Lq"):
                gap["features"]=sorted(set((*gap["features"],"S4E-IDENTITY","S4E-TRAP-REUSE","S4E-EPOCH")))
                gap["semantic_gap"]="已有身份/回收功能缺具体slot/lane/flag/原UID代际情形；首轮小S4程序仅LQ0/1、SQ0。补连续真实完成/陷入取消与同槽新UID、完整非二次幂LQ回绕、SQ物理窗口和ROB代际，不预置指针或借旧分子"
            elif file=="LoadQueueReplay.sv":
                gap["features"]=sorted(set((*gap["features"],"S4E-REPLAY","S4E-EPOCH")))
                gap["semantic_gap"]="S4首轮只需少量nack/miss原slot；缺各entry/lane/代际的head/tail原因、MSHR、真实grant/反馈保存和回收情形。先补真实跨代重用，容量/其他原因另需完整范围，不以全行或接口包代替"
            elif file in("LoadQueueRAR.sv","LoadQueueRAW.sv"):
                gap["features"]=sorted(set((*gap["features"],"S4E-REVOKE","S4E-EPOCH")))
                gap["semantic_gap"]="S4双段真实query/revoke只访问少数记录；缺各记录/入口与head/older撤销、回收、原较老STA冲突和coherence情况。补跨代投机查询再精确撤销/原完成；RAW物理slot不公开则只给完整signature"
    comparison={}
    if name.endswith("03"):
        prior=ROOT/"results/lsq-ldu-s4-02"
        old=json.loads((prior/"line-audit.json").read_text())["native"][0]
        before,after=coverage_signature(old),coverage_signature(native)
        assert before.keys()==after.keys()
        per={}
        for file,(digest,lines) in after.items():
            assert before[file][0]==digest and dict(lines).keys()==dict(before[file][1]).keys()
            b=dict(before[file][1])
            per[Path(file).name]=dict(added=sum(hit and not b[n] for n,hit in lines),lost=sum(b[n] and not hit for n,hit in lines))
        added,lost=sum(v["added"] for v in per.values()),sum(v["lost"] for v in per.values())
        assert not lost and native["closure_line_hit"]==old["closure_line_hit"]+added
        comparison=dict(run=prior.name,old_own_hit=old["closure_line_hit"],added=added,lost=lost,by_source=per)
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(run=name,status="SOURCE_S4_OWN_DA_EACH_GAP_CLASSIFIED_NOT_FINAL_SIGNOFF",tests=manifest["tests"],snapshot_files=len(source),
                own_hit=native["closure_line_hit"],original_denominator=native["closure_line_total"],remaining=sum(counts.values()),missing_by_source=dict(counts),
                native_classified=classified,comparison=comparison,auditor_SHA256=sha(Path(__file__)),
                distinction="S4 exception/fullva/Replay projection is an omitted whole source relation in older coarse gates; remaining concrete slot/lane/flag/epoch saves are missing situations of existing identity/recovery/Replay functions, not arbitrary hardware enumeration.",
                limits="Actual native DA only. No exclusions, old53079/59595 or leaf numerator merge; unexecuted lines remain unproven and retain denominator. Source boundary assumptions are not native LoadUnit proof. Original mixed FAILs, all remaining capacity/128/recovery/local-only/final goal scope stay.")
    out=run/"s4-coverage-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="native_classified"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
