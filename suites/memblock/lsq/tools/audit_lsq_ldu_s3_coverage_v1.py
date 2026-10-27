#!/usr/bin/env python3
"""Corrected S3 26-node run: own DA equals old26 union, not a coverage gain claim."""
import argparse
import json
from pathlib import Path
import shutil

from audit_lsq_ldu_mixed_coverage_v2 import classify
from audit_progress_run_v10 import coverage_signature
from audit_sq_initial import ROOT, sha, verify_common


def audit(name):
    assert name=="lsq-ldu-s3-01"
    run=ROOT/"results"/name
    manifest,source,_=verify_common(run)
    assert manifest["tests"]=={"PASS":17,"FAIL":9}
    row=json.loads((run/"line-audit.json").read_text())["native"][0]
    current=coverage_signature(row)
    union={}
    prior={}
    for name in("lsq-ldu-rar-routing-03","lsq-ldu-mixed-02"):
        previous=ROOT/"results"/name
        old=json.loads((previous/"line-audit.json").read_text())["native"][0]
        prior[name]=dict(manifest_SHA256=sha(previous/"execution/manifest.json"),own_hit=old["closure_line_hit"])
        for file,(digest,lines) in coverage_signature(old).items():
            if file in union:assert union[file][0]==digest
            dst=union.setdefault(file,(digest,{}))[1]
            for n,hit in lines:dst[n]=dst.get(n,False) or hit
    assert union.keys()==current.keys()
    for file,(digest,lines) in current.items():assert union[file]==(digest,dict(lines))
    mapped,counts=classify(row)
    assert row["closure_line_hit"]==40521 and row["closure_line_total"]==59602 and sum(counts.values())==19081
    semantic=json.loads((run/"ldu-s3-audit-v1.json").read_text())
    assert semantic["all26_actual_public_pre_post_output_histories_bitwise_equal"]
    dest=run/"evidence-auditors"
    dest.mkdir(exist_ok=True)
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(run=run.name,status="S3_PRODUCER_CORRECTION_NOT_NEW_DA_GAIN_ALL19081_OWN_GAPS_CLASSIFIED",tests=manifest["tests"],snapshot_files=len(source),
                own_hit=40521,original_denominator=59602,remaining=19081,new_hits_versus_old26_native_union=0,old_hit_loss=0,
                previous_distinct_native_runs=prior,missing_by_source=dict(counts),native_classified=mapped,auditor_SHA256=sha(Path(__file__)),
                limits="Old two-run DA union is only a repeatability comparison; current40521 comes from this real26-node Wrapper run itself. All old source-admission rejections remain; new762 S3 source checks are not RTL line gains. Remaining pool/slot/entry/wrap/recovery cases need source-valid native additions, not all-pool quiescent snapshots with missing revokes or illegal CBO admission. No whole-goal signoff.")
    out=run/"ldu-s3-coverage-audit-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k!="native_classified"},indent=2,ensure_ascii=False))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    audit(p.parse_args().name)
