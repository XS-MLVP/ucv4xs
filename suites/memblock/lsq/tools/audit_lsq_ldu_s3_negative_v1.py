#!/usr/bin/env python3
"""Copied-public-history S3 negative controls; not new native tests."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import audit_lsq_ldu_s3_pipeline_v1 as pipeline
from audit_lsq_population_v1 import events, paths_by_node
from audit_sq_initial import ROOT, sha, verify_common


def audit():
    run=ROOT/"results/lsq-ldu-s3-01"
    manifest,_,nodes=verify_common(run)
    assert manifest["tests"]=={"PASS":17,"FAIL":9}
    candidates=[(node,path,list(events(path))) for node,path in sorted(paths_by_node(run).items()) if not nodes[node] and "s3_mixed.py" in node]
    controls=[]
    def mutate(label,predicate,change):
        for node,path,rows in candidates:
            found=next(((n,l) for n,r in enumerate(rows) for l,q in enumerate(r["input"]["loads"])
                        if q["execution"]["valid"] and predicate(q,r,l)),None)
            if found is None:continue
            n,l=found
            copy=list(rows)
            copy[n]=deepcopy(rows[n])
            change(copy[n]["input"]["loads"][l],copy[n],l)
            before=sha(path)
            try:
                with patch.object(pipeline,"events",lambda _:copy):pipeline.inspect(path,passed=True)
            except AssertionError as exc:reason=str(exc)
            else:raise AssertionError(("auditor accepted copied-history corruption",label))
            assert sha(path)==before
            controls.append(dict(control=label,rejected=True,nodeid=node,tick=rows[n]["post_tick"],lane=l,error=reason,original_raw_SHA256=before))
            return
        raise AssertionError(("negative-control precondition not actually reached",label))
    replay=lambda q,r,l:q["execution"]["need_replay"] and not q["exceptions"] and not q["update_address"]
    mutate("wrong_aligned_type",replay,lambda q,r,l:q["execution"].update(aligned_type=0))
    mutate("wrong_PA_bit6_lastBeat",replay,lambda q,r,l:q["execution"].update(last_beat=not q["execution"]["last_beat"]))
    mutate("normal_Replay_fake_address_writeback",replay,lambda q,r,l:q.update(update_address=True))
    mutate("Replay_missing_native_RAR_revoke",replay,lambda q,r,l:r["input"]["rar_revoke_last"].__setitem__(l,False))
    mutate("first_uncache_fake_writeback",lambda q,r,l:bool(q["mmio"] or q["execution"]["nc"]) and q["execution"]["causes"]==1 and not q["update_address"],
           lambda q,r,l:q.update(update_address=True))
    mutate("returned_uncache_completion_suppressed",lambda q,r,l:bool(q["mmio"] or q["execution"]["nc"]) and not q["execution"]["need_replay"] and not q["exceptions"] and q["update_address"],
           lambda q,r,l:q.update(update_address=False))
    mutate("exception_writeback_suppressed",lambda q,r,l:bool(q["exceptions"]) and q["update_address"],lambda q,r,l:q.update(update_address=False))
    # Tail Query uses size4, while the original architectural scalar was size3.
    mutate("S4_writeback_flipped",lambda q,r,l:q["execution"]["aligned_type"]==4 and q["execution"]["uop"]["operation"]==6,
           lambda q,r,l:q.update(update_address=not q["update_address"]))
    dest=run/"evidence-auditors"
    target=dest/Path(__file__).name
    if target.exists():assert sha(target)==sha(Path(__file__))
    else:shutil.copy2(__file__,target)
    report=dict(run=run.name,status="EIGHT_S3_SOURCE_NEGATIVE_CONTROLS_REJECTED_NOT_NATIVE_CASES",controls=controls,auditor_SHA256=sha(Path(__file__)),
                limits="In-memory copied public inputs only; originals, native outcomes and coverage unchanged. Necessary stage gate sensitivity, not RTL defects or dynamically missing split-error coverage.")
    out=run/"ldu-s3-negative-controls-v1.json"
    if out.exists():assert json.loads(out.read_text())==report
    else:out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=="__main__":audit()
