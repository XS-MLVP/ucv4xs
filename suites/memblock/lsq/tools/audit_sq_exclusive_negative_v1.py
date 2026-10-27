#!/usr/bin/env python3
"""In-memory auditor negative controls; never counted as native DUT tests."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import audit_sq_exclusive_pipeline_v1 as pipeline
import audit_sq_exclusive_pool_v1 as pool
from audit_lsq_population_v1 import events, paths_by_node
from audit_sq_initial import ROOT, sha, verify_common


def audit():
    run=ROOT/"results/lsq-raw-exclusive-06"
    manifest,_,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":75}
    node,path=next(iter(sorted(paths_by_node(run).items())))
    rows=list(events(path))
    index,lane=next((n,l) for n,r in enumerate(rows) for l,q in enumerate(r["input"]["loads"]) if q["execution"]["valid"] and q["execution"]["need_replay"])
    mutations=[]
    for field,value in(("aligned_type",0),("last_beat",not rows[index]["input"]["loads"][lane]["execution"]["last_beat"]),("update_address",True)):
        changed=list(rows)
        changed[index]=deepcopy(rows[index])
        packet=changed[index]["input"]["loads"][lane]
        if field=="update_address":packet[field]=value
        else:packet["execution"][field]=value
        mutations.append((field,pipeline,path,changed,dict(passed=True)))
    report=json.loads((run/"exclusive-pool-audit-v1.json").read_text())
    poolpath=run/report["new_leaf_cases"][0]["journal"]
    poolrows=list(events(poolpath))
    n=next(n for n,r in enumerate(poolrows) if any(q["valid"] for q in r["input"]["enqueues"]))
    changed=list(poolrows)
    changed[n]=deepcopy(poolrows[n])
    changed[n]["after"]["io_replay_0_valid"]=1
    mutations.append(("spurious_grant_before_RAW_credit_or_prefix",pool,poolpath,changed,{}))
    results=[]
    before={str(p.relative_to(ROOT)):sha(p) for p in(path,poolpath)}
    for label,module,original,mutation,kwargs in mutations:
        try:
            reader="checked_rows" if module is pool else "events"
            with patch.object(module,reader,lambda _:mutation):
                module.inspect(original,**kwargs)
        except AssertionError as exc:
            results.append(dict(control=label,rejected=True,error=str(exc)))
        else:raise AssertionError(("auditor accepted corrupted public history",label))
    assert before=={str(p.relative_to(ROOT)):sha(p) for p in(path,poolpath)}
    dest=run/"evidence-auditors"
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    result=dict(status="FOUR_AUDITOR_NEGATIVE_CONTROLS_REJECTED_NOT_NATIVE_DUT_CASES",run=run.name,original_Wrapper_node=node,
                original_raw_SHA256=before,controls=results,auditor_SHA256=sha(Path(__file__)),
                limits="In-memory copied public-history mutations only. No original raw/source/native result overwritten; these are not RTL failures, native executions, additional functional checks or whole-goal signoff.")
    out=run/"exclusive-negative-controls-v1.json"
    if out.exists():assert json.loads(out.read_text())==result
    else:out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=="__main__":audit()
