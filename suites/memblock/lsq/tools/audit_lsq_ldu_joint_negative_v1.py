#!/usr/bin/env python3
"""Copied histories: reject broken source/UID/pool/CBO relations, not DUT cases."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import audit_lsq_cbo_serialization_v2 as cbo
import audit_lsq_ldu_joint_pools_v1 as core
from audit_lsq_ldu_joint_pools_v3 import PhasedPools
import audit_lsq_ldu_s3_pipeline_v1 as pipeline
from audit_lsq_population_v1 import events, paths_by_node
from audit_lsq_bus_v2 import rob
from audit_sq_initial import ROOT, sha, verify_common


def inspect(rows):
    a=PhasedPools()
    # Negative controls deliberately alter a copied public value. Bypass only
    # the fixture-comparison validator here, to test semantic reconstruction
    # itself rather than have expected_after reject every mutation trivially.
    with patch.object(core,"validate_row",lambda *args:None):
        for row in rows:a.step(row)
    return a.finish(passed=True)


def audit():
    run=ROOT/"results/lsq-ldu-joint-phases-04"
    manifest,_,_=verify_common(run)
    assert manifest["tests"]=={"PASS":6,"FAIL":6}
    node,path=next((n,p) for n,p in sorted(paths_by_node(run).items()) if "[8-none-29456]" in n)
    rows=list(events(path))
    original_hash=sha(path)
    controls=[]
    def reject(label,mutation,reader="pool"):
        try:
            if reader=="pool":inspect(mutation)
            elif reader=="pipeline":
                with patch.object(pipeline,"events",lambda _:mutation):pipeline.inspect(path,passed=True)
            else:
                with patch.object(cbo,"events",lambda _:mutation):result=cbo.inspect(path)
                assert not result["violations"],"NoSpec/BlockBack public permission violation detected"
        except AssertionError as exc:controls.append(dict(control=label,rejected=True,error=str(exc)))
        else:raise AssertionError(("semantic auditor accepted copied corruption",label))
    n,l=next((n,l) for n,r in enumerate(rows) for l,q in enumerate(r["input"]["loads"]) if q["execution"]["valid"] and q["execution"]["uop"]["lq"]["value"]==1 and q["execution"]["causes"]==1)
    changed=list(rows);changed[n]=deepcopy(rows[n])
    changed[n]["input"]["rar_revoke_last"][l]=False
    reject("missing_original_NC_RAR_revoke_cannot_inflate_peak",changed)
    changed=list(rows);changed[n]=deepcopy(rows[n])
    changed[n]["input"]["loads"][l]["update_address"]=True
    reject("first_uncache_fake_S3_writeback",changed,"pipeline")
    n=next(n for n,r in enumerate(rows) if r["after"]["io_toLsqEnqCtrl_lqDeq_valid"])
    changed=list(rows);changed[n]=deepcopy(rows[n])
    changed[n]["after"]["io_toLsqEnqCtrl_lqDeq_bits"]+=1
    reject("extra_VLQ_credit_without_original_completion",changed)
    n,l=next((n,l) for n,r in enumerate(rows) for l,q in enumerate(r["input"]["raw_queries"]) if q["valid"] and q["sq"]["first"] and not q["sq"]["second"] and q["sq"]["value"]==0)
    changed=list(rows);changed[n]=deepcopy(rows[n])
    changed[n]["input"]["raw_queries"][l]["sq"]["first"]=False
    reject("exclusive128_falsely_rebound_to_old_head",changed)
    n=next(n for n,r in enumerate(rows) if any(a["valid"] and a["fu_op"]&1 for a in r["input"]["addresses"]))-1
    # Find the actual CBO allocation preceding that STA; change only copied ROB
    # head so a real old instruction remains unretired at CBO admission.
    n=max(k for k in range(n+1) if any(d["valid"] for d in rows[k]["input"]["dispatch"]))
    changed=list(rows);changed[n]=deepcopy(rows[n])
    order=(rob(changed[n]["input"]["pending"])-1)%640
    changed[n]["input"]["pending"]=dict(flag=bool(order//320),value=order//2%160,former=not bool(order%2))
    reject("CBO_NoSpec_with_prior_unretired_ROB",changed,"cbo")
    assert sha(path)==original_hash
    dest=run/"evidence-auditors"
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(run=run.name,status="FIVE_INDEPENDENT_SEMANTIC_NEGATIVE_CONTROLS_REJECTED_NOT_NATIVE_CASES",nodeid=node,raw_SHA256=original_hash,controls=controls,auditor_SHA256=sha(Path(__file__)),
                limits="In-memory copied inputs/outputs, semantic pool validator intentionally bypasses fixture expected-value gate only inside negative control. Original journals/native source/results/coverage untouched. Does not add RTL FAILs or prove unexecuted full-domain scenarios.")
    out=run/"ldu-joint-negative-controls-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=="__main__":audit()
